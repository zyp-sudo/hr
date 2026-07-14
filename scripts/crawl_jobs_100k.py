import csv
import hashlib
import html
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from etl_unify_jobs import extract_skills, normalize_text, source_id, transform


TARGET = int(os.environ.get("CHINA_JOB_TARGET", "100000"))
REQUEST_SLEEP = float(os.environ.get("CHINA_JOB_REQUEST_SLEEP", "0.5"))
RETRIES = int(os.environ.get("CHINA_JOB_RETRIES", "3"))
REGION_ORDER = os.environ.get("JOB_REGIONS", "china")
SOURCE_ORDER = os.environ.get("CHINA_JOB_SOURCES", "china")
ALLOW_FOREIGN_SOURCES = os.environ.get("ALLOW_FOREIGN_SOURCES", "0").strip().lower() in {"1", "true", "yes", "on"}
BALANCED_SOURCES = os.environ.get("CHINA_JOB_BALANCED", "1").strip().lower() not in {"0", "false", "no", "off"}
RESET_OUTPUTS = os.environ.get("CRAWL_RESET", "0").strip().lower() in {"1", "true", "yes", "on"}
USE_RAW_CACHE = os.environ.get("USE_RAW_CACHE", "0").strip().lower() in {"1", "true", "yes", "on"}

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "china_jobs"
IMPORT_DIR = DATA_DIR / "imports"
REPORT_PATH = DATA_DIR / "collection_report.json"
JOBS_PATH = DATA_DIR / "collected_jobs.csv"
SKILLS_PATH = DATA_DIR / "collected_job_skills.csv"
SOURCES_PATH = DATA_DIR / "collected_sources.csv"
SOURCE_TARGETS_PATH = DATA_DIR / "source_targets.csv"

JOB_FIELDS = [
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
]

CHINA_JOBS_PATH = DATA_DIR / "china_jobs.csv"
FOREIGN_JOBS_PATH = DATA_DIR / "foreign_jobs.csv"
COMPANY_TARGETS_PATH = DATA_DIR / "company_targets.csv"

SOURCE_CONFIGS = {
    "Tencent Careers": {
        "source_type": "official_enterprise_api",
        "base_url": "https://careers.tencent.com/",
        "license_note": "Public Tencent Careers job pages/API; keep source attribution.",
    },
    "ByteDance Careers": {
        "source_type": "official_enterprise_api",
        "base_url": "https://jobs.bytedance.com/",
        "license_note": "Official ByteDance careers public pages/API; keep source attribution.",
    },
    "Huawei Careers": {
        "source_type": "official_enterprise_api",
        "base_url": "https://career.huawei.com/reccampportal/",
        "license_note": "Official Huawei careers public pages/API; keep source attribution.",
    },
    "Baidu Careers": {
        "source_type": "official_enterprise_site",
        "base_url": "https://talent.baidu.com/jobs/",
        "license_note": "Official Baidu careers public pages; keep source attribution.",
    },
    "Meituan Careers": {
        "source_type": "official_enterprise_api",
        "base_url": "https://zhaopin.meituan.com/web/social",
        "license_note": "Official Meituan careers public pages/API; keep source attribution.",
    },
    "National College Student Employment Service": {
        "source_type": "public_employment_service",
        "base_url": "https://www.ncss.cn/student/jobs/index.html",
        "license_note": "Education-ministry public employment service pages/API; keep source attribution.",
    },
    "JobOnline Public Employment Service": {
        "source_type": "public_employment_service",
        "base_url": "https://www.jobonline.cn/",
        "license_note": "MOHRSS-organized public employment service platform; keep source attribution.",
    },
    "Alibaba Careers": {
        "source_type": "official_enterprise_site",
        "base_url": "https://talent.alibaba.com/",
        "license_note": "Official Alibaba careers public pages; keep source attribution.",
    },
    "NetEase Careers": {
        "source_type": "official_enterprise_site",
        "base_url": "https://hr.163.com/",
        "license_note": "Official NetEase careers public pages; keep source attribution.",
    },
    "Google Careers": {
        "source_type": "official_enterprise_site",
        "base_url": "https://www.google.com/about/careers/applications/jobs/results/",
        "license_note": "Official Google careers public pages; keep source attribution.",
    },
    "Apple Jobs": {
        "source_type": "official_enterprise_site",
        "base_url": "https://jobs.apple.com/",
        "license_note": "Official Apple jobs public pages; keep source attribution.",
    },
    "Remote OK": {
        "source_type": "remote_job_board_api",
        "base_url": "https://remoteok.com/api",
        "license_note": "Remote OK API requires source attribution and link-back to the job URL.",
    },
    "Arbeitnow": {
        "source_type": "public_job_board_api",
        "base_url": "https://www.arbeitnow.com/api/job-board-api",
        "license_note": "Public job board API; keep source URL attribution.",
    },
    "Greenhouse ATS": {
        "source_type": "ats_public_api",
        "base_url": "https://boards-api.greenhouse.io/v1/boards/",
        "license_note": "Public Greenhouse job board API; keep job URL attribution.",
    },
    "Lever ATS": {
        "source_type": "ats_public_api",
        "base_url": "https://api.lever.co/v0/postings/",
        "license_note": "Public Lever postings API; keep hosted job URL attribution.",
    },
    "Local Imported Dataset": {
        "source_type": "local_file_import",
        "base_url": "file://data/imports/",
        "license_note": "User-provided lawful CSV datasets.",
    },
}

DEFAULT_COMPANY_TARGETS = [
    {
        "region": "china",
        "adapter": "official_html",
        "source": "Alibaba Careers",
        "company": "Alibaba",
        "country": "China",
        "url": "https://talent.alibaba.com/",
    },
    {
        "region": "china",
        "adapter": "official_html",
        "source": "NetEase Careers",
        "company": "NetEase",
        "country": "China",
        "url": "https://hr.163.com/",
    },
    {
        "region": "foreign",
        "adapter": "official_html",
        "source": "Google Careers",
        "company": "Google",
        "country": "United States",
        "url": "https://www.google.com/about/careers/applications/jobs/results/",
    },
    {
        "region": "foreign",
        "adapter": "official_html",
        "source": "Apple Jobs",
        "company": "Apple",
        "country": "United States",
        "url": "https://jobs.apple.com/en-us/search",
    },
]

DEFAULT_GREENHOUSE_BOARDS = [
    "airbnb",
    "anthropic",
    "asana",
    "cloudflare",
    "coinbase",
    "databricks",
    "discord",
    "doordashusa",
    "figma",
    "notion",
    "reddit",
    "roblox",
    "ripple",
    "scaleai",
    "stripe",
]

DEFAULT_LEVER_COMPANIES = [
    "benchling",
    "chime",
    "coursera",
    "duolingo",
    "hashicorp",
    "postman",
    "scaleai",
    "segment",
    "zapier",
]


def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def env_enabled(name, default=True):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def adapter_registry():
    return {
        "china": ("China Companies", china_company_rows),
        "cn": ("China Companies", china_company_rows),
        "baidu": ("Baidu Careers", baidu_rows),
        "baidu_careers": ("Baidu Careers", baidu_rows),
        "huawei": ("Huawei Careers", huawei_rows),
        "huawei_careers": ("Huawei Careers", huawei_rows),
        "meituan": ("Meituan Careers", meituan_rows),
        "meituan_careers": ("Meituan Careers", meituan_rows),
        "ncss": ("National College Student Employment Service", ncss_rows),
        "public_employment": ("National College Student Employment Service", ncss_rows),
        "national_college_student_employment": ("National College Student Employment Service", ncss_rows),
        "jobonline": ("JobOnline Public Employment Service", jobonline_rows),
        "jobonline_public": ("JobOnline Public Employment Service", jobonline_rows),
        "public_employment_service": ("JobOnline Public Employment Service", jobonline_rows),
        "foreign": ("Foreign Companies", foreign_company_rows),
        "global": ("Foreign Companies", foreign_company_rows),
        "greenhouse": ("Greenhouse ATS", greenhouse_rows),
        "greenhouse_ats": ("Greenhouse ATS", greenhouse_rows),
        "lever": ("Lever ATS", lever_rows),
        "lever_ats": ("Lever ATS", lever_rows),
        "tencent": ("Tencent Careers", run_tencent_crawler),
        "tencent_careers": ("Tencent Careers", run_tencent_crawler),
        "remoteok": ("Remote OK", remoteok_rows),
        "remote_ok": ("Remote OK", remoteok_rows),
        "arbeitnow": ("Arbeitnow", arbeitnow_rows),
        "imports": ("Local Imported Dataset", local_import_rows),
        "local": ("Local Imported Dataset", local_import_rows),
        "local_import_dataset": ("Local Imported Dataset", local_import_rows),
    }


def selected_adapters():
    registry = adapter_registry()
    requested = [item.strip().lower() for item in SOURCE_ORDER.split(",") if item.strip()]
    if not requested or "all" in requested:
        requested = ["china"]
    adapters = []
    seen = set()
    foreign_keys = {
        "foreign",
        "global",
        "greenhouse",
        "greenhouse_ats",
        "lever",
        "lever_ats",
        "remoteok",
        "remote_ok",
        "arbeitnow",
    }
    for key in requested:
        if key in foreign_keys and not ALLOW_FOREIGN_SOURCES:
            print(json.dumps({
                "stage": "source_skipped",
                "source": key,
                "reason": "foreign_sources_disabled",
                "enable_with": "ALLOW_FOREIGN_SOURCES=1",
            }, ensure_ascii=False))
            continue
        if key not in registry:
            print(json.dumps({"stage": "source_skipped", "source": key, "reason": "unknown_source_key"}, ensure_ascii=False))
            continue
        name, adapter = registry[key]
        if name in seen:
            continue
        adapters.append((name, adapter))
        seen.add(name)
    return adapters


def request_json(url, cache_path=None):
    if USE_RAW_CACHE and cache_path and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    headers = {
        "Accept": "application/json,text/plain,*/*",
        "User-Agent": "XH-202621 job ETL pipeline; contact: local research project",
    }
    req = urllib.request.Request(url, headers=headers)
    last_error = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(min(5, 0.5 * attempt))
    if cache_path and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    raise RuntimeError(f"request failed after {RETRIES} retries: {url}") from last_error


def request_json_post(url, payload, cache_path=None, extra_headers=None):
    if USE_RAW_CACHE and cache_path and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    headers = {
        "Accept": "application/json,text/plain,*/*",
        "Content-Type": "application/json",
        "User-Agent": "XH-202621 job ETL pipeline; contact: local research project",
    }
    if extra_headers:
        headers.update(extra_headers)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    last_error = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(min(5, 0.5 * attempt))
    if cache_path and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    raise RuntimeError(f"request failed after {RETRIES} retries: {url}") from last_error


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


def split_env_list(name):
    value = os.environ.get(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def source_targets(kind, defaults):
    env_name = f"{kind.upper()}_TARGETS"
    targets = split_env_list(env_name)
    for row in read_csv(SOURCE_TARGETS_PATH):
        if row.get("sourceType", "").strip().lower() != kind.lower():
            continue
        token = row.get("token", "").strip()
        enabled = row.get("enabled", "1").strip().lower()
        if token and enabled not in {"0", "false", "no", "off"}:
            targets.append(token)
    seen = []
    for item in targets or defaults:
        if item not in seen:
            seen.append(item)
    return seen


def company_targets(region):
    rows = []
    for item in DEFAULT_COMPANY_TARGETS:
        if item["region"].lower() == region.lower():
            rows.append(dict(item))
    for row in read_csv(COMPANY_TARGETS_PATH):
        enabled = row.get("enabled", "1").strip().lower()
        if enabled in {"0", "false", "no", "off"}:
            continue
        if row.get("region", "").strip().lower() != region.lower():
            continue
        rows.append({
            "region": row.get("region", "").strip().lower(),
            "adapter": row.get("adapter", "official_html").strip().lower(),
            "source": row.get("source", "").strip(),
            "company": row.get("company", "").strip(),
            "country": row.get("country", "").strip() or ("China" if region.lower() == "china" else ""),
            "url": row.get("url", "").strip(),
        })
    deduped = []
    seen = set()
    for item in rows:
        key = (item.get("source", ""), item.get("url", ""))
        if item.get("source") and item.get("url") and key not in seen:
            deduped.append(item)
            seen.add(key)
    return deduped


def request_text(url, cache_path=None):
    if USE_RAW_CACHE and cache_path and cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="replace")
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": "XH-202621 job ETL pipeline; contact: local research project",
    }
    req = urllib.request.Request(url, headers=headers)
    last_error = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                text = response.read().decode("utf-8", errors="replace")
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(text, encoding="utf-8")
            return text
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(min(5, 0.5 * attempt))
    if cache_path and cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="replace")
    raise RuntimeError(f"request failed after {RETRIES} retries: {url}") from last_error


def join_text(parts):
    return normalize_text(" ".join(str(part or "") for part in parts))


def split_description(text):
    text = normalize_text(text)
    if len(text) <= 1400:
        return text, ""
    return text[:1400], text[1400:2800]


def millis_to_iso(value):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return normalize_text(value)
    if number <= 0:
        return ""
    if number > 10_000_000_000:
        number = number / 1000
    return datetime.fromtimestamp(number, timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def extract_city_parts(location):
    text = normalize_text(location)
    if not text:
        return "", ""
    text = text.replace("China\\", "").replace("中国/", "").replace("中国\\", "")
    text = text.split(";")[0].split(",")[0]
    text = text.replace("-", "/")
    parts = [part for part in re.split(r"[/\s]+", text) if part]
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "", parts[0]


def generic_china_job_row(source, item, *, company, post_id, title, category="", city="", province="", job_type="",
                          work_years="", updated_at="", responsibility="", requirement="", source_url="",
                          bg="", product="", fetched_at=None):
    text = join_text([title, company, category, bg, product, responsibility, requirement])
    return {
        "source": source,
        "postId": normalize_text(post_id),
        "title": normalize_text(title),
        "company": normalize_text(company),
        "bg": normalize_text(bg),
        "product": normalize_text(product),
        "category": normalize_text(category),
        "country": "China",
        "province": normalize_text(province),
        "city": normalize_text(city),
        "jobType": normalize_text(job_type),
        "workYears": normalize_text(work_years),
        "lastUpdateTime": normalize_text(updated_at),
        "responsibility": normalize_text(responsibility),
        "requirement": normalize_text(requirement),
        "skills": "|".join(extract_skills(text)),
        "sourceUrl": normalize_text(source_url),
        "fetchedAt": fetched_at or now_iso(),
    }


def html_job_links(html_text, base_url):
    links = []
    seen = set()
    patterns = [
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        r'"url"\s*:\s*"([^"]+)"[^{}]{0,250}"title"\s*:\s*"([^"]+)"',
        r'"title"\s*:\s*"([^"]+)"[^{}]{0,250}"url"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html_text, flags=re.I | re.S):
            first = html.unescape(match.group(1))
            second = html.unescape(match.group(2))
            if first.startswith("http") or "/" in first:
                href, title = first, second
            else:
                title, href = first, second
            title = normalize_text(re.sub(r"<[^>]+>", " ", title))
            href = normalize_text(href).replace("\\u002F", "/")
            if not href:
                continue
            url = urllib.parse.urljoin(base_url, href)
            probe = f"{title} {url}".lower()
            if not any(word in probe for word in ["job", "career", "position", "opening", "岗位", "职位", "招聘", "apply"]):
                continue
            if not title or len(title) > 160:
                tail = urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]
                title = normalize_text(tail.replace("-", " ").replace("_", " "))
            key = (title.lower(), url)
            if title and key not in seen:
                links.append((title, url))
                seen.add(key)
    return links


def official_html_rows(region, limit):
    if not env_enabled("ENABLE_OFFICIAL_HTML", True) or limit <= 0:
        return []
    rows = []
    fetched_at = now_iso()
    for target in company_targets(region):
        if len(rows) >= limit:
            break
        source_name = target["source"]
        company = target["company"]
        url = target["url"]
        country = target.get("country") or ("China" if region == "china" else "")
        cache_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{region}_{company}")[:80] or region
        try:
            html_text = request_text(url, RAW_DIR / "official_html" / f"{cache_name}.html")
        except Exception as exc:
            print(json.dumps({"stage": "source_target_error", "source": source_name, "target": url, "error": str(exc)}, ensure_ascii=False))
            continue
        links = html_job_links(html_text, url)
        if not links:
            print(json.dumps({"stage": "source_target_empty", "source": source_name, "target": url, "reason": "no_job_links_found"}, ensure_ascii=False))
        for index, (title, job_url) in enumerate(links, start=1):
            text = join_text([title, company, source_name])
            rows.append({
                "source": source_name,
                "postId": f"{company}:{index}:{hashlib.sha1(job_url.encode('utf-8')).hexdigest()[:12]}",
                "title": title,
                "company": company,
                "bg": "",
                "product": "",
                "category": "official_careers",
                "country": country,
                "province": "",
                "city": "",
                "jobType": "",
                "workYears": "",
                "lastUpdateTime": "",
                "responsibility": f"Official careers listing extracted from {url}.",
                "requirement": "",
                "skills": "|".join(extract_skills(text)),
                "sourceUrl": job_url,
                "fetchedAt": fetched_at,
            })
            if len(rows) >= limit:
                break
        time.sleep(REQUEST_SLEEP)
    return rows


def greenhouse_rows(limit):
    if not env_enabled("ENABLE_GREENHOUSE", True) or limit <= 0:
        return []
    rows = []
    fetched_at = now_iso()
    boards = source_targets("greenhouse", DEFAULT_GREENHOUSE_BOARDS)
    for board in boards:
        if len(rows) >= limit:
            break
        url = f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(board)}/jobs?content=true"
        try:
            payload = request_json(url, RAW_DIR / "greenhouse" / f"{board}.json")
        except Exception as exc:
            print(json.dumps({"stage": "source_target_error", "source": "Greenhouse ATS", "target": board, "error": str(exc)}, ensure_ascii=False))
            continue
        for item in payload.get("jobs") or []:
            departments = item.get("departments") or []
            offices = item.get("offices") or []
            location = item.get("location") or {}
            city = normalize_text(location.get("name", ""))
            category = "|".join(normalize_text(dep.get("name", "")) for dep in departments if dep.get("name"))
            office_text = "|".join(normalize_text(office.get("name", "")) for office in offices if office.get("name"))
            description = normalize_text(item.get("content", ""))
            responsibility, requirement = split_description(description)
            text = join_text([item.get("title", ""), category, office_text, description])
            rows.append({
                "source": "Greenhouse ATS",
                "postId": f"{board}:{item.get('id', '')}",
                "title": normalize_text(item.get("title", "")),
                "company": board,
                "bg": category,
                "product": "",
                "category": category or office_text,
                "country": "",
                "province": "",
                "city": city,
                "jobType": "",
                "workYears": "",
                "lastUpdateTime": normalize_text(item.get("updated_at", "")),
                "responsibility": responsibility,
                "requirement": requirement,
                "skills": "|".join(extract_skills(text)),
                "sourceUrl": normalize_text(item.get("absolute_url", "")),
                "fetchedAt": fetched_at,
            })
            if len(rows) >= limit:
                break
        time.sleep(REQUEST_SLEEP)
    return rows


def lever_rows(limit):
    if not env_enabled("ENABLE_LEVER", True) or limit <= 0:
        return []
    rows = []
    fetched_at = now_iso()
    companies = source_targets("lever", DEFAULT_LEVER_COMPANIES)
    for company in companies:
        if len(rows) >= limit:
            break
        url = f"https://api.lever.co/v0/postings/{urllib.parse.quote(company)}?mode=json"
        try:
            payload = request_json(url, RAW_DIR / "lever" / f"{company}.json")
        except Exception as exc:
            print(json.dumps({"stage": "source_target_error", "source": "Lever ATS", "target": company, "error": str(exc)}, ensure_ascii=False))
            continue
        for item in payload if isinstance(payload, list) else []:
            categories = item.get("categories") or {}
            lists = item.get("lists") or []
            list_text = " ".join(join_text([entry.get("text", ""), entry.get("content", "")]) for entry in lists if isinstance(entry, dict))
            description = join_text([
                item.get("descriptionPlain") or item.get("description", ""),
                item.get("additionalPlain") or item.get("additional", ""),
                list_text,
            ])
            responsibility, requirement = split_description(description)
            title = normalize_text(item.get("text", ""))
            team = normalize_text(categories.get("team", ""))
            commitment = normalize_text(categories.get("commitment", ""))
            location = normalize_text(categories.get("location", ""))
            created_at = item.get("createdAt", "")
            if isinstance(created_at, int):
                published_at = datetime.fromtimestamp(created_at / 1000, timezone.utc).isoformat(timespec="seconds")
            else:
                published_at = normalize_text(created_at)
            text = join_text([title, team, commitment, location, description])
            rows.append({
                "source": "Lever ATS",
                "postId": f"{company}:{item.get('id', '')}",
                "title": title,
                "company": company,
                "bg": team,
                "product": "",
                "category": commitment or team,
                "country": "",
                "province": "",
                "city": location,
                "jobType": commitment,
                "workYears": "",
                "lastUpdateTime": published_at,
                "responsibility": responsibility,
                "requirement": requirement,
                "skills": "|".join(extract_skills(text)),
                "sourceUrl": normalize_text(item.get("hostedUrl") or item.get("applyUrl", "")),
                "fetchedAt": fetched_at,
            })
            if len(rows) >= limit:
                break
        time.sleep(REQUEST_SLEEP)
    return rows


def meituan_rows(limit):
    if not env_enabled("ENABLE_MEITUAN", True) or limit <= 0:
        return []
    rows = []
    fetched_at = now_iso()
    url = "https://zhaopin.meituan.com/api/official/job/getJobList"
    max_pages = int(os.environ.get("MEITUAN_MAX_PAGES", "200"))
    page_size = min(100, max(1, int(os.environ.get("MEITUAN_PAGE_SIZE", "100"))))
    for page_no in range(1, max_pages + 1):
        if len(rows) >= limit:
            break
        payload = {
            "page": {"pageNo": page_no, "pageSize": page_size},
            "jobShareType": "1",
            "keywords": "",
            "cityList": [],
            "department": [],
            "jfJgList": [],
            "jobType": [{"code": "3", "subCode": []}],
            "typeCode": [],
            "specialCode": [],
        }
        data = request_json_post(
            url,
            payload,
            RAW_DIR / "meituan" / f"page_{page_no}.json",
            {"Referer": "https://zhaopin.meituan.com/web/social", "Origin": "https://zhaopin.meituan.com"},
        )
        body = data.get("data") or {}
        items = body.get("list") or []
        if not items:
            break
        for item in items:
            city_names = [entry.get("name", "") for entry in item.get("cityList") or [] if isinstance(entry, dict)]
            dept_names = [entry.get("name", "") for entry in item.get("department") or [] if isinstance(entry, dict)]
            city = "|".join(city_names)
            category = item.get("jobFamily") or item.get("jobFamilyGroup") or ""
            responsibility = item.get("jobDuty") or item.get("desc") or ""
            requirement = item.get("jobRequirement") or item.get("highLight") or item.get("otherInfo") or ""
            updated_at = millis_to_iso(item.get("firstPostTime") or item.get("refreshTime"))
            source_url = f"https://zhaopin.meituan.com/web/position/detail?jobUnionId={item.get('jobUnionId', '')}"
            rows.append(generic_china_job_row(
                "Meituan Careers",
                item,
                company="Meituan",
                post_id=item.get("jobUnionId", ""),
                title=item.get("name", ""),
                category=category,
                city=city,
                job_type=item.get("jobType", ""),
                work_years=item.get("workYear", ""),
                updated_at=updated_at,
                responsibility=responsibility,
                requirement=requirement,
                source_url=source_url,
                bg="|".join(dept_names),
                fetched_at=fetched_at,
            ))
            if len(rows) >= limit:
                break
        page = body.get("page") or {}
        if page.get("totalPage") and page_no >= int(page.get("totalPage")):
            break
        time.sleep(REQUEST_SLEEP)
    return rows


def huawei_rows(limit):
    if not env_enabled("ENABLE_HUAWEI", True) or limit <= 0:
        return []
    rows = []
    fetched_at = now_iso()
    page_size = min(100, max(1, int(os.environ.get("HUAWEI_PAGE_SIZE", "100"))))
    max_pages = int(os.environ.get("HUAWEI_MAX_PAGES", "100"))
    for page_no in range(1, max_pages + 1):
        if len(rows) >= limit:
            break
        query = urllib.parse.urlencode({
            "jobType": "1",
            "orderBy": "P_COUNT_DESC",
            "language": "zh_CN",
            "reqTime": int(time.time() * 1000),
        })
        url = f"https://career.huawei.com/reccampportal/services/portal/portalpub/getJob/newHr/page/{page_size}/{page_no}?{query}"
        data = request_json(url, RAW_DIR / "huawei" / f"page_{page_no}.json")
        items = data.get("result") or []
        if not items:
            break
        for item in items:
            province, city = extract_city_parts(item.get("jobArea") or item.get("jobAddress", ""))
            title = item.get("jobname") or item.get("nameCn") or item.get("externalJobName") or ""
            source_url = (
                "https://career.huawei.com/reccampportal/portal5/social-recruitment-detail.html?"
                f"jobId={item.get('jobId', '')}&dataSource={item.get('dataSource', '')}"
            )
            rows.append(generic_china_job_row(
                "Huawei Careers",
                item,
                company="Huawei",
                post_id=item.get("positionReqCode") or item.get("advertisementCode") or item.get("jobId", ""),
                title=title,
                category=item.get("jobFamilyName") or item.get("categoryName") or "",
                province=province,
                city=city,
                job_type=item.get("jobType", ""),
                work_years=item.get("workYear", ""),
                updated_at=item.get("releaseDate") or item.get("creationDate") or "",
                responsibility=item.get("mainBusiness", ""),
                requirement=item.get("jobRequire", ""),
                source_url=source_url,
                bg=item.get("deptName", ""),
                fetched_at=fetched_at,
            ))
            if len(rows) >= limit:
                break
        page = data.get("pageVO") or {}
        if page.get("totalPages") and page_no >= int(page.get("totalPages")):
            break
        time.sleep(REQUEST_SLEEP)
    return rows


def extract_json_array_after(text, marker):
    idx = text.find(marker)
    if idx < 0:
        return []
    start = text.find("[", idx)
    if start < 0:
        return []
    depth = 0
    in_string = False
    escaped = False
    for pos in range(start, len(text)):
        char = text[pos]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                snippet = text[start:pos + 1]
                snippet = snippet.replace("undefined", "null")
                return json.loads(snippet)
    return []


def baidu_rows(limit):
    if not env_enabled("ENABLE_BAIDU", True) or limit <= 0:
        return []
    rows = []
    fetched_at = now_iso()
    page_size = 10
    max_pages = int(os.environ.get("BAIDU_MAX_PAGES", "200"))
    for page_no in range(1, max_pages + 1):
        if len(rows) >= limit:
            break
        url = f"https://talent.baidu.com/jobs/social-list?pageNum={page_no}&pageSize={page_size}"
        text = request_text(url, RAW_DIR / "baidu" / f"social_page_{page_no}.html")
        items = extract_json_array_after(text, '"listDetailData"') or extract_json_array_after(text, '"jobList"')
        if not items:
            break
        seen_before = len(rows)
        for item in items:
            source_url = f"https://talent.baidu.com/jobs/detail/{item.get('postId') or item.get('jobId') or ''}"
            rows.append(generic_china_job_row(
                "Baidu Careers",
                item,
                company="Baidu",
                post_id=item.get("postId") or item.get("jobId") or "",
                title=item.get("name", ""),
                category=item.get("postType", ""),
                city=item.get("workPlace", ""),
                job_type=item.get("projectType") or item.get("recruitType") or "",
                work_years=item.get("workYears", ""),
                updated_at=item.get("updateDate") or item.get("publishDate") or "",
                responsibility=item.get("workContent", ""),
                requirement=item.get("serviceCondition", ""),
                source_url=source_url,
                bg=item.get("bgShortName", ""),
                fetched_at=fetched_at,
            ))
            if len(rows) >= limit:
                break
        if len(rows) == seen_before or len(items) < page_size:
            break
        time.sleep(REQUEST_SLEEP)
    return rows


def ncss_rows(limit):
    if not env_enabled("ENABLE_NCSS", True) or limit <= 0:
        return []
    rows = []
    fetched_at = now_iso()
    page_size = 20
    max_pages = int(os.environ.get("NCSS_MAX_PAGES", "2000"))
    for page_no in range(1, max_pages + 1):
        if len(rows) >= limit:
            break
        query = urllib.parse.urlencode({"offset": page_no, "limit": page_size})
        url = f"https://www.ncss.cn/student/jobs/jobslist/ajax/?{query}"
        data = request_json(url, RAW_DIR / "ncss" / f"page_{page_no}.json")
        body = data.get("data") or {}
        items = body.get("list") or []
        if not items:
            break
        for item in items:
            tags = item.get("recTags") or ""
            salary = ""
            if item.get("lowMonthPay") or item.get("highMonthPay"):
                salary = f"{item.get('lowMonthPay', '')}-{item.get('highMonthPay', '')}K/月"
            requirement = join_text([item.get("degreeName", ""), item.get("major", ""), tags, salary])
            source_name = item.get("sourcesNameCh") or "国家大学生就业服务平台"
            source_url = f"https://www.ncss.cn/student/jobs/{item.get('jobId', '')}/detail.html"
            rows.append(generic_china_job_row(
                "National College Student Employment Service",
                item,
                company=item.get("recName", ""),
                post_id=item.get("jobId", ""),
                title=item.get("jobName", ""),
                category=item.get("recProperty") or source_name,
                city=item.get("areaCodeName", ""),
                job_type=item.get("recruitType", ""),
                updated_at=millis_to_iso(item.get("updateDate") or item.get("publishDate")),
                responsibility=join_text([item.get("jobName", ""), f"招聘人数: {item.get('headCount', '')}"]),
                requirement=requirement,
                source_url=source_url,
                bg=item.get("recScale", ""),
                fetched_at=fetched_at,
            ))
            if len(rows) >= limit:
                break
        page = body.get("pagenation") or {}
        total_pages = int(page.get("total") or 0)
        if total_pages and page_no >= total_pages:
            break
        time.sleep(REQUEST_SLEEP)
    return rows


def jobonline_rows(limit):
    if not env_enabled("ENABLE_JOBONLINE", True) or limit <= 0:
        return []
    raw_dir = RAW_DIR / "jobonline"
    output_path = raw_dir / "jobonline_batch.json"
    env = os.environ.copy()
    env.update({
        "JOBONLINE_TARGET": str(limit),
        "JOBONLINE_RAW_DIR": str(raw_dir),
        "JOBONLINE_OUTPUT": str(output_path),
        "USE_RAW_CACHE": "1" if USE_RAW_CACHE else "0",
        "JOBONLINE_PAGE_SIZE": os.environ.get("JOBONLINE_PAGE_SIZE", "40"),
        "JOBONLINE_SLEEP_MS": os.environ.get("JOBONLINE_SLEEP_MS", "40"),
        "JOBONLINE_MAX_PAGES_PER_SHARD": os.environ.get("JOBONLINE_MAX_PAGES_PER_SHARD", "250"),
    })
    completed = subprocess.run(
        ["node", "scripts/jobonline_client.js"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    if completed.stdout:
        for line in completed.stdout.splitlines()[-10:]:
            print(line)
    if completed.returncode != 0:
        message = completed.stderr.strip() or "jobonline client failed"
        raise RuntimeError(message)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    rows = []
    fetched_at = now_iso()
    for item in payload.get("rows", []):
        salary = ""
        low_salary = item.get("lowSalary") or item.get("lowSalaryOrigin") or ""
        high_salary = item.get("highSalary") or item.get("highSalaryOrigin") or ""
        salary_unit = item.get("salaryUnitName") or ""
        if low_salary or high_salary:
            salary = f"{low_salary}-{high_salary}{salary_unit}"
        location = join_text([item.get("provinceName", ""), item.get("cityName", ""), item.get("areaName", "")])
        requirement = join_text([
            item.get("eduDegree", ""),
            item.get("jobAge", ""),
            salary,
            item.get("industryName", ""),
            item.get("nature", ""),
            item.get("size", ""),
            item.get("category", ""),
        ])
        responsibility = join_text([
            item.get("positionName", ""),
            item.get("address", ""),
            f"headcount: {item.get('num', '')}" if item.get("num") else "",
            f"channel: {item.get('channelNumber', '')}" if item.get("channelNumber") else "",
        ])
        post_id = item.get("id", "")
        source_url = f"https://www.jobonline.cn/position?positionId={post_id}"
        rows.append(generic_china_job_row(
            "JobOnline Public Employment Service",
            item,
            company=item.get("companyName") or item.get("aliasName") or item.get("name") or "",
            post_id=post_id,
            title=item.get("positionName", ""),
            category=item.get("positionCode3") or item.get("industryName") or item.get("category") or "",
            province=item.get("provinceName", ""),
            city=location,
            job_type=item.get("category", ""),
            work_years=item.get("jobAge", ""),
            updated_at=millis_to_iso(item.get("publishTime") or item.get("createTimeP")),
            responsibility=responsibility,
            requirement=requirement,
            source_url=source_url,
            bg=item.get("industryName", ""),
            product=item.get("channelNumberOrigin", ""),
            fetched_at=fetched_at,
        ))
        if len(rows) >= limit:
            break
    return rows


def run_tencent_crawler(limit):
    if not env_enabled("ENABLE_TENCENT", True) or limit <= 0:
        return []
    env = os.environ.copy()
    env.update({
        "TENCENT_JOB_MODE": os.environ.get("TENCENT_JOB_MODE", "all"),
        "TENCENT_JOB_MAX": str(limit),
        "TENCENT_JOB_WORKERS": os.environ.get("TENCENT_JOB_WORKERS", "32"),
        "TENCENT_JOB_PAGE_SIZE": os.environ.get("TENCENT_JOB_PAGE_SIZE", "20"),
    })
    completed = subprocess.run(
        [sys.executable, "scripts/crawl_tencent_jobs.py"],
        cwd=ROOT,
        env=env,
        text=True,
    )
    if completed.returncode != 0:
        print(f"[warn] Tencent crawler failed with exit code {completed.returncode}; using existing CSV if present.")
    rows = [row for row in read_csv(JOBS_PATH) if row.get("source") == "Tencent Careers"]
    for row in rows:
        row["company"] = row.get("company") or "Tencent"
        row["country"] = row.get("country") or "China"
        row["province"] = row.get("province") or ""
        row["jobType"] = row.get("jobType") or "full_time"
        row["sourceUrl"] = row.get("sourceUrl") or f"http://careers.tencent.com/jobdesc.html?postId={row.get('postId', '')}"
    return rows[:limit]


def china_company_rows(limit):
    rows = []
    if limit <= 0:
        return rows
    tencent_limit = min(limit, int(os.environ.get("CHINA_TENCENT_LIMIT", str(limit))))
    rows.extend(run_tencent_crawler(tencent_limit))
    remaining = max(0, limit - len(rows))
    rows.extend(meituan_rows(remaining))
    remaining = max(0, limit - len(rows))
    rows.extend(huawei_rows(remaining))
    remaining = max(0, limit - len(rows))
    rows.extend(baidu_rows(remaining))
    remaining = max(0, limit - len(rows))
    rows.extend(ncss_rows(remaining))
    remaining = max(0, limit - len(rows))
    rows.extend(jobonline_rows(remaining))
    remaining = max(0, limit - len(rows))
    rows.extend(official_html_rows("china", remaining))
    return rows[:limit]


def foreign_company_rows(limit):
    rows = []
    if limit <= 0:
        return rows
    official_limit = min(limit, int(os.environ.get("FOREIGN_OFFICIAL_LIMIT", str(limit))))
    rows.extend(official_html_rows("foreign", official_limit))
    remaining = max(0, limit - len(rows))
    if remaining > 0:
        rows.extend(greenhouse_rows(remaining))
    remaining = max(0, limit - len(rows))
    if remaining > 0:
        rows.extend(lever_rows(remaining))
    remaining = max(0, limit - len(rows))
    if remaining > 0:
        rows.extend(remoteok_rows(remaining))
    remaining = max(0, limit - len(rows))
    if remaining > 0:
        rows.extend(arbeitnow_rows(remaining))
    return rows[:limit]


def remoteok_rows(limit):
    if not env_enabled("ENABLE_REMOTEOK", True) or limit <= 0:
        return []
    payload = request_json(
        "https://remoteok.com/api",
        RAW_DIR / "remoteok" / "remoteok_api.json",
    )
    rows = []
    fetched_at = now_iso()
    for item in payload:
        if not isinstance(item, dict) or item.get("legal"):
            continue
        description = normalize_text(item.get("description", ""))
        tags = item.get("tags") or []
        if isinstance(tags, list):
            category = "|".join(str(tag) for tag in tags)
        else:
            category = normalize_text(tags)
        text = " ".join([item.get("position", ""), category, description])
        skills = extract_skills(text)
        rows.append({
            "source": "Remote OK",
            "postId": str(item.get("id") or item.get("slug") or ""),
            "title": normalize_text(item.get("position", "")),
            "company": normalize_text(item.get("company", "")),
            "bg": "",
            "product": "",
            "category": category,
            "country": "",
            "province": "",
            "city": normalize_text(item.get("location", "")) or "Remote",
            "jobType": "remote",
            "workYears": "",
            "lastUpdateTime": normalize_text(item.get("date", "")),
            "responsibility": description[:1200],
            "requirement": description[1200:2400],
            "skills": "|".join(skills),
            "sourceUrl": normalize_text(item.get("url") or item.get("apply_url", "")),
            "fetchedAt": fetched_at,
        })
        if len(rows) >= limit:
            break
    return rows


def arbeitnow_rows(limit):
    if not env_enabled("ENABLE_ARBEITNOW", True) or limit <= 0:
        return []
    rows = []
    fetched_at = now_iso()
    max_pages = int(os.environ.get("ARBEITNOW_MAX_PAGES", "2000"))
    for page in range(1, max_pages + 1):
        if len(rows) >= limit:
            break
        query = urllib.parse.urlencode({"page": page})
        payload = request_json(
            f"https://www.arbeitnow.com/api/job-board-api?{query}",
            RAW_DIR / "arbeitnow" / f"page_{page}.json",
        )
        items = payload.get("data") or []
        if not items:
            break
        for item in items:
            description = normalize_text(item.get("description", ""))
            tags = item.get("tags") or []
            category = "|".join(str(tag) for tag in tags) if isinstance(tags, list) else normalize_text(tags)
            job_types = item.get("job_types") or []
            text = " ".join([item.get("title", ""), category, description])
            created_at = item.get("created_at", "")
            if isinstance(created_at, int):
                published_at = datetime.fromtimestamp(created_at, timezone.utc).isoformat(timespec="seconds")
            else:
                published_at = normalize_text(created_at)
            rows.append({
                "source": "Arbeitnow",
                "postId": normalize_text(item.get("slug", "")),
                "title": normalize_text(item.get("title", "")),
                "company": normalize_text(item.get("company_name", "")),
                "bg": "",
                "product": "",
                "category": category,
                "country": "",
                "province": "",
                "city": normalize_text(item.get("location", "")),
                "jobType": "|".join(str(job_type) for job_type in job_types),
                "workYears": "",
                "lastUpdateTime": published_at,
                "responsibility": description[:1200],
                "requirement": description[1200:2400],
                "skills": "|".join(extract_skills(text)),
                "sourceUrl": normalize_text(item.get("url", "")),
                "fetchedAt": fetched_at,
            })
            if len(rows) >= limit:
                break
        time.sleep(REQUEST_SLEEP)
    return rows


def local_import_rows(limit):
    if not env_enabled("ENABLE_IMPORTS", True) or limit <= 0:
        return []
    rows = []
    fetched_at = now_iso()
    for path in sorted(IMPORT_DIR.glob("*.csv")):
        for item in read_csv(path):
            text = " ".join([
                item.get("title", ""),
                item.get("job_title", ""),
                item.get("description", ""),
                item.get("responsibility", ""),
                item.get("requirement", ""),
                item.get("requirements", ""),
                item.get("skills", ""),
            ])
            source_name = item.get("source") or item.get("source_name") or "Local Imported Dataset"
            rows.append({
                "source": source_name,
                "postId": item.get("postId") or item.get("post_id") or item.get("id") or f"{path.stem}:{len(rows) + 1}",
                "title": item.get("title") or item.get("job_title") or item.get("position") or "",
                "company": item.get("company") or item.get("company_name") or "",
                "bg": item.get("bg") or item.get("department") or "",
                "product": item.get("product") or "",
                "category": item.get("category") or item.get("tags") or "",
                "country": item.get("country") or "",
                "province": item.get("province") or item.get("state") or item.get("region") or "",
                "city": item.get("city") or item.get("location") or "",
                "jobType": item.get("jobType") or item.get("job_type") or item.get("employment_type") or "",
                "workYears": item.get("workYears") or item.get("work_years") or "",
                "lastUpdateTime": item.get("lastUpdateTime") or item.get("published_at") or item.get("date") or "",
                "responsibility": item.get("responsibility") or item.get("description") or "",
                "requirement": item.get("requirement") or item.get("requirements") or "",
                "skills": item.get("skills") or "|".join(extract_skills(text)),
                "sourceUrl": item.get("sourceUrl") or item.get("source_url") or item.get("url") or "",
                "fetchedAt": item.get("fetchedAt") or item.get("collected_at") or fetched_at,
            })
            if len(rows) >= limit:
                return rows
    return rows


def dedupe(rows):
    result = []
    seen_ids = set()
    seen_content = set()
    for row in rows:
        sid = source_id(row.get("source", ""))
        origin = row.get("postId") or ""
        id_key = (sid, origin)
        content_key = "|".join([
            normalize_text(row.get("title", "")).lower(),
            normalize_text(row.get("company", "")).lower(),
            normalize_text(row.get("city", "")).lower(),
            normalize_text(row.get("responsibility", ""))[:300].lower(),
        ])
        if origin:
            if id_key in seen_ids:
                continue
            seen_ids.add(id_key)
        elif content_key in seen_content:
            continue
        seen_content.add(content_key)
        result.append({field: row.get(field, "") for field in JOB_FIELDS})
    return result


def build_skill_rows(job_rows):
    rows = []
    for row in job_rows:
        evidence = normalize_text(" ".join([
            row.get("title", ""),
            row.get("responsibility", ""),
            row.get("requirement", ""),
        ]))[:500]
        for skill in [item for item in row.get("skills", "").split("|") if item]:
            rows.append({
                "source": row.get("source", ""),
                "postId": row.get("postId", ""),
                "title": row.get("title", ""),
                "skill": skill,
                "evidence": evidence,
                "sourceUrl": row.get("sourceUrl", ""),
                "fetchedAt": row.get("fetchedAt", ""),
            })
    return rows


def write_sources(job_rows):
    counts = {}
    for row in job_rows:
        counts[row["source"]] = counts.get(row["source"], 0) + 1
    source_rows = []
    fetched_at = now_iso()
    for source_name, count in sorted(counts.items()):
        config = SOURCE_CONFIGS.get(source_name, SOURCE_CONFIGS["Local Imported Dataset"])
        source_rows.append({
            "source": source_name,
            "sourceId": source_id(source_name),
            "sourceType": config["source_type"],
            "baseUrl": config["base_url"],
            "licenseNote": config["license_note"],
            "records": count,
            "fetchedAt": fetched_at,
        })
    write_csv(
        SOURCES_PATH,
        ["source", "sourceId", "sourceType", "baseUrl", "licenseNote", "records", "fetchedAt"],
        source_rows,
    )


def is_china_row(row):
    source = row.get("source", "")
    country = row.get("country", "")
    china_sources = {
        "Tencent Careers",
        "Alibaba Careers",
        "NetEase Careers",
        "ByteDance Careers",
        "Huawei Careers",
        "Baidu Careers",
        "Meituan Careers",
        "National College Student Employment Service",
        "JobOnline Public Employment Service",
    }
    return country == "China" or source in china_sources


def write_region_outputs(job_rows):
    china_rows = [row for row in job_rows if is_china_row(row)]
    foreign_rows = [row for row in job_rows if not is_china_row(row)]
    write_csv(CHINA_JOBS_PATH, JOB_FIELDS, china_rows)
    write_csv(FOREIGN_JOBS_PATH, JOB_FIELDS, foreign_rows)
    return china_rows, foreign_rows


def merge_with_existing(new_rows):
    existing_rows = [] if RESET_OUTPUTS else read_csv(JOBS_PATH)
    merged_rows = dedupe(existing_rows + new_rows)
    return existing_rows, merged_rows


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = []
    source_errors = []
    adapters = selected_adapters()
    if not adapters:
        raise SystemExit("No enabled source adapters. Set CHINA_JOB_SOURCES=remoteok,arbeitnow,tencent,imports")

    per_source_limit = int(os.environ.get("CHINA_JOB_PER_SOURCE_LIMIT", "0"))
    if per_source_limit <= 0 and BALANCED_SOURCES:
        per_source_limit = math.ceil(TARGET / len(adapters))

    print(json.dumps({
        "stage": "source_plan",
        "target": TARGET,
        "balanced": BALANCED_SOURCES,
        "per_source_limit": per_source_limit if per_source_limit > 0 else "remaining",
        "sources": [name for name, _ in adapters],
    }, ensure_ascii=False))

    for source_name, adapter in adapters:
        remaining = max(0, TARGET - len(all_rows))
        if remaining <= 0:
            break
        limit = min(remaining, per_source_limit) if per_source_limit > 0 else remaining
        try:
            rows = adapter(limit)
            all_rows.extend(rows)
            print(json.dumps({
                "stage": "source_done",
                "source": source_name,
                "limit": limit,
                "records": len(rows),
                "total": len(all_rows),
            }, ensure_ascii=False))
        except Exception as exc:
            source_errors.append({"source": source_name, "error": str(exc)})
            print(json.dumps({"stage": "source_error", "source": source_name, "error": str(exc)}, ensure_ascii=False))

    new_rows = dedupe(all_rows)
    existing_rows, job_rows = merge_with_existing(new_rows)
    china_rows, foreign_rows = write_region_outputs(job_rows)
    skill_rows = build_skill_rows(job_rows)
    write_csv(JOBS_PATH, JOB_FIELDS, job_rows)
    write_csv(SKILLS_PATH, ["source", "postId", "title", "skill", "evidence", "sourceUrl", "fetchedAt"], skill_rows)
    write_sources(job_rows)

    etl_manifest = transform()
    source_counts = {}
    for row in job_rows:
        source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1

    report = {
        "generated_at": now_iso(),
        "target": TARGET,
        "write_mode": "reset" if RESET_OUTPUTS else "merge",
        "existing_records_before_run": len(existing_rows),
        "new_records_this_run": len(new_rows),
        "actual_records": len(job_rows),
        "actual_skill_records": len(skill_rows),
        "active_sources": sorted(source_counts),
        "active_source_count": len(source_counts),
        "active_source_types": etl_manifest.get("active_source_types", []),
        "active_source_type_count": len(etl_manifest.get("active_source_types", [])),
        "source_counts": source_counts,
        "region_counts": {
            "china": len(china_rows),
            "foreign": len(foreign_rows),
        },
        "gap": max(0, TARGET - len(job_rows)),
        "target_met": len(job_rows) >= TARGET,
        "source_errors": source_errors,
        "outputs": {
            "jobs": str(JOBS_PATH.relative_to(ROOT)),
            "china_jobs": str(CHINA_JOBS_PATH.relative_to(ROOT)),
            "foreign_jobs": str(FOREIGN_JOBS_PATH.relative_to(ROOT)),
            "skills": str(SKILLS_PATH.relative_to(ROOT)),
            "sources": str(SOURCES_PATH.relative_to(ROOT)),
            "etl_manifest": "data/etl/etl_manifest.json",
        },
        "note": (
            "The pipeline never duplicates postings just to hit 100k. "
            "If target_met is false, add more lawful source adapters or CSV imports under data/imports/."
        ),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
