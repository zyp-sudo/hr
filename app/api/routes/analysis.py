from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_es
from app.schemas.search import JobTrendResponse, SkillAnalysisResponse
from app.services.es_client import ElasticsearchClient

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _bucket_items(aggs: dict, name: str) -> list[dict]:
    return [
        {"key": bucket.get("key_as_string", bucket.get("key")), "count": bucket.get("doc_count", 0)}
        for bucket in aggs.get(name, {}).get("buckets", [])
    ]


@router.get("/skills", response_model=SkillAnalysisResponse)
def analyze_skills(
    es: Annotated[ElasticsearchClient, Depends(get_es)],
    size: int = Query(default=30, ge=1, le=200),
) -> dict:
    try:
        result = es.aggregate_skills(size=size)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Elasticsearch 聚合服务不可用: {type(exc).__name__}") from exc
    buckets = result.get("aggregations", {}).get("hot_skills", {}).get("buckets", [])
    return {
        "hot_skills": [
            {
                "skill": bucket["key"],
                "count": bucket.get("doc_count", 0),
                "related_job_count": bucket.get("related_jobs", {}).get("value", bucket.get("doc_count", 0)),
            }
            for bucket in buckets
        ]
    }


@router.get("/jobs/trend", response_model=JobTrendResponse)
def analyze_job_trend(es: Annotated[ElasticsearchClient, Depends(get_es)]) -> dict:
    try:
        result = es.job_trend_analysis()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Elasticsearch 趋势服务不可用: {type(exc).__name__}") from exc
    aggs = result.get("aggregations", {})
    return {
        "by_date": _bucket_items(aggs, "by_date"),
        "by_city": _bucket_items(aggs, "by_city"),
        "by_industry": _bucket_items(aggs, "by_industry"),
    }
