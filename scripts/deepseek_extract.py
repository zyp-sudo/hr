import csv
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ETL_JOBS_PATH = DATA_DIR / "etl" / "unified_jobs.csv"
AI_DIR = DATA_DIR / "ai"
OUTPUT_PATH = AI_DIR / "deepseek_extractions.jsonl"
MANIFEST_PATH = AI_DIR / "deepseek_manifest.json"


def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def rel(path):
    return path.relative_to(ROOT).as_posix()


def compact_text(value, limit=2400):
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value[:limit]


def dry_run_extract(row):
    skills = [item for item in row.get("normalized_skills", "").split("|") if item]
    role = row.get("job_title", "")
    dimensions = []
    for skill in skills:
        if skill in {"LLM", "RAG", "NLP", "Machine Learning", "Deep Learning", "Vector Search"}:
            dimensions.append("智能技术能力")
        elif skill in {"SQL", "Big Data", "Data Warehouse", "Redis"}:
            dimensions.append("数据能力")
        elif skill in {"Docker", "Kubernetes", "Linux", "DevOps"}:
            dimensions.append("基础设施能力")
        elif skill in {"Product", "Marketing", "Design"}:
            dimensions.append("业务与体验能力")
        else:
            dimensions.append("工程研发能力")
    dimensions = list(dict.fromkeys(dimensions))
    return {
        "role_name": role,
        "skills": skills,
        "capability_dimensions": dimensions,
        "relations": [
            {"head": role, "relation": "requires", "tail": skill, "confidence": 0.62}
            for skill in skills
        ],
        "quality_notes": ["dry_run_no_external_call"],
    }


def prompt_for(row):
    return f"""你是岗位能力知识图谱抽取器。请只返回 JSON，不要 Markdown。
字段要求：
- role_name: 规范岗位名称
- skills: 技能实体数组
- capability_dimensions: 能力维度数组
- relations: 三元组数组，每项包含 head, relation, tail, confidence
- quality_notes: 数据质量或歧义说明

岗位标题：{row.get("job_title", "")}
岗位类别：{row.get("normalized_category", "")}
已命中技能：{row.get("normalized_skills", "")}
岗位文本：{compact_text(row.get("raw_text", ""))}
"""


def call_deepseek(row, api_key, base_url, model):
    url = base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你负责从招聘 JD 中抽取岗位、技能、能力维度和关系，输出可入库 JSON。"},
            {"role": "user", "content": prompt_for(row)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def build():
    rows = read_csv(ETL_JOBS_PATH)
    max_records = int(os.environ.get("DEEPSEEK_MAX_RECORDS", "30"))
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    mode = "deepseek_api" if api_key else "dry_run"

    AI_DIR.mkdir(parents=True, exist_ok=True)
    success = 0
    failed = 0
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        for row in rows[:max_records]:
            status = "ok"
            error = ""
            try:
                result = call_deepseek(row, api_key, base_url, model) if api_key else dry_run_extract(row)
                success += 1
            except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, ValueError) as exc:
                status = "error"
                error = str(exc)
                result = dry_run_extract(row)
                failed += 1
            payload = {
                "record_id": row.get("record_id", ""),
                "source_id": row.get("source_id", ""),
                "job_title": row.get("job_title", ""),
                "provider": "deepseek" if api_key else "local_dry_run",
                "model": model if api_key else "rule_based",
                "mode": mode,
                "status": status,
                "error": error,
                "extracted_at": now_iso(),
                "result": result,
            }
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")

    manifest = {
        "generated_at": now_iso(),
        "mode": mode,
        "model": model if api_key else "rule_based",
        "input": rel(ETL_JOBS_PATH),
        "output": rel(OUTPUT_PATH),
        "requested_records": min(max_records, len(rows)),
        "success": success,
        "failed": failed,
        "notes": [
            "Set DEEPSEEK_API_KEY to call the real DeepSeek API.",
            "Without a key the script writes deterministic dry-run JSON so the pipeline remains runnable.",
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
