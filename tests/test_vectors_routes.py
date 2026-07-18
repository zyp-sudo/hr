"""Unit tests for app.api.routes.vectors — Milvus talent vector endpoints."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.deps import get_graph_repository, get_settings
from app.core.config import Settings
from app.main import app


# ======================================================================
# Fake TalentVectorStore
# ======================================================================

class FakeTalentVectorStore:
    def __init__(self, uri: str = "", token: str = "", collection: str = "", dimension: int = 128):
        self.uri = uri
        self.collection = collection
        self.fail = False

    def health(self):
        if self.fail:
            raise ConnectionError("milvus down")
        return {"status": "connected", "collectionReady": True}

    def upsert(self, candidate: dict):
        if self.fail:
            raise ConnectionError("milvus down")
        return {"status": "stored", "candidateId": candidate.get("id", "?")}

    def search(self, query: str, limit: int = 5):
        if self.fail:
            raise ConnectionError("milvus down")
        return [{"candidate_id": "c1", "name": "张三", "score": 0.95}]


# ======================================================================
# Fake Graph Repository
# ======================================================================

class FakeGraphRepo:
    def related_subgraph(self, terms):
        return {"nodes": [{"id": "s1", "label": "Python"}], "edges": [], "storage": "neo4j"}


# ======================================================================
# Fake Settings
# ======================================================================

def _fake_settings():
    return Settings(
        milvus_uri="http://mock:19530",
        milvus_token="",
        milvus_collection="test_coll",
        talent_vector_dim=128,
    )


# ======================================================================
# Client setup / teardown
# ======================================================================

def _client(talent_store=None, graph=None):
    app.dependency_overrides[get_settings] = _fake_settings
    app.dependency_overrides[get_graph_repository] = lambda: graph or FakeGraphRepo()
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


# ======================================================================
# Health
# ======================================================================

def test_vectors_health_connected(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.vectors.TalentVectorStore",
        lambda *a, **kw: FakeTalentVectorStore(*a, **kw),
    )
    client = _client()
    resp = client.get("/api/talent-vectors/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "connected"


def test_vectors_health_unavailable(monkeypatch):
    store = FakeTalentVectorStore()
    store.fail = True
    monkeypatch.setattr(
        "app.api.routes.vectors.TalentVectorStore",
        lambda *a, **kw: store,
    )
    client = _client()
    resp = client.get("/api/talent-vectors/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unavailable"


# ======================================================================
# Upsert
# ======================================================================

def test_vectors_upsert(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.vectors.TalentVectorStore",
        lambda *a, **kw: FakeTalentVectorStore(*a, **kw),
    )
    client = _client()
    resp = client.post("/api/talent-vectors/upsert", json={
        "id": "cand-1",
        "name": "张三",
        "skills": ["Python", "Go"],
        "experienceYears": 3,
        "education": "本科",
        "projectScore": 85,
        "collaborationScore": 90,
    })
    assert resp.status_code == 200
    assert resp.json()["candidateId"] == "cand-1"


def test_vectors_upsert_503_on_failure(monkeypatch):
    store = FakeTalentVectorStore()
    store.fail = True
    monkeypatch.setattr(
        "app.api.routes.vectors.TalentVectorStore",
        lambda *a, **kw: store,
    )
    client = _client()
    resp = client.post("/api/talent-vectors/upsert", json={"id": "cand-1"})
    assert resp.status_code == 503


# ======================================================================
# Search
# ======================================================================

def test_vectors_search(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.vectors.TalentVectorStore",
        lambda *a, **kw: FakeTalentVectorStore(*a, **kw),
    )
    client = _client()
    resp = client.post("/api/talent-vectors/search", json={
        "query": "Python工程师",
        "limit": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "Python工程师"
    assert len(data["items"]) == 1


def test_vectors_search_503_on_failure(monkeypatch):
    store = FakeTalentVectorStore()
    store.fail = True
    monkeypatch.setattr(
        "app.api.routes.vectors.TalentVectorStore",
        lambda *a, **kw: store,
    )
    client = _client()
    resp = client.post("/api/talent-vectors/search", json={"query": "Python"})
    assert resp.status_code == 503


def test_vectors_search_validates_query_min_length():
    client = _client()
    resp = client.post("/api/talent-vectors/search", json={"query": "P", "limit": 5})
    assert resp.status_code == 422  # pydantic validation: min_length=2


# ======================================================================
# Hybrid search
# ======================================================================

def test_vectors_hybrid_search(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.vectors.TalentVectorStore",
        lambda *a, **kw: FakeTalentVectorStore(*a, **kw),
    )
    client = _client(graph=FakeGraphRepo())
    resp = client.post("/api/talent-vectors/hybrid-search", json={
        "query": "Python 工程师",
        "limit": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "Python 工程师"
    assert len(data["talents"]) == 1
    assert data["retrieval"]["vector"] == "milvus"
    assert "evidenceSubgraph" in data


def test_vectors_hybrid_search_graph_unavailable_still_succeeds(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.vectors.TalentVectorStore",
        lambda *a, **kw: FakeTalentVectorStore(*a, **kw),
    )

    class FailingGraph:
        def related_subgraph(self, terms):
            raise ConnectionError("neo4j down")

    client = _client(graph=FailingGraph())
    resp = client.post("/api/talent-vectors/hybrid-search", json={
        "query": "Python",
        "limit": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["retrieval"]["graph"].startswith("unavailable")


def test_vectors_hybrid_search_milvus_fails(monkeypatch):
    store = FakeTalentVectorStore()
    store.fail = True
    monkeypatch.setattr(
        "app.api.routes.vectors.TalentVectorStore",
        lambda *a, **kw: store,
    )
    client = _client()
    resp = client.post("/api/talent-vectors/hybrid-search", json={
        "query": "Python",
        "limit": 5,
    })
    assert resp.status_code == 503
