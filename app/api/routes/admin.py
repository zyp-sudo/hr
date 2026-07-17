"""Admin dashboard — API routes and server-rendered pages.

Serves:
- ``/api/admin/*``  — REST / SSE endpoints for logs, data quality,
  ETL governance, sample data, settings, and health.
- ``/admin/*``      — Jinja2-rendered HTML pages.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.api.deps import get_es, get_graph_repository, get_job_repository
from app.core.config import Settings, get_settings
from app.services.es_client import ElasticsearchClient
from app.services.log_service import log_stats, read_logs, stream_logs
from app.services.milvus_talent import TalentVectorStore
from app.services.storage_runtime import MySQLJobRepository, Neo4jGraphRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Templates & static discovery
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

# Project root (for reading data files relative to the repo)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

api_router = APIRouter(prefix="/api/admin", tags=["admin-api"])
page_router = APIRouter(include_in_schema=False)

# ===========================================================================
# API — Logs
# ===========================================================================


@api_router.get("/logs")
def api_logs(
    level: str | None = None,
    module: str | None = None,
    search: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> dict:
    """Query application logs with filters and pagination."""
    try:
        return read_logs(
            level=level,
            module=module,
            search=search,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"日志查询失败: {exc}") from exc


@api_router.get("/logs/stats")
def api_log_stats(
    level: str | None = None,
    module: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict:
    """Aggregate log counts by level and module."""
    try:
        return log_stats(level=level, module=module, start_time=start_time, end_time=end_time)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"日志统计失败: {exc}") from exc


@api_router.get("/logs/stream")
async def api_log_stream(
    level: str | None = None,
    module: str | None = None,
    search: str | None = None,
) -> StreamingResponse:
    """SSE endpoint that streams new log lines in real time."""
    return StreamingResponse(
        stream_logs(level=level, module=module, search=search),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ===========================================================================
# API — Data Quality
# ===========================================================================


def _read_quality_csv() -> list[dict]:
    """Read ``data/etl/data_quality_report.csv`` into a list of dicts."""
    path = os.path.join(_PROJECT_ROOT, "data", "etl", "data_quality_report.csv")
    if not os.path.isfile(path):
        raise HTTPException(status_code=503, detail="数据质量报告文件不存在，请先运行 ETL")
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Convert numeric fields
            out: dict = {}
            for k, v in row.items():
                if k in ("records", "avg_quality_score", "level_a", "level_b", "level_c", "level_d",
                         "missing_title", "missing_source_url", "missing_collected_at",
                         "missing_published_at", "missing_city", "missing_company",
                         "missing_origin_record_id", "short_responsibility", "short_requirement",
                         "no_skill_hit", "duplicate_content", "unknown_source"):
                    try:
                        out[k] = int(v) if k != "avg_quality_score" else float(v)
                    except (ValueError, TypeError):
                        out[k] = v
                else:
                    out[k] = v
            rows.append(out)
    return rows


@api_router.get("/data-quality/report")
def api_dq_report() -> dict:
    """Per-source data quality report from the ETL output CSV."""
    rows = _read_quality_csv()
    return {"sources": rows, "total_sources": len(rows)}


@api_router.get("/data-quality/summary")
def api_dq_summary() -> dict:
    """Aggregate quality distribution across all sources."""
    rows = _read_quality_csv()
    total_records = sum(r.get("records", 0) for r in rows)
    total_a = sum(r.get("level_a", 0) for r in rows)
    total_b = sum(r.get("level_b", 0) for r in rows)
    total_c = sum(r.get("level_c", 0) for r in rows)
    total_d = sum(r.get("level_d", 0) for r in rows)
    avg_score = (
        sum(r.get("avg_quality_score", 0) * r.get("records", 0) for r in rows) / total_records
        if total_records > 0 else 0
    )
    return {
        "total_records": total_records,
        "total_sources": len(rows),
        "avg_quality_score": round(avg_score, 2),
        "level_a": total_a,
        "level_b": total_b,
        "level_c": total_c,
        "level_d": total_d,
        "level_a_pct": round(total_a / total_records * 100, 1) if total_records else 0,
    }


@api_router.get("/data-quality/rules")
def api_dq_rules() -> dict:
    """Quality scoring rules from the ETL manifest."""
    manifest_path = os.path.join(_PROJECT_ROOT, "data", "etl", "etl_manifest.json")
    if not os.path.isfile(manifest_path):
        raise HTTPException(status_code=503, detail="ETL manifest 不存在")
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    return manifest.get("quality_rules", {})


@api_router.get("/data-quality/field-coverage")
def api_dq_field_coverage() -> dict:
    """Field coverage statistics from benchmarks."""
    path = os.path.join(_PROJECT_ROOT, "data", "benchmarks", "field_coverage_report.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=503, detail="字段覆盖率报告不存在")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ===========================================================================
# API — ETL Governance
# ===========================================================================


@api_router.get("/etl/manifest")
def api_etl_manifest() -> dict:
    """Full ETL manifest."""
    path = os.path.join(_PROJECT_ROOT, "data", "etl", "etl_manifest.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=503, detail="ETL manifest 不存在")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@api_router.get("/etl/sources")
def api_etl_sources() -> dict:
    """Data source registry from collection report."""
    path = os.path.join(_PROJECT_ROOT, "data", "collection_report.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=503, detail="采集报告不存在")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@api_router.post("/etl/sync-es")
def api_etl_sync_es() -> dict:
    """Trigger MySQL → Elasticsearch sync (best-effort).

    Spawns the sync script as a subprocess and returns immediately.
    """
    import subprocess
    import sys

    script = os.path.join(_PROJECT_ROOT, "scripts", "sync_mysql_to_es.py")
    if not os.path.isfile(script):
        raise HTTPException(status_code=503, detail=f"同步脚本不存在: {script}")

    try:
        # Fire-and-forget on Windows, synchronous on others for simplicity
        subprocess.Popen(
            [sys.executable, script, "--auto"],
            cwd=_PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"status": "started", "message": "MySQL → ES 同步已触发，请稍后检查 ES 索引"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"触发同步失败: {exc}") from exc


# ===========================================================================
# API — Sample Data
# ===========================================================================


@api_router.get("/samples/jobs")
def api_samples_jobs(
    mysql: Annotated[MySQLJobRepository, Depends(get_job_repository)],
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Paginated job postings from MySQL."""
    try:
        data = mysql.real_jobs(limit=1000)
        jobs = data.get("jobs", [])

        # In-memory search filter
        if search:
            q = search.lower()
            jobs = [
                j for j in jobs
                if q in (j.get("title") or "").lower()
                or q in (j.get("company") or "").lower()
                or any(q in (s or "").lower() for s in j.get("skills", []))
                or q in (j.get("category") or "").lower()
            ]

        total = len(jobs)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size) if total else 0,
            "items": jobs[start:end],
            "record_count": data.get("recordCount", 0),
            "stats": {
                "skill_stats": data.get("skillStats", [])[:10],
                "city_stats": data.get("cityStats", [])[:10],
                "category_stats": data.get("categoryStats", []),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"样本数据查询失败: {exc}") from exc


@api_router.get("/samples/skills")
def api_samples_skills(
    es: Annotated[ElasticsearchClient, Depends(get_es)],
    size: int = Query(default=30, ge=1, le=200),
) -> dict:
    """Top skills from Elasticsearch aggregation."""
    try:
        result = es.aggregate_skills(size=size)
        buckets = result.get("aggregations", {}).get("hot_skills", {}).get("buckets", [])
        return {
            "total": len(buckets),
            "items": [
                {"skill": b["key"], "count": b.get("doc_count", 0),
                 "related_job_count": b.get("related_jobs", {}).get("value", b.get("doc_count", 0))}
                for b in buckets
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"技能数据查询失败: {exc}") from exc


# ===========================================================================
# API — Settings & Health
# ===========================================================================


@api_router.get("/settings")
def api_settings(settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    """Current runtime settings (passwords masked)."""
    data = settings.model_dump()

    def _mask(key: str, val: object) -> object:
        if any(s in key.lower() for s in ("password", "secret", "token", "key", "url")):
            if isinstance(val, str) and val:
                # Show first 4 and last 4 chars if long enough
                if len(val) > 12:
                    return val[:4] + "***" + val[-4:]
                return val[:2] + "***"
        return val

    return {
        "settings": {k: _mask(k, v) for k, v in data.items()},
        "app_name": settings.app_name_en,
        "version": "1.0.0",
    }


@api_router.get("/health-full")
def api_health_full(
    mysql: Annotated[MySQLJobRepository, Depends(get_job_repository)],
    neo4j: Annotated[Neo4jGraphRepository, Depends(get_graph_repository)],
    es: Annotated[ElasticsearchClient, Depends(get_es)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Full health check: all 4 stores + disk + memory."""
    checks: dict[str, dict] = {}

    # MySQL
    try:
        mysql.ping()
        checks["mysql"] = {"status": "connected", "host": settings.mysql_url.split("@")[-1].split("/")[0] if "@" in settings.mysql_url else "localhost"}
    except Exception as exc:
        checks["mysql"] = {"status": "error", "detail": str(exc)}

    # Neo4j
    try:
        neo4j.ping()
        checks["neo4j"] = {"status": "connected", "uri": settings.neo4j_uri}
    except Exception as exc:
        checks["neo4j"] = {"status": "error", "detail": str(exc)}

    # Elasticsearch
    try:
        es.ping()
        checks["elasticsearch"] = {"status": "connected", "hosts": settings.es_hosts}
    except Exception as exc:
        checks["elasticsearch"] = {"status": "error", "detail": str(exc)}

    # Milvus
    try:
        TalentVectorStore(settings.milvus_uri, settings.milvus_token, settings.milvus_collection, settings.talent_vector_dim).health()
        checks["milvus"] = {"status": "connected", "uri": settings.milvus_uri}
    except Exception as exc:
        checks["milvus"] = {"status": "error", "detail": str(exc)}

    # Disk
    try:
        usage = shutil.disk_usage(_PROJECT_ROOT)
        checks["disk"] = {
            "status": "ok",
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "pct_used": round(usage.used / usage.total * 100, 1),
        }
    except Exception as exc:
        checks["disk"] = {"status": "error", "detail": str(exc)}

    # Memory (best-effort via psutil if available)
    try:
        import psutil
        mem = psutil.virtual_memory()
        checks["memory"] = {
            "status": "ok",
            "total_gb": round(mem.total / (1024**3), 1),
            "used_gb": round(mem.used / (1024**3), 1),
            "available_gb": round(mem.available / (1024**3), 1),
            "pct_used": mem.percent,
        }
    except ImportError:
        checks["memory"] = {"status": "unknown", "detail": "psutil not installed — install for memory stats"}

    all_ok = all(c.get("status") in ("connected", "ok") for c in checks.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "service": settings.app_name_en,
        "checks": checks,
    }


# ===========================================================================
# HTML Page Routes
# ===========================================================================


def _page_context(request: Request, title: str, current: str) -> dict:
    """Shared template context for every admin page."""
    return {
        "title": title,
        "current_page": current,
        "app_name": "XH-202621 Admin",
        "nav_items": [
            {"key": "dashboard", "label": "总览", "icon": "◉", "url": "/admin"},
            {"key": "logs", "label": "日志", "icon": "☰", "url": "/admin/logs"},
            {"key": "data-quality", "label": "数据质量", "icon": "◆", "url": "/admin/data-quality"},
            {"key": "etl", "label": "ETL 治理", "icon": "↻", "url": "/admin/etl"},
            {"key": "samples", "label": "样本数据", "icon": "▣", "url": "/admin/samples"},
            {"key": "settings", "label": "系统设置", "icon": "⚙", "url": "/admin/settings"},
        ],
    }


@page_router.get("/admin", include_in_schema=False)
async def page_dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context=_page_context(request, "总览仪表盘", "dashboard"),
    )


@page_router.get("/admin/logs", include_in_schema=False)
async def page_logs(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin/logs.html",
        context=_page_context(request, "日志查看器", "logs"),
    )


@page_router.get("/admin/data-quality", include_in_schema=False)
async def page_data_quality(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin/data_quality.html",
        context=_page_context(request, "数据质量", "data-quality"),
    )


@page_router.get("/admin/etl", include_in_schema=False)
async def page_etl(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin/etl.html",
        context=_page_context(request, "ETL 治理", "etl"),
    )


@page_router.get("/admin/samples", include_in_schema=False)
async def page_samples(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin/samples.html",
        context=_page_context(request, "样本数据", "samples"),
    )


@page_router.get("/admin/settings", include_in_schema=False)
async def page_settings(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin/settings.html",
        context=_page_context(request, "系统设置", "settings"),
    )
