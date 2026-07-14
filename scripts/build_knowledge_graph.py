import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ETL_DIR = DATA_DIR / "etl"
KG_DIR = DATA_DIR / "kg"

UNIFIED_JOBS_PATH = ETL_DIR / "unified_jobs.csv"
NODES_PATH = KG_DIR / "nodes.csv"
EDGES_PATH = KG_DIR / "edges.csv"
ROLE_ALIASES_PATH = KG_DIR / "role_aliases.csv"
SKILL_TRENDS_PATH = KG_DIR / "skill_trends.csv"
GRAPH_VERSIONS_PATH = KG_DIR / "graph_versions.csv"
MANIFEST_PATH = KG_DIR / "kg_manifest.json"


NODE_FIELDS = ["id", "label", "type", "canonical", "count", "first_seen", "last_seen", "properties"]
EDGE_FIELDS = ["id", "from", "to", "type", "weight", "confidence", "first_seen", "last_seen", "evidence"]
ROLE_ALIAS_FIELDS = ["alias", "canonical_role_id", "canonical_role", "evidence_count"]
SKILL_TREND_FIELDS = ["period", "role_id", "role", "skill", "dimension", "demand", "source_count"]
GRAPH_VERSION_FIELDS = ["version_id", "period", "node_count", "edge_count", "job_count", "skill_mentions"]


DIMENSION_BY_SKILL = {
    "Java": "编程语言",
    "Python": "编程语言",
    "Go": "编程语言",
    "C++": "编程语言",
    "JavaScript": "编程语言",
    "React": "前端开发",
    "Vue": "前端开发",
    "SQL": "数据技术",
    "Redis": "数据存储",
    "Kafka": "中间件",
    "Docker": "云原生",
    "Kubernetes": "云原生",
    "Linux": "基础设施",
    "Microservices": "系统架构",
    "DevOps": "工程效能",
    "Big Data": "数据工程",
    "Data Warehouse": "数据工程",
    "Machine Learning": "人工智能",
    "Deep Learning": "人工智能",
    "NLP": "人工智能",
    "LLM": "人工智能",
    "RAG": "人工智能",
    "Vector Search": "人工智能",
    "Testing": "质量保障",
    "Security": "安全合规",
    "Product": "产品运营",
    "Marketing": "产品运营",
    "Design": "设计体验",
    "Excel": "办公分析",
}

DIMENSION_PARENT = {
    "编程语言": "工程基础能力",
    "前端开发": "工程研发能力",
    "数据技术": "数据能力",
    "数据存储": "数据能力",
    "中间件": "工程基础能力",
    "云原生": "基础设施能力",
    "基础设施": "基础设施能力",
    "系统架构": "工程研发能力",
    "工程效能": "工程研发能力",
    "数据工程": "数据能力",
    "人工智能": "智能技术能力",
    "质量保障": "工程质量能力",
    "安全合规": "安全能力",
    "产品运营": "业务能力",
    "设计体验": "体验能力",
    "办公分析": "通用能力",
}

ROLE_RULES = [
    ("java-backend-engineer", "Java 后端工程师", ["java", "spring", "后端", "后台"]),
    ("backend-engineer", "后端工程师", ["backend", "server", "后端", "后台", "服务端"]),
    ("frontend-engineer", "前端工程师", ["frontend", "front end", "前端", "react", "vue", "web"]),
    ("mobile-engineer", "移动端工程师", ["android", "ios", "客户端", "移动端"]),
    ("ai-algorithm-engineer", "AI 算法工程师", ["算法", "机器学习", "深度学习", "nlp", "llm", "大模型", "aigc"]),
    ("data-engineer", "数据工程师", ["数据开发", "数据工程", "大数据", "数仓", "etl", "hadoop", "spark", "flink"]),
    ("cloud-sre-engineer", "云原生 SRE 工程师", ["sre", "devops", "运维", "kubernetes", "k8s", "云原生"]),
    ("security-engineer", "安全工程师", ["安全", "security", "风控", "攻防", "漏洞"]),
    ("testing-engineer", "测试工程师", ["测试", "qa", "质量", "自动化测试"]),
    ("product-manager", "产品经理", ["产品经理", "产品", "product manager"]),
    ("operations-specialist", "运营", ["运营", "增长", "marketing"]),
    ("designer", "设计师", ["设计", "ui", "ux", "交互", "视觉"]),
]


def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def slug(value):
    value = normalize_text(value).lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value).strip("-")
    return value or "unknown"


def parse_skills(value):
    result = []
    for item in str(value or "").split("|"):
        item = normalize_text(item)
        if item and item not in result:
            result.append(item)
    return result


def parse_period(value):
    value = normalize_text(value)
    if not value:
        return "unknown"
    match = re.search(r"(\d{4})年\s*(\d{1,2})月", value)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}"
    match = re.search(r"(\d{4})[-/](\d{1,2})", value)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m")
    except ValueError:
        return "unknown"


def date_sort_key(period):
    if re.match(r"\d{4}-\d{2}$", period):
        return period
    return "0000-00"


def canonical_role(row, skills):
    text = " ".join([
        row.get("job_title", ""),
        row.get("category", ""),
        row.get("normalized_category", ""),
        " ".join(skills),
    ]).lower()
    for role_id, label, keywords in ROLE_RULES:
        if any(keyword.lower() in text for keyword in keywords):
            return role_id, label

    title = normalize_text(row.get("job_title", ""))
    title = re.sub(r"[（(].*?[）)]", "", title)
    title = re.sub(r"(高级|资深|专家|实习|校招|社招|初级|中级|senior|staff|principal)", "", title, flags=re.I)
    title = normalize_text(title)
    if not title:
        title = row.get("normalized_category", "其他岗位")
    return f"role-{slug(title)}", title


def skill_dimension(skill):
    return DIMENSION_BY_SKILL.get(skill, "其他能力")


def add_node(nodes, node_id, label, node_type, canonical, period, properties=None):
    item = nodes.setdefault(node_id, {
        "id": node_id,
        "label": label,
        "type": node_type,
        "canonical": canonical,
        "count": 0,
        "first_seen": period,
        "last_seen": period,
        "properties": json.dumps(properties or {}, ensure_ascii=False),
    })
    item["count"] += 1
    if date_sort_key(period) < date_sort_key(item["first_seen"]):
        item["first_seen"] = period
    if date_sort_key(period) > date_sort_key(item["last_seen"]):
        item["last_seen"] = period


def add_edge(edges, from_id, to_id, edge_type, period, evidence):
    edge_id = f"{from_id}->{edge_type}->{to_id}"
    item = edges.setdefault(edge_id, {
        "id": edge_id,
        "from": from_id,
        "to": to_id,
        "type": edge_type,
        "weight": 0,
        "confidence": 0,
        "first_seen": period,
        "last_seen": period,
        "evidence": evidence[:300],
    })
    item["weight"] += 1
    item["confidence"] = min(1.0, round(0.55 + item["weight"] * 0.03, 2))
    if date_sort_key(period) < date_sort_key(item["first_seen"]):
        item["first_seen"] = period
    if date_sort_key(period) > date_sort_key(item["last_seen"]):
        item["last_seen"] = period


def build():
    jobs = read_csv(UNIFIED_JOBS_PATH)
    nodes = {}
    edges = {}
    alias_counts = Counter()
    trend_counts = Counter()
    trend_sources = defaultdict(set)
    period_jobs = Counter()
    period_skill_mentions = Counter()

    for row in jobs:
        skills = parse_skills(row.get("normalized_skills", ""))
        if not skills:
            continue
        period = parse_period(row.get("published_at") or row.get("collected_at"))
        role_id, role_label = canonical_role(row, skills)
        role_node_id = f"role:{role_id}"
        title_alias = normalize_text(row.get("job_title", ""))
        alias_counts[(title_alias, role_id, role_label)] += 1
        period_jobs[period] += 1

        add_node(nodes, role_node_id, role_label, "job", role_id, period, {
            "category": row.get("normalized_category", ""),
            "sample_title": title_alias,
        })

        for skill in skills:
            dimension = skill_dimension(skill)
            parent = DIMENSION_PARENT.get(dimension, "其他能力")
            skill_id = f"skill:{slug(skill)}"
            dim_id = f"cap:{slug(dimension)}"
            parent_id = f"cap:{slug(parent)}"

            add_node(nodes, skill_id, skill, "skill", skill, period)
            add_node(nodes, dim_id, dimension, "capability", dimension, period)
            add_node(nodes, parent_id, parent, "capability", parent, period)

            add_edge(edges, role_node_id, skill_id, "requires", period, row.get("source_url", ""))
            add_edge(edges, skill_id, dim_id, "belongs_to", period, skill)
            add_edge(edges, dim_id, parent_id, "part_of", period, dimension)

            trend_counts[(period, role_id, role_label, skill, dimension)] += 1
            trend_sources[(period, role_id, skill)].add(row.get("source_id", ""))
            period_skill_mentions[period] += 1

    nodes_rows = sorted(nodes.values(), key=lambda item: (item["type"], -item["count"], item["label"]))
    edge_rows = sorted(edges.values(), key=lambda item: (item["type"], -item["weight"], item["from"], item["to"]))
    alias_rows = [
        {
            "alias": alias,
            "canonical_role_id": role_id,
            "canonical_role": role_label,
            "evidence_count": count,
        }
        for (alias, role_id, role_label), count in alias_counts.items()
        if alias
    ]
    alias_rows.sort(key=lambda item: (-int(item["evidence_count"]), item["canonical_role"], item["alias"]))

    trend_rows = []
    for (period, role_id, role_label, skill, dimension), demand in trend_counts.items():
        trend_rows.append({
            "period": period,
            "role_id": role_id,
            "role": role_label,
            "skill": skill,
            "dimension": dimension,
            "demand": demand,
            "source_count": len(trend_sources[(period, role_id, skill)]),
        })
    trend_rows.sort(key=lambda item: (date_sort_key(item["period"]), item["role"], -int(item["demand"])))

    version_rows = []
    for period in sorted(period_jobs, key=date_sort_key):
        active_nodes = {item["id"] for item in nodes_rows if date_sort_key(item["first_seen"]) <= date_sort_key(period) <= date_sort_key(item["last_seen"])}
        active_edges = {item["id"] for item in edge_rows if date_sort_key(item["first_seen"]) <= date_sort_key(period) <= date_sort_key(item["last_seen"])}
        version_rows.append({
            "version_id": f"kg-{period}",
            "period": period,
            "node_count": len(active_nodes),
            "edge_count": len(active_edges),
            "job_count": period_jobs[period],
            "skill_mentions": period_skill_mentions[period],
        })

    write_csv(NODES_PATH, NODE_FIELDS, nodes_rows)
    write_csv(EDGES_PATH, EDGE_FIELDS, edge_rows)
    write_csv(ROLE_ALIASES_PATH, ROLE_ALIAS_FIELDS, alias_rows)
    write_csv(SKILL_TRENDS_PATH, SKILL_TREND_FIELDS, trend_rows)
    write_csv(GRAPH_VERSIONS_PATH, GRAPH_VERSION_FIELDS, version_rows)

    manifest = {
        "generated_at": now_iso(),
        "input": str(UNIFIED_JOBS_PATH.relative_to(ROOT)),
        "outputs": [
            str(NODES_PATH.relative_to(ROOT)),
            str(EDGES_PATH.relative_to(ROOT)),
            str(ROLE_ALIASES_PATH.relative_to(ROOT)),
            str(SKILL_TRENDS_PATH.relative_to(ROOT)),
            str(GRAPH_VERSIONS_PATH.relative_to(ROOT)),
        ],
        "job_records_read": len(jobs),
        "nodes": len(nodes_rows),
        "edges": len(edge_rows),
        "role_aliases": len(alias_rows),
        "trend_rows": len(trend_rows),
        "versions": len(version_rows),
        "entity_disambiguation": [
            "Normalize role titles by removing seniority/recruitment modifiers.",
            "Map aliases such as Java开发、Java工程师、后端开发 into canonical role nodes.",
            "Keep data/kg/role_aliases.csv as auditable evidence for role merging.",
        ],
        "relationship_inference": [
            "Infer role -> skill requires edges from extracted skill mentions.",
            "Infer skill -> capability belongs_to edges from skill taxonomy.",
            "Infer capability -> parent capability part_of edges from hierarchy rules.",
        ],
        "temporal_model": [
            "Use monthly period from published_at, falling back to collected_at.",
            "Write graph_versions.csv for versioned graph snapshots.",
            "Write skill_trends.csv for queries like demand in the past N months.",
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
