"""Unit tests for app.services.milvus_talent — TalentVectorStore with mocked MilvusClient."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.milvus_talent import TalentVectorStore


# ======================================================================
# Helpers
# ======================================================================

def _make_store(uri: str = "http://localhost:19530", token: str = "",
                collection: str = "test_coll", dimension: int = 128) -> TalentVectorStore:
    return TalentVectorStore(uri, token, collection, dimension)


# ======================================================================
# embed
# ======================================================================

def test_embed_returns_normalized_vector_of_correct_dimension():
    store = _make_store(dimension=8)
    vec = store.embed("Python developer 3 years experience")
    assert len(vec) == 8
    # normalized → length ≈ 1.0
    import math
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-9 or norm == 0.0  # norm == 0 only if empty


def test_embed_empty_text_returns_zero_vector():
    store = _make_store(dimension=8)
    vec = store.embed("")
    assert len(vec) == 8
    # normalization of zero vector → length stays 0? Let's check logic.
    # norm = max(sqrt(0.0), 1.0) = 1.0, so vec[i] / 1.0 = 0.0 for all i
    assert all(v == 0.0 for v in vec)


def test_embed_chinese_text():
    store = _make_store(dimension=16)
    vec = store.embed("精通Python和机器学习算法")
    assert len(vec) == 16
    import math
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-9 or norm == 0.0


def test_embed_is_deterministic():
    store = _make_store()
    v1 = store.embed("same text")
    v2 = store.embed("same text")
    assert v1 == v2


# ======================================================================
# _ensure_collection
# ======================================================================

def test_ensure_collection_skips_when_exists():
    store = _make_store()
    mock_client = MagicMock()
    mock_client.has_collection.return_value = True
    store._ensure_collection(mock_client)
    mock_client.has_collection.assert_called_once_with("test_coll")
    mock_client.create_collection.assert_not_called()


def test_ensure_collection_creates_when_missing():
    store = _make_store()
    mock_client = MagicMock()
    mock_client.has_collection.return_value = False
    store._ensure_collection(mock_client)
    mock_client.create_collection.assert_called_once()


# ======================================================================
# upsert
# ======================================================================

def test_upsert_returns_stored_status():
    store = _make_store()
    mock_client = MagicMock()
    mock_client.has_collection.return_value = True
    with patch.object(store, "_client", return_value=mock_client):
        result = store.upsert({
            "id": "cand-1",
            "name": "张三",
            "skills": ["Python", "SQL"],
            "experienceYears": 3,
            "education": "本科",
            "projectScore": 85,
            "collaborationScore": 90,
            "profileText": "Full-stack developer",
            "updatedAt": "2026-01-01",
        })
    assert result["status"] == "stored"
    assert result["candidateId"] == "cand-1"
    mock_client.upsert.assert_called_once()


def test_upsert_with_minimal_candidate():
    store = _make_store()
    mock_client = MagicMock()
    mock_client.has_collection.return_value = True
    with patch.object(store, "_client", return_value=mock_client):
        result = store.upsert({"id": "min-1"})
    assert result["status"] == "stored"
    assert result["candidateId"] == "min-1"


def test_upsert_profile_text_capped_at_8192_chars():
    store = _make_store()
    mock_client = MagicMock()
    mock_client.has_collection.return_value = True
    with patch.object(store, "_client", return_value=mock_client):
        result = store.upsert({
            "id": "long-1",
            "name": "Long",
            "profileText": "A" * 20000,
        })
    assert result["status"] == "stored"
    call_args = mock_client.upsert.call_args
    data = call_args.kwargs["data"][0]
    assert len(data["profile_text"]) <= 8192


# ======================================================================
# search
# ======================================================================

def test_search_returns_list_from_milvus():
    store = _make_store()
    mock_client = MagicMock()
    mock_client.has_collection.return_value = True
    mock_client.search.return_value = [[
        {"candidate_id": "c1", "name": "张三", "profile_text": "text", "updated_at": ""},
    ]]
    with patch.object(store, "_client", return_value=mock_client):
        results = store.search("Python工程师", limit=3)
    assert len(results) == 1
    assert results[0]["candidate_id"] == "c1"


def test_search_returns_empty_when_no_rows():
    store = _make_store()
    mock_client = MagicMock()
    mock_client.has_collection.return_value = True
    mock_client.search.return_value = []  # no rows in first element
    with patch.object(store, "_client", return_value=mock_client):
        results = store.search("nothing", limit=5)
    assert results == []


# ======================================================================
# health
# ======================================================================

def test_health_connected_when_collection_exists():
    store = _make_store()
    mock_client = MagicMock()
    mock_client.list_collections.return_value = ["test_coll", "other"]
    with patch.object(store, "_client", return_value=mock_client):
        result = store.health()
    assert result["status"] == "connected"
    assert result["collectionReady"] is True


def test_health_collection_not_ready():
    store = _make_store()
    mock_client = MagicMock()
    mock_client.list_collections.return_value = ["other_coll"]
    with patch.object(store, "_client", return_value=mock_client):
        result = store.health()
    assert result["status"] == "connected"
    assert result["collectionReady"] is False


# ======================================================================
# _client factory
# ======================================================================

def test_client_with_token():
    store = TalentVectorStore("http://uri", "my-token", "coll", 64)
    with patch("app.services.milvus_talent.MilvusClient") as MockClient:
        store._client()
        MockClient.assert_called_once_with(uri="http://uri", token="my-token")


def test_client_without_token():
    store = TalentVectorStore("http://uri", "", "coll", 64)
    with patch("app.services.milvus_talent.MilvusClient") as MockClient:
        store._client()
        MockClient.assert_called_once_with(uri="http://uri")
