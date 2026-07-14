import csv
import hashlib
import html
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from bilingual_matching import skill_hits
import job_taxonomy as taxonomy


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ETL_DIR = DATA_DIR / "etl"

JOBS_PATH = DATA_DIR / "collected_jobs.csv"
SKILLS_PATH = DATA_DIR / "collected_job_skills.csv"
REGISTRY_PATH = DATA_DIR / "source_registry.csv"
RESUME_SAMPLES_PATH = DATA_DIR / "resume_samples.csv"
APPLICATION_OUTCOMES_PATH = DATA_DIR / "application_outcomes.csv"

UNIFIED_JOBS_PATH = ETL_DIR / "unified_jobs.csv"
UNIFIED_SKILLS_PATH = ETL_DIR / "unified_job_skills.csv"
QUALITY_REPORT_PATH = ETL_DIR / "data_quality_report.csv"
CANDIDATE_SCORES_PATH = ETL_DIR / "job_candidate_scores.csv"
MANIFEST_PATH = ETL_DIR / "etl_manifest.json"


UNIFIED_JOB_FIELDS = [
    "record_id",
    "origin_record_id",
    "source_id",
    "source_type",
    "source_name",
    "source_url",
    "collected_at",
    "published_at",
    "country",
    "province",
    "city",
    "company",
    "department",
    "product",
    "category",
    "normalized_category",
    "role_id",
    "role_name",
    "job_title",
    "job_type",
    "work_years",
    "responsibility",
    "requirement",
    "raw_text",
    "normalized_skills",
    "skill_count",
    "skill_evidence",
    "capability_dimensions",
    "capability_scores",
    "estimated_application_success_probability",
    "relative_ability_score",
    "scoring_basis",
    "quality_score",
    "quality_level",
    "quality_flags",
    "content_hash",
]

UNIFIED_SKILL_FIELDS = [
    "record_id",
    "job_record_id",
    "source_id",
    "source_name",
    "skill",
    "evidence",
    "collected_at",
]

QUALITY_REPORT_FIELDS = [
    "source_id",
    "source_name",
    "source_type",
    "records",
    "avg_quality_score",
    "level_a",
    "level_b",
    "level_c",
    "level_d",
    "missing_title",
    "missing_source_url",
    "missing_collected_at",
    "missing_published_at",
    "missing_city",
    "missing_company",
    "missing_origin_record_id",
    "short_responsibility",
    "short_requirement",
    "no_skill_hit",
    "duplicate_content",
    "unknown_source",
]

CANDIDATE_SCORE_FIELDS = [
    "application_id",
    "resume_id",
    "job_record_id",
    "job_title",
    "company",
    "source_id",
    "matched_skills",
    "missing_skills",
    "skill_match_rate",
    "dimension_match_rate",
    "experience_match_score",
    "education_match_score",
    "relative_ability_score",
    "success_probability",
    "outcome_label",
    "scoring_basis",
    "scored_at",
]

SOURCE_ALIASES = {
    "Tencent Careers": "tencent_careers",
    "Alibaba Careers": "alibaba_careers",
    "NetEase Careers": "netease_careers",
    "Google Careers": "google_careers",
    "Apple Jobs": "apple_jobs",
    "Remote OK": "remoteok_public_api",
    "RemoteOK": "remoteok_public_api",
    "Arbeitnow": "arbeitnow_public_api",
    "Greenhouse ATS": "greenhouse_ats",
    "Lever ATS": "lever_ats",
    "Local Imported Dataset": "local_import_dataset",
}

FIELD_ALIASES = {
    "source": ["source", "source_name"],
    "postId": ["postId", "post_id", "origin_record_id", "id", "slug"],
    "title": ["title", "job_title", "position", "name"],
    "company": ["company", "company_name", "employer"],
    "bg": ["bg", "department", "business_group"],
    "product": ["product", "product_line"],
    "category": ["category", "job_category", "tags"],
    "city": ["city", "location"],
    "province": ["province", "state", "region"],
    "country": ["country"],
    "workYears": ["workYears", "work_years", "experience"],
    "lastUpdateTime": ["lastUpdateTime", "published_at", "date", "created_at", "updated_at"],
    "responsibility": ["responsibility", "description", "job_description"],
    "requirement": ["requirement", "requirements", "qualification", "qualifications"],
    "skills": ["skills", "normalized_skills", "tags"],
    "sourceUrl": ["sourceUrl", "source_url", "url", "apply_url"],
    "fetchedAt": ["fetchedAt", "collected_at", "fetched_at"],
    "jobType": ["jobType", "job_type", "employment_type"],
}

SKILL_ALIASES = {
    "Java": ["java", "jvm", "spring", "spring boot", "spring cloud"],
    "Python": ["python", "django", "flask", "fastapi"],
    "Go": ["go", "golang"],
    "C++": ["c++", "cpp"],
    "JavaScript": ["javascript", "typescript", "node.js", "nodejs"],
    "React": ["react", "next.js", "nextjs"],
    "Vue": ["vue", "vue.js"],
    "SQL": ["sql", "mysql", "postgresql", "oracle", "数据库"],
    "Redis": ["redis", "缓存"],
    "Kafka": ["kafka", "消息队列"],
    "Docker": ["docker", "容器"],
    "Kubernetes": ["kubernetes", "k8s", "云原生"],
    "Linux": ["linux"],
    "Microservices": ["microservice", "microservices", "微服务", "分布式"],
    "DevOps": ["devops", "ci/cd", "自动化部署"],
    "Big Data": ["大数据", "hadoop", "spark", "flink", "hive"],
    "Data Warehouse": ["数据仓库", "数仓", "etl"],
    "Machine Learning": ["机器学习", "machine learning", "tensorflow", "pytorch", "sklearn"],
    "Deep Learning": ["深度学习", "neural network", "神经网络"],
    "NLP": ["nlp", "自然语言", "语义分析", "命名实体"],
    "LLM": ["llm", "大模型", "large language model", "aigc", "生成式ai"],
    "RAG": ["rag", "检索增强", "知识库问答"],
    "Vector Search": ["向量检索", "embedding", "vector database", "向量数据库"],
    "Testing": ["测试", "qa", "automation testing", "自动化测试", "performance testing"],
    "Security": ["安全", "风控", "攻防", "漏洞", "合规"],
    "Product": ["产品经理", "product manager", "产品"],
    "Marketing": ["marketing", "增长", "运营", "seo"],
    "Design": ["设计", "ui", "ux", "交互", "视觉"],
    "Excel": ["excel", "vlookup", "pivot"],
}

CATEGORY_RULES = [
    ("ai_algorithm", ["大模型", "aigc", "人工智能", "机器学习", "深度学习", "算法", "nlp", "llm", "rag", "模型"]),
    ("data_engineering", ["大数据", "数据开发", "数据工程", "数据仓库", "数仓", "数据分析", "bi", "etl", "hadoop", "spark", "flink", "hive"]),
    ("frontend_client", ["前端", "frontend", "front end", "react", "vue", "android", "ios", "web", "移动端", "小程序"]),
    ("cloud_infra", ["云原生", "云计算", "运维", "sre", "devops", "kubernetes", "k8s", "docker", "linux", "网络架构", "基础架构", "platform engineer"]),
    ("security", ["安全", "security", "风控", "攻防", "漏洞", "合规"]),
    ("testing_quality", ["测试", "testing", "qa", "quality assurance", "质量", "自动化测试", "性能测试"]),
    ("product_operation", ["产品", "运营", "product manager", "project manager", "项目经理", "用户增长", "marketing", "sales"]),
    ("design", ["设计", "design", "交互", "ui", "ux", "视觉", "用研"]),
    ("backend_engineering", ["后台", "后端", "backend", "server", "java", "golang", "go", "c++", "分布式", "微服务", "接口"]),
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
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def first_value(row, canonical):
    for field in FIELD_ALIASES.get(canonical, [canonical]):
        value = row.get(field)
        if value not in (None, ""):
            return normalize_text(value)
    return ""


def source_id(source_name):
    if source_name in SOURCE_ALIASES:
        return SOURCE_ALIASES[source_name]
    return re.sub(r"[^a-z0-9]+", "_", str(source_name or "unknown").lower()).strip("_") or "unknown"


def parse_skills(value):
    seen = []
    chunks = re.split(r"[|,，;/；]+", str(value or ""))
    for item in chunks:
        item = normalize_text(item)
        if item and item not in seen:
            seen.append(item)
    return seen


def extract_skills(text):
    return taxonomy.extract_skills(text)


def normalized_row(row):
    source_name = first_value(row, "source") or "Unknown Source"
    responsibility = first_value(row, "responsibility")
    requirement = first_value(row, "requirement")
    if not requirement and len(responsibility) > 600:
        requirement = responsibility[600:]
        responsibility = responsibility[:600]
    return {
        "source": source_name,
        "postId": first_value(row, "postId"),
        "title": first_value(row, "title"),
        "company": first_value(row, "company"),
        "bg": first_value(row, "bg"),
        "product": first_value(row, "product"),
        "category": first_value(row, "category"),
        "city": first_value(row, "city"),
        "province": first_value(row, "province"),
        "country": first_value(row, "country") or "China",
        "workYears": first_value(row, "workYears"),
        "lastUpdateTime": first_value(row, "lastUpdateTime"),
        "responsibility": responsibility,
        "requirement": requirement,
        "skills": first_value(row, "skills"),
        "sourceUrl": first_value(row, "sourceUrl"),
        "fetchedAt": first_value(row, "fetchedAt"),
        "jobType": first_value(row, "jobType") or "full_time",
    }


def classify_job(row, skills):
    return taxonomy.classify_job(
        row.get("title", "") or row.get("job_title", ""),
        row.get("category", ""),
        row.get("responsibility", ""),
        row.get("requirement", ""),
        skills,
    )


def content_hash(row):
    text = "\n".join([
        normalize_text(row.get("title") or row.get("job_title")),
        normalize_text(row.get("company")),
        normalize_text(row.get("city")),
        normalize_text(row.get("responsibility")),
        normalize_text(row.get("requirement")),
    ])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def quality_level(score):
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def quality_score(row, skills, is_duplicate):
    normalized = normalized_row(row)
    score = 100
    flags = []
    checks = [
        ("title", 25, "missing_title"),
        ("sourceUrl", 15, "missing_source_url"),
        ("fetchedAt", 15, "missing_collected_at"),
        ("lastUpdateTime", 10, "missing_published_at"),
        ("city", 5, "missing_city"),
        ("company", 5, "missing_company"),
        ("postId", 5, "missing_origin_record_id"),
    ]
    for field, penalty, flag in checks:
        if not normalized.get(field):
            score -= penalty
            flags.append(flag)
    if len(normalized["responsibility"]) < 30:
        score -= 12
        flags.append("short_responsibility")
    if len(normalized["requirement"]) < 30:
        score -= 12
        flags.append("short_requirement")
    if not skills:
        score -= 10
        flags.append("no_skill_hit")
    if is_duplicate:
        score -= 20
        flags.append("duplicate_content")
    if source_id(normalized["source"]) == "unknown":
        score -= 10
        flags.append("unknown_source")
    return max(0, score), flags


def load_registry():
    registry = {}
    for row in read_csv(REGISTRY_PATH):
        registry[row["sourceId"]] = row
    return registry


def build_quality_report(unified_jobs):
    grouped = defaultdict(list)
    for row in unified_jobs:
        grouped[row["source_id"]].append(row)

    report = []
    for source, rows in grouped.items():
        levels = Counter(row["quality_level"] for row in rows)
        scores = [int(row["quality_score"]) for row in rows if str(row.get("quality_score", "")).isdigit()]
        flags = Counter()
        for row in rows:
            for flag in row["quality_flags"].split("|"):
                if flag:
                    flags[flag] += 1
        report.append({
            "source_id": source,
            "source_name": rows[0]["source_name"],
            "source_type": rows[0]["source_type"],
            "records": len(rows),
            "avg_quality_score": round(sum(scores) / len(scores), 2) if scores else 0,
            "level_a": levels["A"],
            "level_b": levels["B"],
            "level_c": levels["C"],
            "level_d": levels["D"],
            "missing_title": flags["missing_title"],
            "missing_source_url": flags["missing_source_url"],
            "missing_collected_at": flags["missing_collected_at"],
            "missing_published_at": flags["missing_published_at"],
            "missing_city": flags["missing_city"],
            "missing_company": flags["missing_company"],
            "missing_origin_record_id": flags["missing_origin_record_id"],
            "short_responsibility": flags["short_responsibility"],
            "short_requirement": flags["short_requirement"],
            "no_skill_hit": flags["no_skill_hit"],
            "duplicate_content": flags["duplicate_content"],
            "unknown_source": flags["unknown_source"],
        })
    return sorted(report, key=lambda item: item["records"], reverse=True)


def load_resume_profiles():
    profiles = []
    for row in read_csv(RESUME_SAMPLES_PATH):
        resume_id = row.get("id") or row.get("resume_id") or row.get("name") or f"resume-{len(profiles) + 1}"
        text = row.get("text") or row.get("raw_text") or row.get("description") or ""
        parsed = taxonomy.parse_resume_text(text)
        profiles.append({
            "resume_id": resume_id,
            "text": text,
            "skills": parsed["skills"],
            "years": parsed["years"],
            "education": parsed["education"],
            "dimensions": parsed["dimensions"],
        })
    return profiles


def load_application_outcomes():
    rows = []
    for row in read_csv(APPLICATION_OUTCOMES_PATH):
        rows.append({
            "application_id": row.get("application_id") or row.get("id") or f"application-{len(rows) + 1}",
            "resume_id": row.get("resume_id") or row.get("candidate_id") or "",
            "job_record_id": row.get("job_record_id") or row.get("record_id") or "",
            "outcome_label": row.get("outcome_label") or row.get("success") or row.get("hired") or "",
        })
    return rows


def build_candidate_scores(unified_jobs):
    profiles = {profile["resume_id"]: profile for profile in load_resume_profiles()}
    if not profiles:
        return [], {}

    jobs_by_id = {row["record_id"]: row for row in unified_jobs}
    outcomes = load_application_outcomes()
    scored_at = now_iso()
    rows = []
    best_by_job = {}
    max_rows = int(os.environ.get("ETL_MAX_CANDIDATE_SCORE_ROWS", "50000"))

    if outcomes:
        pairs = []
        for outcome in outcomes:
            profile = profiles.get(outcome["resume_id"])
            job = jobs_by_id.get(outcome["job_record_id"])
            if profile and job:
                pairs.append((outcome["application_id"], outcome["outcome_label"], profile, job))
    else:
        pairs = []
        for job in unified_jobs:
            for profile in profiles.values():
                pairs.append((
                    f"synthetic:{profile['resume_id']}:{job['record_id']}",
                    "",
                    profile,
                    job,
                ))
                if len(pairs) >= max_rows:
                    break
            if len(pairs) >= max_rows:
                break

    for application_id, outcome_label, profile, job in pairs[:max_rows]:
        score = taxonomy.score_application(job, profile, outcome_label)
        row = {
            "application_id": application_id,
            "resume_id": profile["resume_id"],
            "job_record_id": job["record_id"],
            "job_title": job["job_title"],
            "company": job["company"],
            "source_id": job["source_id"],
            "matched_skills": "|".join(score["matched_skills"]),
            "missing_skills": "|".join(score["missing_skills"]),
            "skill_match_rate": score["skill_match_rate"],
            "dimension_match_rate": score["dimension_match_rate"],
            "experience_match_score": score["experience_match_score"],
            "education_match_score": score["education_match_score"],
            "relative_ability_score": score["relative_ability_score"],
            "success_probability": score["success_probability"],
            "outcome_label": outcome_label,
            "scoring_basis": score["scoring_basis"],
            "scored_at": scored_at,
        }
        rows.append(row)
        current = best_by_job.get(job["record_id"])
        if current is None or float(row["relative_ability_score"]) > float(current["relative_ability_score"]):
            best_by_job[job["record_id"]] = row

    return rows, best_by_job


def transform_row(row, registry, seen_hashes):
    row = normalized_row(row)
    sid = source_id(row["source"])
    source = registry.get(sid, {})
    skills = parse_skills(row["skills"])
    text = " ".join([row["title"], row["category"], row["responsibility"], row["requirement"]])
    for skill in extract_skills(text):
        if skill not in skills:
            skills.append(skill)
    digest = content_hash(row)
    duplicate = digest in seen_hashes
    seen_hashes.add(digest)
    score, flags = quality_score(row, skills, duplicate)
    origin_id = row["postId"] or digest
    record_id = f"{sid}:{origin_id}"
    raw_text = normalize_text(" ".join([row["title"], row["responsibility"], row["requirement"]]))
    normalized_category = classify_job(row, skills)
    role_id, role_name = taxonomy.infer_role(row["title"], row["category"], normalized_category, skills)
    dimensions = taxonomy.capability_dimensions(skills)

    unified_job = {
        "record_id": record_id,
        "origin_record_id": origin_id,
        "source_id": sid,
        "source_type": source.get("sourceType", "unknown"),
        "source_name": source.get("sourceName", row["source"]),
        "source_url": row["sourceUrl"],
        "collected_at": row["fetchedAt"],
        "published_at": row["lastUpdateTime"],
        "country": row["country"],
        "province": row["province"],
        "city": row["city"],
        "company": row["company"],
        "department": row["bg"],
        "product": row["product"],
        "category": row["category"],
        "normalized_category": normalized_category,
        "role_id": role_id,
        "role_name": role_name,
        "job_title": row["title"],
        "job_type": row["jobType"],
        "work_years": row["workYears"],
        "responsibility": row["responsibility"],
        "requirement": row["requirement"],
        "raw_text": raw_text,
        "normalized_skills": "|".join(skills),
        "skill_count": len(skills),
        "skill_evidence": taxonomy.skill_evidence_json(raw_text),
        "capability_dimensions": "|".join(dimensions),
        "capability_scores": taxonomy.capability_scores_json(skills),
        "estimated_application_success_probability": "",
        "relative_ability_score": "",
        "scoring_basis": "",
        "quality_score": score,
        "quality_level": quality_level(score),
        "quality_flags": "|".join(flags),
        "content_hash": digest,
    }
    unified_skills = [
        {
            "record_id": f"{record_id}:skill:{index}",
            "job_record_id": record_id,
            "source_id": sid,
            "source_name": unified_job["source_name"],
            "skill": skill,
            "evidence": raw_text[:500],
            "collected_at": row["fetchedAt"],
        }
        for index, skill in enumerate(skills, start=1)
    ]
    return unified_job, unified_skills


def transform():
    registry = load_registry()
    source_types = sorted({row["sourceType"] for row in registry.values()})
    raw_jobs = read_csv(JOBS_PATH)
    raw_skills = read_csv(SKILLS_PATH)
    seen_hashes = set()

    skills_by_record = defaultdict(list)
    for row in raw_skills:
        sid = source_id(row.get("source", ""))
        key = f"{sid}:{row.get('postId', '')}"
        if row.get("skill"):
            skills_by_record[key].append(row)

    unified_jobs = []
    unified_skills = []
    seen_records = set()
    for raw_row in raw_jobs:
        job, extracted_skills = transform_row(raw_row, registry, seen_hashes)
        if job["record_id"] in seen_records:
            continue
        seen_records.add(job["record_id"])
        unified_jobs.append(job)

        evidence_rows = skills_by_record.get(job["record_id"], [])
        if evidence_rows:
            for index, skill_row in enumerate(evidence_rows, start=1):
                unified_skills.append({
                    "record_id": f"{job['record_id']}:skill:{index}",
                    "job_record_id": job["record_id"],
                    "source_id": job["source_id"],
                    "source_name": job["source_name"],
                    "skill": skill_row.get("skill", ""),
                    "evidence": normalize_text(skill_row.get("evidence", ""))[:500],
                    "collected_at": skill_row.get("fetchedAt", job["collected_at"]),
                })
        else:
            unified_skills.extend(extracted_skills)

    candidate_scores, best_scores = build_candidate_scores(unified_jobs)
    for job in unified_jobs:
        best = best_scores.get(job["record_id"])
        if best:
            job["estimated_application_success_probability"] = best["success_probability"]
            job["relative_ability_score"] = best["relative_ability_score"]
            job["scoring_basis"] = best["scoring_basis"]

    quality_report = build_quality_report(unified_jobs)
    write_csv(UNIFIED_JOBS_PATH, UNIFIED_JOB_FIELDS, unified_jobs)
    write_csv(UNIFIED_SKILLS_PATH, UNIFIED_SKILL_FIELDS, unified_skills)
    write_csv(QUALITY_REPORT_PATH, QUALITY_REPORT_FIELDS, quality_report)
    write_csv(CANDIDATE_SCORES_PATH, CANDIDATE_SCORE_FIELDS, candidate_scores)

    active_sources = sorted({row["source_id"] for row in unified_jobs})
    active_source_types = sorted({row["source_type"] for row in unified_jobs if row["source_type"]})
    manifest = {
        "generated_at": now_iso(),
        "input_files": [
            str(JOBS_PATH.relative_to(ROOT)),
            str(SKILLS_PATH.relative_to(ROOT)),
            str(REGISTRY_PATH.relative_to(ROOT)),
        ],
        "output_files": [
            str(UNIFIED_JOBS_PATH.relative_to(ROOT)),
            str(UNIFIED_SKILLS_PATH.relative_to(ROOT)),
            str(QUALITY_REPORT_PATH.relative_to(ROOT)),
            str(CANDIDATE_SCORES_PATH.relative_to(ROOT)),
        ],
        "unified_job_records": len(unified_jobs),
        "unified_skill_records": len(unified_skills),
        "candidate_score_records": len(candidate_scores),
        "registered_sources": len(registry),
        "registered_source_types": source_types,
        "active_sources": active_sources,
        "active_source_types": active_source_types,
        "category_counts": Counter(row["normalized_category"] for row in unified_jobs),
        "quality_rules": {
            "base_score": 100,
            "penalties": {
                "missing_title": 25,
                "missing_source_url": 15,
                "missing_collected_at": 15,
                "missing_published_at": 10,
                "missing_city": 5,
                "missing_company": 5,
                "missing_origin_record_id": 5,
                "short_responsibility": 12,
                "short_requirement": 12,
                "no_skill_hit": 10,
                "duplicate_content": 20,
                "unknown_source": 10,
            },
            "levels": {"A": ">=85", "B": "70-84", "C": "55-69", "D": "<55"},
        },
        "application_scoring": {
            "input_candidates": str(RESUME_SAMPLES_PATH.relative_to(ROOT)),
            "optional_outcomes": str(APPLICATION_OUTCOMES_PATH.relative_to(ROOT)),
            "output": str(CANDIDATE_SCORES_PATH.relative_to(ROOT)),
            "features": [
                "skill_match_rate",
                "dimension_match_rate",
                "experience_match_score",
                "education_match_score",
                "job_quality_score",
            ],
            "formula": "relative ability = 45% skill + 20% dimension + 20% experience + 10% education + 5% data quality; success probability = sigmoid(relative ability)",
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = transform()
    print(json.dumps(result, ensure_ascii=False, indent=2))
