from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_es
from app.core.security import get_current_user
from app.schemas.search import JobSearchResponse
from app.services.es_client import ElasticsearchClient

router = APIRouter(prefix="/api/search", tags=["search"])


def _buckets(aggs: dict, name: str) -> list[dict]:
    return [
        {"key": bucket.get("key_as_string", bucket.get("key")), "count": bucket.get("doc_count", 0)}
        for bucket in aggs.get(name, {}).get("buckets", [])
    ]


@router.get("/jobs", response_model=JobSearchResponse)
def search_jobs(
    es: Annotated[ElasticsearchClient, Depends(get_es)],
    keyword: str | None = None,
    city: str | None = None,
    industry: str | None = None,
    education: str | None = None,
    experience: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    skills: list[str] = Query(default_factory=list),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    try:
        result = es.search_jobs(
            keyword=keyword,
            city=city,
            industry=industry,
            education=education,
            experience=experience,
            salary_min=salary_min,
            salary_max=salary_max,
            skills=skills,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Elasticsearch 检索服务不可用: {type(exc).__name__}") from exc
    hits = result.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    items = [hit.get("_source", {}) for hit in hits.get("hits", [])]
    aggs = result.get("aggregations", {})
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
        "aggregations": {
            "cities": _buckets(aggs, "cities"),
            "industries": _buckets(aggs, "industries"),
            "educations": _buckets(aggs, "educations"),
            "experiences": _buckets(aggs, "experiences"),
            "skills": _buckets(aggs, "skills"),
            "salary_ranges": _buckets(aggs, "salary_ranges"),
        },
    }


# ---------------------------------------------------------------------------
# Preview endpoint — public, no auth, limited data
# ---------------------------------------------------------------------------

def _strip_for_preview(hit: dict) -> dict:
    """Keep only safe preview fields — title, summary, city, company, salary range."""
    src = hit.get("_source", hit)
    return {
        "id": src.get("id"),
        "title": src.get("title", src.get("job_title", "")),
        "company": src.get("company", src.get("company_name", "")),
        "city": src.get("city", ""),
        "salary_min": src.get("salary_min"),
        "salary_max": src.get("salary_max"),
        "summary": (
            src.get("summary")
            or src.get("description", "")[:120]
        ),
    }


@router.get("/jobs/preview")
def search_jobs_preview(
    es: Annotated[ElasticsearchClient, Depends(get_es)],
    keyword: str | None = None,
    city: str | None = None,
    industry: str | None = None,
    education: str | None = None,
    experience: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    skills: list[str] = Query(default_factory=list),
) -> dict:
    """Public preview — max 3 results with limited fields. No auth required."""
    try:
        result = es.search_jobs(
            keyword=keyword,
            city=city,
            industry=industry,
            education=education,
            experience=experience,
            salary_min=salary_min,
            salary_max=salary_max,
            skills=skills,
            page=1,
            page_size=3,            # ← hard limit: 3 rows only
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Elasticsearch 检索服务不可用: {type(exc).__name__}") from exc

    hits = result.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    items = [_strip_for_preview(h) for h in hits.get("hits", [])]
    aggs = result.get("aggregations", {})
    return {
        "total": total,
        "page": 1,
        "page_size": 3,
        "is_preview": True,          # ← frontend uses this to show login overlay
        "items": items,
        "aggregations": {
            "cities": _buckets(aggs, "cities"),
            "industries": _buckets(aggs, "industries"),
            "educations": _buckets(aggs, "educations"),
            "experiences": _buckets(aggs, "experiences"),
            "skills": _buckets(aggs, "skills"),
            "salary_ranges": _buckets(aggs, "salary_ranges"),
        },
    }


# ---------------------------------------------------------------------------
# Full-access endpoint — auth required, returns everything
# ---------------------------------------------------------------------------

@router.get("/jobs/full")
def search_jobs_full(
    es: Annotated[ElasticsearchClient, Depends(get_es)],
    user: dict = Depends(get_current_user),  # ← gatekeeper
    keyword: str | None = None,
    city: str | None = None,
    industry: str | None = None,
    education: str | None = None,
    experience: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    skills: list[str] = Query(default_factory=list),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Full search — requires valid JWT. Returns all fields, full pagination."""
    try:
        result = es.search_jobs(
            keyword=keyword,
            city=city,
            industry=industry,
            education=education,
            experience=experience,
            salary_min=salary_min,
            salary_max=salary_max,
            skills=skills,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Elasticsearch 检索服务不可用: {type(exc).__name__}") from exc
    hits = result.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    items = [hit.get("_source", {}) for hit in hits.get("hits", [])]
    aggs = result.get("aggregations", {})
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "is_preview": False,
        "items": items,
        "aggregations": {
            "cities": _buckets(aggs, "cities"),
            "industries": _buckets(aggs, "industries"),
            "educations": _buckets(aggs, "educations"),
            "experiences": _buckets(aggs, "experiences"),
            "skills": _buckets(aggs, "skills"),
            "salary_ranges": _buckets(aggs, "salary_ranges"),
        },
    }
