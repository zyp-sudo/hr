from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_es, get_graph_repository, get_job_repository
from app.main import app


class FakeES:
    def __init__(self, fail=False):
        self.fail = fail

    def ping(self):
        if self.fail:
            raise ConnectionError("es")
        return True

    def search_jobs(self, **_kwargs):
        if self.fail:
            raise ConnectionError("es")
        return {
            "hits": {"total": {"value": 1}, "hits": [{"_source": {"id": "1", "title": "Python"}}]},
            "aggregations": {"cities": {"buckets": [{"key": "深圳", "doc_count": 1}]}},
        }

    def aggregate_skills(self, size=30):
        if self.fail:
            raise ConnectionError("es")
        return {"aggregations": {"hot_skills": {"buckets": [{"key": "Python", "doc_count": size}]}}}

    def job_trend_analysis(self):
        if self.fail:
            raise ConnectionError("es")
        return {"aggregations": {"by_date": {"buckets": [{"key_as_string": "2026-01-01", "doc_count": 2}]}}}


class FakeMySQL:
    def __init__(self, fail=False):
        self.fail = fail

    def ping(self):
        if self.fail:
            raise ConnectionError("mysql")
        return True

    def jobs(self):
        if self.fail:
            raise ConnectionError("mysql")
        return [{"id": "role:1"}]

    def real_jobs(self, limit):
        if self.fail:
            raise ConnectionError("mysql")
        return {"jobs": [], "returnedCount": limit}


class FakeGraph:
    def __init__(self, fail=False):
        self.fail = fail

    def ping(self):
        if self.fail:
            raise ConnectionError("neo4j")
        return True

    def graph(self, limit):
        if self.fail:
            raise ConnectionError("neo4j")
        return {"nodes": [], "edges": [], "limit": limit}

    def summary(self):
        if self.fail:
            raise ConnectionError("neo4j")
        return {"nodes": 1}


def _client(es=None, mysql=None, graph=None):
    app.dependency_overrides[get_es] = lambda: es or FakeES()
    app.dependency_overrides[get_job_repository] = lambda: mysql or FakeMySQL()
    app.dependency_overrides[get_graph_repository] = lambda: graph or FakeGraph()
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_fastapi_search_analysis_storage_happy_paths():
    client = _client()
    assert client.get("/api/search/jobs?keyword=Python").json()["total"] == 1
    assert client.get("/api/analysis/skills?size=2").json()["hot_skills"][0]["count"] == 2
    assert client.get("/api/analysis/jobs/trend").json()["by_date"][0]["key"] == "2026-01-01"
    assert client.get("/api/jobs").status_code == 200
    assert client.get("/api/real-jobs?limit=3").json()["returnedCount"] == 3
    assert client.get("/api/graph").status_code == 200
    assert client.get("/api/kg-summary").json()["nodes"] == 1
    assert client.get("/api/health").json()["status"] == "ok"


def test_fastapi_dependencies_report_503_and_degraded_health():
    client = _client(es=FakeES(True), mysql=FakeMySQL(True), graph=FakeGraph(True))
    assert client.get("/api/search/jobs").status_code == 503
    assert client.get("/api/analysis/skills").status_code == 503
    assert client.get("/api/analysis/jobs/trend").status_code == 503
    assert client.get("/api/jobs").status_code == 503
    assert client.get("/api/real-jobs").status_code == 503
    assert client.get("/api/graph").status_code == 503
    assert client.get("/api/kg-summary").status_code == 503
    health = client.get("/api/health").json()
    assert health["status"] == "degraded"
    for dependency in ("mysql", "neo4j", "elasticsearch"):
        assert health["storage"][dependency].startswith("unavailable")
    assert health["storage"]["milvus"] == "connected" or health["storage"]["milvus"].startswith("unavailable")
