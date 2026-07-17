from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_es, get_graph_repository, get_job_repository
from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.services.storage_runtime import MySQLJobRepository, Neo4jGraphRepository
from app.services.es_client import ElasticsearchClient
from app.services.milvus_talent import TalentVectorStore

router = APIRouter(prefix="/api", tags=["mysql-neo4j-runtime"])


@router.get("/health")
def health(
    mysql: Annotated[MySQLJobRepository, Depends(get_job_repository)],
    neo4j: Annotated[Neo4jGraphRepository, Depends(get_graph_repository)],
    elasticsearch: Annotated[ElasticsearchClient, Depends(get_es)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    checks: dict[str, str] = {}
    for name, check in (("mysql", mysql.ping), ("neo4j", neo4j.ping), ("elasticsearch", elasticsearch.ping)):
        try:
            check()
            checks[name] = "connected"
        except Exception as exc:
            checks[name] = f"unavailable: {type(exc).__name__}"
    try:
        TalentVectorStore(settings.milvus_uri, settings.milvus_token, settings.milvus_collection, settings.talent_vector_dim).health()
        checks["milvus"] = "connected"
    except Exception as exc:
        checks["milvus"] = f"unavailable: {type(exc).__name__}"
    return {
        "status": "ok" if all(value == "connected" for value in checks.values()) else "degraded",
        "service": "xh-202621-storage-api",
        "storage": checks,
    }


@router.get("/jobs")
def jobs(mysql: Annotated[MySQLJobRepository, Depends(get_job_repository)]) -> dict:
    try:
        return {"jobs": mysql.jobs(), "storage": "mysql"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MySQL 数据源不可用: {exc}") from exc


@router.get("/real-jobs")
def real_jobs(
    mysql: Annotated[MySQLJobRepository, Depends(get_job_repository)],
    limit: int = Query(default=100, ge=0, le=1000),
) -> dict:
    try:
        return mysql.real_jobs(limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MySQL 数据源不可用: {exc}") from exc


@router.get("/graph")
def graph(
    neo4j: Annotated[Neo4jGraphRepository, Depends(get_graph_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        return neo4j.graph(settings.graph_node_limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Neo4j 图数据源不可用: {exc}") from exc


@router.get("/kg-summary")
def graph_summary(
    neo4j: Annotated[Neo4jGraphRepository, Depends(get_graph_repository)],
) -> dict:
    try:
        return neo4j.summary()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Neo4j 图数据源不可用: {exc}") from exc


# ---------------------------------------------------------------------------
# Preview / Full-access split — auth-gated data endpoints
# ---------------------------------------------------------------------------

_PREVIEW_LIMIT = 3

_PREVIEW_JOB_FIELDS = {
    "id", "title", "job_title", "company", "company_name",
    "city", "salary_min", "salary_max", "summary", "industry",
}


def _strip_job_for_preview(job: dict) -> dict:
    """Return only safe preview fields from a job dict."""
    return {k: v for k, v in job.items() if k in _PREVIEW_JOB_FIELDS}


@router.get("/jobs/preview")
def jobs_preview(
    mysql: Annotated[MySQLJobRepository, Depends(get_job_repository)],
) -> dict:
    """Public preview — first 3 jobs with limited fields."""
    try:
        all_jobs: list[dict] = mysql.jobs().get("jobs", [])
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MySQL 数据源不可用: {exc}") from exc
    preview = [_strip_job_for_preview(j) for j in all_jobs[:_PREVIEW_LIMIT]]
    return {
        "jobs": preview,
        "storage": "mysql",
        "is_preview": True,
        "total": len(all_jobs),
        "shown": len(preview),
    }


@router.get("/jobs/full")
def jobs_full(
    mysql: Annotated[MySQLJobRepository, Depends(get_job_repository)],
    user: dict = Depends(get_current_user),  # ← gatekeeper
) -> dict:
    """Full jobs list — requires valid JWT."""
    try:
        return {"jobs": mysql.jobs().get("jobs", []), "storage": "mysql", "is_preview": False}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MySQL 数据源不可用: {exc}") from exc


@router.get("/real-jobs/preview")
def real_jobs_preview(
    mysql: Annotated[MySQLJobRepository, Depends(get_job_repository)],
) -> dict:
    """Public preview — first 3 real jobs with limited fields."""
    try:
        result = mysql.real_jobs(limit=_PREVIEW_LIMIT)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MySQL 数据源不可用: {exc}") from exc

    items = result.get("items", result.get("jobs", []))
    pre_count = result.get("total", result.get("count", len(items)))

    return {
        "items": [_strip_job_for_preview(i) for i in items],
        "is_preview": True,
        "total": pre_count,
        "shown": len(items),
    }


@router.get("/real-jobs/full")
def real_jobs_full(
    mysql: Annotated[MySQLJobRepository, Depends(get_job_repository)],
    user: dict = Depends(get_current_user),  # ← gatekeeper
    limit: int = Query(default=100, ge=0, le=1000),
) -> dict:
    """Full real-jobs list — requires valid JWT."""
    try:
        result = mysql.real_jobs(limit)
        result["is_preview"] = False
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MySQL 数据源不可用: {exc}") from exc
