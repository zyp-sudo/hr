from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from elasticsearch import Elasticsearch, helpers

from app.core.config import get_settings
from app.services.es_mappings import INDEX_MAPPINGS, JOB_INDEX, SKILL_INDEX


class ElasticsearchClient:
    def __init__(self) -> None:
        settings = get_settings()
        kwargs: dict[str, Any] = {
            "hosts": settings.es_hosts,
            "verify_certs": settings.es_verify_certs,
            "request_timeout": 30,
        }
        if settings.es_username and settings.es_password:
            kwargs["basic_auth"] = (settings.es_username, settings.es_password)
        self.client = Elasticsearch(**kwargs)

    def ping(self) -> bool:
        return bool(self.client.ping())

    def count(self, index_name: str = JOB_INDEX) -> int:
        if not self.client.indices.exists(index=index_name):
            return 0
        return int(self.client.count(index=index_name).get("count", 0))

    def refresh(self, index_name: str = JOB_INDEX) -> None:
        self.client.indices.refresh(index=index_name)

    def create_index(self, index_name: str, recreate: bool = False) -> None:
        if recreate:
            self.delete_index(index_name, ignore_missing=True)
        if self.client.indices.exists(index=index_name):
            return
        body = INDEX_MAPPINGS[index_name]
        self.client.indices.create(index=index_name, **body)

    def create_all_indices(self, recreate: bool = False) -> None:
        for index_name in INDEX_MAPPINGS:
            self.create_index(index_name, recreate=recreate)

    def delete_index(self, index_name: str, ignore_missing: bool = False) -> None:
        if not self.client.indices.exists(index=index_name):
            if ignore_missing:
                return
            raise ValueError(f"Index not found: {index_name}")
        self.client.indices.delete(index=index_name)

    def index_document(self, index_name: str, doc_id: int | str, document: dict[str, Any]) -> None:
        self.client.index(index=index_name, id=str(doc_id), document=document)

    def bulk_index(self, index_name: str, documents: Iterable[dict[str, Any]], chunk_size: int = 800) -> tuple[int, list[Any]]:
        actions = (
            {
                "_op_type": "index",
                "_index": index_name,
                "_id": str(doc["id"]),
                "_source": doc,
            }
            for doc in documents
        )
        success, errors = helpers.bulk(
            self.client,
            actions,
            chunk_size=chunk_size,
            raise_on_error=False,
            request_timeout=60,
        )
        return success, errors

    def search_jobs(
        self,
        keyword: str | None = None,
        city: str | None = None,
        industry: str | None = None,
        education: str | None = None,
        experience: str | None = None,
        salary_min: int | None = None,
        salary_max: int | None = None,
        skills: list[str] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        filters: list[dict[str, Any]] = []
        if city:
            filters.append({"term": {"city": city}})
        if industry:
            filters.append({"term": {"industry": industry}})
        if education:
            filters.append({"term": {"education": education}})
        if experience:
            filters.append({"term": {"experience": experience}})
        if skills:
            filters.append({"terms": {"skills": skills}})
        if salary_min is not None:
            filters.append({"range": {"salary_max": {"gte": salary_min}}})
        if salary_max is not None:
            filters.append({"range": {"salary_min": {"lte": salary_max}}})

        must: list[dict[str, Any]] = []
        if keyword:
            must.append({
                "multi_match": {
                    "query": keyword,
                    "fields": ["title^4", "company_name^2", "description", "requirement", "skill_text^3"],
                    "type": "best_fields",
                }
            })

        query: dict[str, Any] = {"bool": {"filter": filters}}
        if must:
            query["bool"]["must"] = must
        else:
            query["bool"]["must"] = [{"match_all": {}}]

        # A textual query must rank by relevance first. Freshness is only a
        # deterministic tie-breaker; browsing without a query remains recency-first.
        sort: list[dict[str, Any]]
        if keyword:
            sort = [
                {"_score": {"order": "desc"}},
                {"published_at": {"order": "desc", "missing": "_last"}},
                {"id": {"order": "asc"}},
            ]
        else:
            sort = [
                {"published_at": {"order": "desc", "missing": "_last"}},
                {"id": {"order": "asc"}},
            ]

        body = {
            "query": query,
            "track_total_hits": True,
            "from": max(page - 1, 0) * page_size,
            "size": page_size,
            "sort": sort,
            "aggs": {
                "cities": {"terms": {"field": "city", "size": 20}},
                "industries": {"terms": {"field": "industry", "size": 20}},
                "educations": {"terms": {"field": "education", "size": 10}},
                "experiences": {"terms": {"field": "experience", "size": 10}},
                "skills": {"terms": {"field": "skills", "size": 30}},
                "salary_ranges": {
                    "range": {
                        "field": "salary_min",
                        "ranges": [
                            {"to": 10000},
                            {"from": 10000, "to": 20000},
                            {"from": 20000, "to": 30000},
                            {"from": 30000},
                        ],
                    }
                },
            },
        }
        return self.client.search(index=JOB_INDEX, body=body)

    def search_jobs_by_skills(self, skills: list[str], page: int = 1, page_size: int = 20) -> dict[str, Any]:
        return self.search_jobs(skills=skills, page=page, page_size=page_size)

    def aggregate_skills(self, size: int = 50) -> dict[str, Any]:
        body = {
            "size": 0,
            "aggs": {
                "hot_skills": {
                    "terms": {"field": "skills", "size": size},
                    "aggs": {"related_jobs": {"cardinality": {"field": "id"}}},
                }
            },
        }
        return self.client.search(index=JOB_INDEX, body=body)

    def job_trend_analysis(self) -> dict[str, Any]:
        body = {
            "size": 0,
            "aggs": {
                "by_date": {
                    "date_histogram": {
                        "field": "published_at",
                        "calendar_interval": "day",
                        "format": "yyyy-MM-dd",
                        "min_doc_count": 0,
                    }
                },
                "by_city": {"terms": {"field": "city", "size": 30}},
                "by_industry": {"terms": {"field": "industry", "size": 30}},
            },
        }
        return self.client.search(index=JOB_INDEX, body=body)

    def get_skill_index_stats(self, size: int = 50) -> dict[str, Any]:
        body = {
            "size": size,
            "sort": [{"heat": {"order": "desc"}}, {"related_job_count": {"order": "desc"}}],
            "query": {"match_all": {}},
        }
        return self.client.search(index=SKILL_INDEX, body=body)


def get_es_client() -> ElasticsearchClient:
    return ElasticsearchClient()
