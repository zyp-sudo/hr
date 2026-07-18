"""Unit tests for app.api.routes.search — search endpoints and helpers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.deps import get_es
from app.core.security import get_current_user
from app.main import app


# ======================================================================
# Fake ES client
# ======================================================================

class FakeES:
    def __init__(self, fail: bool = False):
        self.fail = fail

    def search_jobs(self, **kwargs):
        if self.fail:
            raise ConnectionError("es down")
        return {
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {"_source": {"id": "1", "title": "Python工程师", "company": "阿里", "city": "杭州"}},
                    {"_source": {"id": "2", "title": "Go后端", "company": "腾讯", "city": "深圳"}},
                ],
            },
            "aggregations": {
                "cities": {"buckets": [{"key": "深圳", "doc_count": 1}, {"key": "杭州", "doc_count": 1}]},
                "industries": {"buckets": [{"key": "互联网", "doc_count": 2}]},
                "educations": {"buckets": []},
                "experiences": {"buckets": []},
                "skills": {"buckets": [{"key": "Python", "doc_count": 1}]},
                "salary_ranges": {"buckets": []},
            },
        }


# ======================================================================
# Helpers (imported from search module)
# ======================================================================

def test_buckets_extracts_key_and_count():
    from app.api.routes.search import _buckets
    aggs = {
        "cities": {
            "buckets": [
                {"key": "深圳", "doc_count": 5},
                {"key_as_string": "2026", "key": 2026, "doc_count": 10},
            ],
        },
    }
    result = _buckets(aggs, "cities")
    assert result == [
        {"key": "深圳", "count": 5},
        {"key": "2026", "count": 10},
    ]


def test_buckets_returns_empty_for_missing_key():
    from app.api.routes.search import _buckets
    assert _buckets({}, "missing") == []


def test_strip_for_preview_from_source():
    from app.api.routes.search import _strip_for_preview
    hit = {
        "_source": {
            "id": "1", "title": "工程师", "company": "公司A",
            "city": "北京", "salary_min": 10, "salary_max": 20,
            "description": "负责后端开发工作，需要熟悉Python...",
        },
    }
    result = _strip_for_preview(hit)
    assert result["id"] == "1"
    assert result["title"] == "工程师"
    assert result["company"] == "公司A"
    assert result["city"] == "北京"
    assert result["salary_min"] == 10
    assert result["salary_max"] == 20
    assert result["summary"].startswith("负责后端开发工作")


def test_strip_for_preview_direct_dict():
    from app.api.routes.search import _strip_for_preview
    hit = {
        "id": "2", "job_title": "设计师", "company_name": "公司B",
        "city": "上海", "description": "UI设计",
    }
    result = _strip_for_preview(hit)
    assert result["id"] == "2"
    assert result["title"] == "设计师"
    assert result["company"] == "公司B"
    assert result["city"] == "上海"


def test_strip_for_preview_falls_back_to_empty():
    from app.api.routes.search import _strip_for_preview
    result = _strip_for_preview({})
    assert result["id"] is None
    assert result["title"] == ""
    assert result["company"] == ""
    assert result["city"] == ""
    assert result["summary"] == ""


# ======================================================================
# Client fixture
# ======================================================================

def _client(es=None):
    app.dependency_overrides[get_es] = lambda: es or FakeES()
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


# ======================================================================
# search endpoints
# ======================================================================

def test_search_jobs_returns_results_and_aggs():
    client = _client()
    resp = client.get("/api/search/jobs?keyword=Python&page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert len(data["items"]) == 2
    assert data["items"][0]["title"] == "Python工程师"
    assert len(data["aggregations"]["cities"]) == 2


def test_search_jobs_default_pagination():
    client = _client()
    resp = client.get("/api/search/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 20


def test_search_jobs_503_when_es_fails():
    client = _client(es=FakeES(fail=True))
    resp = client.get("/api/search/jobs")
    assert resp.status_code == 503
    assert "Elasticsearch" in resp.json()["detail"]


def test_search_jobs_preview_limits_to_3():
    client = _client()
    resp = client.get("/api/search/jobs/preview?keyword=Python")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_preview"] is True
    assert data["page_size"] == 3
    assert len(data["items"]) <= 3


def test_search_jobs_preview_503_when_es_fails():
    client = _client(es=FakeES(fail=True))
    resp = client.get("/api/search/jobs/preview")
    assert resp.status_code == 503


def test_search_jobs_full_requires_auth():
    client = _client()
    resp = client.get("/api/search/jobs/full?keyword=Python")
    assert resp.status_code == 403 or resp.status_code == 401  # HTTPBearer returns 401/403 when no credentials


def test_search_jobs_full_with_auth():
    client = _client()
    # Override the auth dependency
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1, "role": "user"}
    resp = client.get("/api/search/jobs/full?keyword=Python")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_preview"] is False
    assert data["total"] == 2


def test_search_jobs_full_503_when_es_fails():
    client = _client(es=FakeES(fail=True))
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1, "role": "user"}
    resp = client.get("/api/search/jobs/full")
    assert resp.status_code == 503


def test_search_jobs_with_skills_filter():
    client = _client()
    resp = client.get("/api/search/jobs?skills=Python&skills=Go")
    assert resp.status_code == 200


def test_search_jobs_with_salary_filter():
    client = _client()
    resp = client.get("/api/search/jobs?salary_min=10000&salary_max=50000")
    assert resp.status_code == 200


def test_search_jobs_with_all_filters():
    client = _client()
    resp = client.get(
        "/api/search/jobs"
        "?keyword=Python&city=深圳&industry=互联网&education=本科"
        "&experience=3年&salary_min=15000&salary_max=35000"
        "&skills=Python&skills=SQL"
        "&page=1&page_size=10"
    )
    assert resp.status_code == 200
