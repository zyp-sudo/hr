import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import job_taxonomy as taxonomy


BASE = "https://careers.tencent.com/tencentcareer/api/post"
OUT_DIR = Path("data/raw/china_jobs/tencent")
DATA_DIR = Path("data")

KEYWORDS = [
    "Java",
    "Python",
    "Go",
    "C++",
    "AI",
    "人工智能",
    "大模型",
    "AIGC",
    "大数据",
    "数据开发",
    "数据分析",
    "数据仓库",
    "算法",
    "机器学习",
    "深度学习",
    "NLP",
    "后台开发",
    "后端开发",
    "前端开发",
    "客户端开发",
    "Android",
    "iOS",
    "云原生",
    "云计算",
    "数据工程",
    "物联网",
    "测试开发",
    "运维开发",
    "安全",
]

MAX_DETAILS = int(os.environ.get("TENCENT_JOB_MAX", "1200"))
PAGE_SIZE = int(os.environ.get("TENCENT_JOB_PAGE_SIZE", "20"))
PAGE_LIMIT_PER_KEYWORD = int(os.environ.get("TENCENT_JOB_PAGE_LIMIT", "30"))
WORKERS = int(os.environ.get("TENCENT_JOB_WORKERS", "24"))
RETRIES = int(os.environ.get("TENCENT_JOB_RETRIES", "3"))
REQUEST_SLEEP = float(os.environ.get("TENCENT_JOB_REQUEST_SLEEP", "0.02"))
MODE = os.environ.get("TENCENT_JOB_MODE", "all").lower()

SKILL_ALIASES = {
    "Java": ["Java", "JVM", "Spring", "Spring Boot", "SpringCloud", "Spring Cloud"],
    "Python": ["Python"],
    "Go": ["Go", "Golang"],
    "C++": ["C++"],
    "SQL": ["SQL", "MySQL", "PostgreSQL", "Oracle", "数据库"],
    "Redis": ["Redis", "缓存"],
    "Kafka": ["Kafka", "消息队列"],
    "Docker": ["Docker", "容器"],
    "Kubernetes": ["Kubernetes", "K8s", "云原生"],
    "Linux": ["Linux"],
    "微服务": ["微服务", "分布式"],
    "DevOps": ["DevOps", "CI/CD", "自动化部署"],
    "大数据": ["大数据", "Hadoop", "Spark", "Flink", "Hive"],
    "数据仓库": ["数据仓库", "数仓", "ETL"],
    "机器学习": ["机器学习", "Machine Learning", "TensorFlow", "Pytorch", "PyTorch", "deepSpeed"],
    "深度学习": ["深度学习", "神经网络"],
    "NLP": ["NLP", "自然语言处理", "语义分析", "命名实体识别"],
    "知识图谱": ["知识图谱", "图谱", "Neo4j"],
    "RAG": ["RAG", "检索增强生成", "知识库问答"],
    "向量检索": ["向量检索", "Embedding", "向量数据库"],
    "LLMOps": ["LLMOps", "大模型工程", "大模型平台"],
    "AIGC": ["AIGC", "生成式AI", "大模型"],
    "测试": ["测试", "自动化测试", "性能测试"],
    "物联网": ["物联网", "IoT", "MQTT", "边缘计算"],
    "安全": ["安全", "风控", "攻防", "漏洞"],
}

KEYWORDS = [
    "Java", "Python", "Go", "C++", "AI", "人工智能", "大模型", "AIGC",
    "大数据", "数据开发", "数据分析", "数据仓库", "算法", "机器学习", "深度学习",
    "NLP", "后台开发", "后端开发", "前端开发", "客户端开发", "Android", "iOS",
    "云原生", "云计算", "数据工程", "物联网", "测试开发", "运维开发", "安全",
]
SKILL_ALIASES = taxonomy.SKILL_ALIASES


def request_json(path, params):
    query = urllib.parse.urlencode(params)
    url = f"{BASE}/{path}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://careers.tencent.com/search.html",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    last_error = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.5 * attempt)
    raise RuntimeError(f"request failed after {RETRIES} retries: {url}") from last_error


def extract_skills(text):
    found = []
    lowered = text.lower()
    for canonical, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lowered:
                found.append(canonical)
                break
    return found


def clean(value):
    return " ".join(str(value or "").replace("\r", "\n").split())


def tencent_job_url(row):
    return row.get("PostURL") or f"http://careers.tencent.com/jobdesc.html?postId={row.get('PostId', '')}"


def safe_name(value):
    return urllib.parse.quote(value, safe="")


def collect_posts_for_keyword(keyword):
    rows = []
    logs = []
    for page in range(1, PAGE_LIMIT_PER_KEYWORD + 1):
        payload = request_json(
            "Query",
            {
                "timestamp": int(time.time() * 1000),
                "keyword": keyword,
                "pageIndex": page,
                "pageSize": PAGE_SIZE,
                "language": "zh-cn",
            },
        )
        raw_path = OUT_DIR / f"query_{safe_name(keyword)}_{page}.json"
        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        posts = payload.get("Data", {}).get("Posts") or []
        rows.extend(posts)
        logs.append({"keyword": keyword, "page": page, "count": len(posts)})
        if len(posts) < PAGE_SIZE:
            break
        time.sleep(REQUEST_SLEEP)
    return rows, logs


def collect_all_posts():
    rows = []
    logs = []
    first = request_json(
        "Query",
        {
            "timestamp": int(time.time() * 1000),
            "pageIndex": 1,
            "pageSize": PAGE_SIZE,
            "language": "zh-cn",
        },
    )
    count = int(first.get("Data", {}).get("Count") or 0)
    total_pages = min((count + PAGE_SIZE - 1) // PAGE_SIZE, (MAX_DETAILS + PAGE_SIZE - 1) // PAGE_SIZE)
    for page in range(1, total_pages + 1):
        payload = first if page == 1 else request_json(
            "Query",
            {
                "timestamp": int(time.time() * 1000),
                "pageIndex": page,
                "pageSize": PAGE_SIZE,
                "language": "zh-cn",
            },
        )
        raw_path = OUT_DIR / f"query_all_{page}.json"
        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        posts = payload.get("Data", {}).get("Posts") or []
        rows.extend(posts)
        logs.append({"keyword": "__ALL__", "page": page, "count": len(posts), "sourceCount": count})
        if len(rows) >= MAX_DETAILS or len(posts) < PAGE_SIZE:
            break
        time.sleep(REQUEST_SLEEP)
    return rows, logs


def collect_post_ids():
    seen = {}
    query_logs = []

    if MODE == "all":
        post_batches = [collect_all_posts()]
    else:
        post_batches = []
        for keyword in KEYWORDS:
            posts, logs = collect_posts_for_keyword(keyword)
            post_batches.append((posts, logs))
            print(f"[query] keyword={keyword} partial_posts={len(posts)}")
            if len(seen) >= MAX_DETAILS:
                break

    for posts, logs in post_batches:
        query_logs.extend(logs)
        for post in posts:
            post_id = str(post.get("PostId") or "")
            if post_id:
                seen.setdefault(post_id, post)
            if len(seen) >= MAX_DETAILS:
                break
        print(f"[query] mode={MODE} total_ids={len(seen)}")

    selected = dict(list(seen.items())[:MAX_DETAILS])
    (OUT_DIR / "post_candidates.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return selected, query_logs


def detail_path(post_id):
    return OUT_DIR / f"detail_{post_id}.json"


def load_existing_detail(post_id):
    path = detail_path(post_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload.get("Data") or None


def fetch_detail(post_id):
    existing = load_existing_detail(post_id)
    if existing:
        return "cached", existing
    payload = request_json(
        "ByPostId",
        {
            "timestamp": int(time.time() * 1000),
            "postId": post_id,
            "language": "zh-cn",
        },
    )
    detail_path(post_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return "fetched", payload.get("Data") or {}


def fetch_details(post_ids):
    details = []
    fetched = 0
    cached = 0
    errors = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch_detail, post_id): post_id for post_id in post_ids}
        total = len(futures)
        for index, future in enumerate(as_completed(futures), 1):
            post_id = futures[future]
            try:
                status, row = future.result()
                if row:
                    details.append(row)
                if status == "cached":
                    cached += 1
                else:
                    fetched += 1
            except Exception as exc:
                errors.append({"postId": post_id, "error": str(exc)})
            if index % 50 == 0 or index == total:
                print(f"[detail] done={index}/{total} fetched={fetched} cached={cached} errors={len(errors)}")
    if errors:
        (OUT_DIR / "detail_errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    return details, {"fetched": fetched, "cached": cached, "errors": len(errors)}


def write_outputs(details, fetched_at):
    jobs_path = DATA_DIR / "collected_jobs.csv"
    skills_path = DATA_DIR / "collected_job_skills.csv"
    sources_path = DATA_DIR / "collected_sources.csv"

    with jobs_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source",
                "postId",
                "title",
                "company",
                "bg",
                "product",
                "category",
                "country",
                "province",
                "city",
                "jobType",
                "workYears",
                "lastUpdateTime",
                "responsibility",
                "requirement",
                "skills",
                "sourceUrl",
                "fetchedAt",
            ],
        )
        writer.writeheader()
        for row in details:
            text = "\n".join([row.get("RecruitPostName", ""), row.get("Responsibility", ""), row.get("Requirement", "")])
            writer.writerow(
                {
                    "source": "Tencent Careers",
                    "postId": row.get("PostId", ""),
                    "title": clean(row.get("RecruitPostName", "")),
                    "company": clean(row.get("ComName", "")) or "Tencent",
                    "bg": clean(row.get("BGName", "")),
                    "product": clean(row.get("ProductName", "")),
                    "category": clean(row.get("CategoryName", "")),
                    "country": "China",
                    "province": "",
                    "city": clean(row.get("LocationName", "")),
                    "jobType": "full_time",
                    "workYears": clean(row.get("RequireWorkYearsName", "")),
                    "lastUpdateTime": clean(row.get("LastUpdateTime", "")),
                    "responsibility": clean(row.get("Responsibility", "")),
                    "requirement": clean(row.get("Requirement", "")),
                    "skills": "|".join(extract_skills(text)),
                    "sourceUrl": tencent_job_url(row),
                    "fetchedAt": fetched_at,
                }
            )

    with skills_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "postId", "title", "skill", "evidence", "sourceUrl", "fetchedAt"])
        writer.writeheader()
        for row in details:
            text = "\n".join([row.get("RecruitPostName", ""), row.get("Responsibility", ""), row.get("Requirement", "")])
            for skill in extract_skills(text):
                writer.writerow(
                    {
                        "source": "Tencent Careers",
                        "postId": row.get("PostId", ""),
                        "title": clean(row.get("RecruitPostName", "")),
                        "skill": skill,
                        "evidence": clean(text[:500]),
                        "sourceUrl": tencent_job_url(row),
                        "fetchedAt": fetched_at,
                    }
                )

    with sources_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "baseUrl", "licenseNote", "records", "fetchedAt"])
        writer.writeheader()
        writer.writerow(
            {
                "source": "Tencent Careers",
                "baseUrl": "https://careers.tencent.com/",
                "licenseNote": "Public Tencent Careers job pages/API; use only for project analysis and keep source attribution.",
                "records": len(details),
                "fetchedAt": fetched_at,
            }
        )

    return jobs_path, skills_path, sources_path


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    candidates, query_logs = collect_post_ids()
    details, detail_stats = fetch_details(list(candidates.keys()))
    jobs_path, skills_path, sources_path = write_outputs(details, fetched_at)

    manifest = {
        "fetchedAt": fetched_at,
        "source": "Tencent Careers",
        "keywords": KEYWORDS,
        "maxDetails": MAX_DETAILS,
        "mode": MODE,
        "workers": WORKERS,
        "queryLogs": query_logs,
        "detailStats": detail_stats,
        "records": len(details),
        "outputs": [str(jobs_path), str(skills_path), str(sources_path)],
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
