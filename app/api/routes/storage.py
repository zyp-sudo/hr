from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_es, get_graph_repository, get_job_repository
from app.core.config import Settings, get_settings
from app.services.storage_runtime import MySQLJobRepository, Neo4jGraphRepository
from app.services.es_client import ElasticsearchClient

router = APIRouter(prefix="/api", tags=["mysql-neo4j-runtime"])


@router.get("/health")
def health(
    mysql: Annotated[MySQLJobRepository, Depends(get_job_repository)],
    neo4j: Annotated[Neo4jGraphRepository, Depends(get_graph_repository)],
    elasticsearch: Annotated[ElasticsearchClient, Depends(get_es)],
) -> dict:
    checks: dict[str, str] = {}
    for name, check in (("mysql", mysql.ping), ("neo4j", neo4j.ping), ("elasticsearch", elasticsearch.ping)):
        try:
            check()
            checks[name] = "connected"
        except Exception as exc:
            checks[name] = f"unavailable: {type(exc).__name__}"
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
