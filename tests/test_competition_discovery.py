"""Comprehensive tests for competition discovery — service layer + HTTP routes.

All tests use `tmp_path` to isolate data — no pollution of production
``data/competition/`` at any point, even on test failure or interruption.
"""

from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

import pytest

# ── Monkeypatch service paths BEFORE importing anything from app ──
# We do this at module level via a pytest fixture so every test gets
# isolated paths by default.


@pytest.fixture(autouse=True)
def _isolate_competition_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect ALL competition JSON paths into a fresh tmp_path per test."""
    # Build the competition subdirectory
    comp_dir = tmp_path / "competition"
    comp_dir.mkdir(parents=True, exist_ok=True)

    # Seed empty files so the service doesn't warn on first read
    for name in ["discoveries.json", "reviews.json", "roles.json", "panorama.json"]:
        p = comp_dir / name
        default = [] if name != "panorama.json" else {"nodes": [], "edges": [], "meta": {}}
        p.write_text(json.dumps(default, ensure_ascii=False), encoding="utf-8")

    # Target the _DATA_DIR constant in the service *after* it is imported
    import app.services.competition_core as svc

    monkeypatch.setattr(svc, "_DATA_DIR", comp_dir, raising=True)
    monkeypatch.setattr(svc, "_DISCOVERIES_PATH", comp_dir / "discoveries.json", raising=True)
    monkeypatch.setattr(svc, "_REVIEWS_PATH", comp_dir / "reviews.json", raising=True)
    monkeypatch.setattr(svc, "_ROLES_PATH", comp_dir / "roles.json", raising=True)
    monkeypatch.setattr(svc, "_PANORAMA_PATH", comp_dir / "panorama.json", raising=True)

    yield tmp_path

    # tmp_path is auto-cleaned by pytest


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _unique_name() -> str:
    return f"测试岗位-{uuid.uuid4().hex[:8]}"


# ═══════════════════════════════════════════════════════════════════════════
# SERVICE-LAYER TESTS (tmp_path isolated)
# ═══════════════════════════════════════════════════════════════════════════


class TestServiceCreate:
    """Service.create_discovery with tmp_path isolation."""

    def test_basic_create(self):
        from app.services.competition_core import create_discovery

        name = _unique_name()
        result = create_discovery(
            name=name,
            responsibilities=["设计系统架构", "编写核心代码"],
            required_skills=["Python", "FastAPI"],
            bonus_skills=["Docker"],
            application_scenarios=["后端服务"],
        )

        assert result is not None
        assert result["name"] == name
        assert result["review_status"] == "pending"
        assert result["source_ids"] == ["manual-entry"]
        assert len(result["id"]) > 0
        assert len(result["required_skills"]) == 2
        assert result["required_skills"][0]["name"] == "Python"
        assert result["required_skills"][0]["source_ids"] == ["manual-entry"]
        assert result["confidence"] == 0.5
        assert result["growth_rate"] == 0.05
        assert isinstance(result["created_at"], str)

    def test_appears_in_list(self):
        from app.services.competition_core import create_discovery, list_discoveries

        name = _unique_name()
        create_discovery(name=name, responsibilities=["测试"], required_skills=[], bonus_skills=[], application_scenarios=[])

        all_items = list_discoveries()
        found = [it for it in all_items if it["name"] == name]
        assert len(found) == 1
        assert found[0]["review_status"] == "pending"

    def test_duplicate_returns_none(self):
        from app.services.competition_core import create_discovery

        name = _unique_name()
        first = create_discovery(name=name, responsibilities=["A"], required_skills=[], bonus_skills=[], application_scenarios=[])
        assert first is not None

        second = create_discovery(name=name, responsibilities=["B"], required_skills=[], bonus_skills=[], application_scenarios=[])
        assert second is None

    def test_duplicate_case_insensitive(self):
        from app.services.competition_core import create_discovery

        name = _unique_name()
        create_discovery(name=name, responsibilities=["X"], required_skills=[], bonus_skills=[], application_scenarios=[])
        dup = create_discovery(name=name.upper(), responsibilities=["Y"], required_skills=[], bonus_skills=[], application_scenarios=[])
        assert dup is None

    def test_persistence_survives_reread(self):
        from app.services.competition_core import create_discovery, list_discoveries

        name = _unique_name()
        create_discovery(name=name, responsibilities=["R1"], required_skills=["Go"], bonus_skills=[], application_scenarios=[])

        items = list_discoveries()
        found = next(it for it in items if it["name"] == name)
        assert found is not None
        assert found["review_status"] == "pending"

    def test_default_values(self):
        from app.services.competition_core import create_discovery

        name = _unique_name()
        result = create_discovery(name=name, responsibilities=["R"], required_skills=[], bonus_skills=[], application_scenarios=[])
        assert result is not None
        assert result["confidence"] == 0.5
        assert result["growth_rate"] == 0.05
        assert result["source_count"] == 1
        assert result["source_note"] == "人工录入"
        assert result["review_status"] == "pending"
        assert result["reviewed_at"] is None

    def test_whitespace_trimmed(self):
        from app.services.competition_core import create_discovery

        name = _unique_name()
        result = create_discovery(
            name=f"  {name}  ",
            responsibilities=["  代码审查  ", "", "  架构设计  "],
            required_skills=["  Python  ", "", "  Go  "],
            bonus_skills=[],
            application_scenarios=["  后端  "],
        )
        assert result is not None
        assert result["name"] == name
        assert result["responsibilities"] == ["代码审查", "架构设计"]
        assert {s["name"] for s in result["required_skills"]} == {"Python", "Go"}

    def test_empty_name_rejected(self):
        from app.services.competition_core import create_discovery

        result = create_discovery(name="   ", responsibilities=["R"], required_skills=[], bonus_skills=[], application_scenarios=[])
        assert result is None

    def test_empty_responsibilities_rejected(self):
        from app.services.competition_core import create_discovery

        result = create_discovery(name=_unique_name(), responsibilities=["  ", ""], required_skills=[], bonus_skills=[], application_scenarios=[])
        assert result is None


class TestServiceReview:
    """Verify review flow still works after creation."""

    def test_review_after_create(self):
        from app.services.competition_core import create_discovery, create_review, get_discovery

        name = _unique_name()
        created = create_discovery(name=name, responsibilities=["R"], required_skills=[], bonus_skills=[], application_scenarios=[])
        assert created is not None

        review = create_review(
            discovery_id=created["id"],
            status="approved",
            editor="test-runner",
            comment="批准测试",
        )
        assert review is not None
        assert review["status"] == "approved"

        updated = get_discovery(created["id"])
        assert updated is not None
        assert updated["review_status"] == "approved"
        assert updated["reviewed_at"] is not None

    def test_review_does_not_pollute(self):
        """Review records are written inside tmp_path, never to real data."""
        from app.services.competition_core import create_discovery, create_review

        name = _unique_name()
        created = create_discovery(name=name, responsibilities=["R"], required_skills=[], bonus_skills=[], application_scenarios=[])
        create_review(discovery_id=created["id"], status="approved", editor="test")

        # After this test, tmp_path is cleaned — no assertion needed;
        # the fixture ensures data never hits the real competition dir.


# ═══════════════════════════════════════════════════════════════════════════
# CONCURRENT SAFETY TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestConcurrentSafety:
    """Verify the per-file lock prevents write-loss during concurrent access."""

    def test_concurrent_creates_no_write_loss(self):
        """Two threads racing to create distinct records should both succeed."""
        import app.services.competition_core as svc

        results = []
        errors = []

        def create_one(idx: int):
            try:
                name = f"并发测试-{uuid.uuid4().hex[:8]}"
                r = svc.create_discovery(
                    name=name,
                    responsibilities=[f"并发职责-{idx}"],
                    required_skills=[f"skill-{idx}"],
                    bonus_skills=[],
                    application_scenarios=[],
                )
                results.append((idx, r))
            except Exception as e:
                errors.append((idx, e))

        threads = [threading.Thread(target=create_one, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Unexpected errors: {errors}"
        successful = [r for _, r in results if r is not None]
        assert len(successful) == 8, f"Expected 8 successful creates, got {len(successful)}"

        # All 8 should appear in the list
        items = svc.list_discoveries()
        assert len(items) >= 8

    def test_concurrent_duplicate_only_one_wins(self):
        """Two threads creating same-name records — exactly one succeeds."""
        import app.services.competition_core as svc

        shared_name = _unique_name()
        results = []

        def try_create():
            r = svc.create_discovery(
                name=shared_name,
                responsibilities=["并发去重"],
                required_skills=[],
                bonus_skills=[],
                application_scenarios=[],
            )
            results.append(r)

        t1 = threading.Thread(target=try_create)
        t2 = threading.Thread(target=try_create)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        non_none = [r for r in results if r is not None]
        assert len(non_none) == 1, f"Duplicate should produce exactly 1 success, got {len(non_none)}"
        assert non_none[0]["name"] == shared_name


# ═══════════════════════════════════════════════════════════════════════════
# PYDANTIC VALIDATION TESTS (no HTTP, exercises field_validators directly)
# ═══════════════════════════════════════════════════════════════════════════


class TestPydanticValidation:
    """Test that CreateDiscoveryRequest field_validators work correctly."""

    def test_strips_name_whitespace(self):
        from app.schemas.competition import CreateDiscoveryRequest

        req = CreateDiscoveryRequest(name="   AI工程师  ", responsibilities=["R"])
        assert req.name == "AI工程师"

    def test_rejects_empty_name_string(self):
        """Empty string should fail Pydantic min_length=1."""
        from app.schemas.competition import CreateDiscoveryRequest
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            CreateDiscoveryRequest(name="", responsibilities=["R"])

    def test_rejects_empty_name(self):
        """Whitespace-only name must raise Pydantic ValidationError via field_validator."""
        from app.schemas.competition import CreateDiscoveryRequest
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            CreateDiscoveryRequest(name="   ", responsibilities=["R"])

    def test_rejects_all_whitespace_responsibilities(self):
        """All-whitespace responsibilities must raise Pydantic ValidationError."""
        from app.schemas.competition import CreateDiscoveryRequest
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            CreateDiscoveryRequest(name="工程师", responsibilities=["  ", "\t", ""])

    def test_strips_responsibilities(self):
        from app.schemas.competition import CreateDiscoveryRequest

        req = CreateDiscoveryRequest(name="工程师", responsibilities=["  设计架构  ", "", "  编码  "])
        assert req.responsibilities == ["设计架构", "编码"]

    def test_strips_skills(self):
        from app.schemas.competition import CreateDiscoveryRequest

        req = CreateDiscoveryRequest(
            name="工程师",
            responsibilities=["R"],
            required_skills=["  Python  ", "", "  Go  "],
            bonus_skills=["  Docker  "],
        )
        assert req.required_skills == ["Python", "Go"]
        assert req.bonus_skills == ["Docker"]

    def test_empty_source_note_defaults(self):
        from app.schemas.competition import CreateDiscoveryRequest

        req = CreateDiscoveryRequest(name="工程师", responsibilities=["R"], source_note="   ")
        assert req.source_note == "人工录入"

    def test_name_too_long(self):
        from app.schemas.competition import CreateDiscoveryRequest
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            CreateDiscoveryRequest(name="A" * 201, responsibilities=["R"])

    def test_responsibilities_too_many(self):
        from app.schemas.competition import CreateDiscoveryRequest
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            CreateDiscoveryRequest(name="工程师", responsibilities=["R"] * 21)

    def test_skills_too_many(self):
        from app.schemas.competition import CreateDiscoveryRequest
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            CreateDiscoveryRequest(name="工程师", responsibilities=["R"], required_skills=["s"] * 31)


# ═══════════════════════════════════════════════════════════════════════════
# HTTP ROUTE TESTS (FastAPI TestClient, tmp_path isolated)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a FastAPI TestClient with isolated competition data paths.

    This fixture builds a minimal FastAPI app that only includes the
    competition_core router, so no MySQL/ES/Milvus dependencies are required.
    """
    comp_dir = tmp_path / "competition"
    comp_dir.mkdir(parents=True, exist_ok=True)
    for name in ["discoveries.json", "reviews.json", "roles.json", "panorama.json"]:
        p = comp_dir / name
        default = [] if name != "panorama.json" else {"nodes": [], "edges": [], "meta": {}}
        p.write_text(json.dumps(default, ensure_ascii=False), encoding="utf-8")

    import app.services.competition_core as svc

    monkeypatch.setattr(svc, "_DATA_DIR", comp_dir, raising=True)
    monkeypatch.setattr(svc, "_DISCOVERIES_PATH", comp_dir / "discoveries.json", raising=True)
    monkeypatch.setattr(svc, "_REVIEWS_PATH", comp_dir / "reviews.json", raising=True)
    monkeypatch.setattr(svc, "_ROLES_PATH", comp_dir / "roles.json", raising=True)
    monkeypatch.setattr(svc, "_PANORAMA_PATH", comp_dir / "panorama.json", raising=True)

    from fastapi import FastAPI
    from app.api.routes.competition_core import router

    app = FastAPI()
    app.include_router(router)

    from fastapi.testclient import TestClient
    return TestClient(app)


class TestHttpCreate:
    """HTTP POST /api/competition/discoveries tests."""

    BASE = "/api/competition/discoveries"

    def test_create_returns_201(self, client):
        name = _unique_name()
        resp = client.post(self.BASE, json={
            "name": name,
            "responsibilities": ["设计架构", "编写代码"],
            "required_skills": ["Python"],
            "bonus_skills": [],
            "application_scenarios": [],
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == name
        assert body["review_status"] == "pending"
        assert "id" in body

    def test_response_matches_discovery_item(self, client):
        name = _unique_name()
        resp = client.post(self.BASE, json={
            "name": name,
            "responsibilities": ["R"],
        })
        assert resp.status_code == 201
        body = resp.json()
        # Check all DiscoveryItem fields are present
        for key in ["id", "name", "confidence", "growth_rate", "source_count",
                     "responsibilities", "required_skills", "bonus_skills",
                     "application_scenarios", "source_ids", "review_status",
                     "reviewed_at", "source_note", "created_at"]:
            assert key in body, f"Missing field: {key}"

    def test_appears_in_list_after_create(self, client):
        name = _unique_name()
        client.post(self.BASE, json={"name": name, "responsibilities": ["R"]})

        resp = client.get(self.BASE)
        assert resp.status_code == 200
        data = resp.json()
        found = [it for it in data["items"] if it["name"] == name]
        assert len(found) == 1

    def test_duplicate_returns_409(self, client):
        name = _unique_name()
        r1 = client.post(self.BASE, json={"name": name, "responsibilities": ["R"]})
        assert r1.status_code == 201

        r2 = client.post(self.BASE, json={"name": name, "responsibilities": ["R2"]})
        assert r2.status_code == 409
        detail = r2.json().get("detail", "")
        assert "已存在" in detail
        assert name in detail

    def test_empty_name_returns_422(self, client):
        resp = client.post(self.BASE, json={"name": "", "responsibilities": ["R"]})
        assert resp.status_code == 422

    def test_whitespace_name_returns_422(self, client):
        resp = client.post(self.BASE, json={"name": "   ", "responsibilities": ["R"]})
        assert resp.status_code == 422

    def test_empty_responsibilities_returns_422(self, client):
        resp = client.post(self.BASE, json={"name": _unique_name(), "responsibilities": []})
        assert resp.status_code == 422

    def test_whitespace_responsibilities_returns_422(self, client):
        resp = client.post(self.BASE, json={"name": _unique_name(), "responsibilities": ["  ", "\t"]})
        assert resp.status_code == 422

    def test_name_too_long_returns_422(self, client):
        resp = client.post(self.BASE, json={
            "name": "A" * 201,
            "responsibilities": ["R"],
        })
        assert resp.status_code == 422

    def test_too_many_responsibilities_returns_422(self, client):
        resp = client.post(self.BASE, json={
            "name": _unique_name(),
            "responsibilities": ["R"] * 21,
        })
        assert resp.status_code == 422

    def test_too_many_skills_returns_422(self, client):
        resp = client.post(self.BASE, json={
            "name": _unique_name(),
            "responsibilities": ["R"],
            "required_skills": ["s"] * 31,
        })
        assert resp.status_code == 422

    def test_default_status_is_pending(self, client):
        name = _unique_name()
        resp = client.post(self.BASE, json={"name": name, "responsibilities": ["R"]})
        assert resp.status_code == 201
        assert resp.json()["review_status"] == "pending"

    def test_422_error_structure(self, client):
        """FastAPI 422 should include reachable error info (detail array or errors array)."""
        # Whitespace-only triggers field_validator → custom handler → {errors:[...]}
        resp = client.post(self.BASE, json={"name": "   ", "responsibilities": ["R"]})
        assert resp.status_code == 422
        body = resp.json()
        # Accept either: errors array (custom handler) or detail array (standard FastAPI)
        has_errors = isinstance(body.get("errors"), list) and len(body["errors"]) > 0
        has_detail_list = isinstance(body.get("detail"), list) and len(body["detail"]) > 0
        assert has_errors or has_detail_list, (
            f"Body has no parseable error info: {json.dumps(body)}"
        )

    def test_source_note_present(self, client):
        name = _unique_name()
        resp = client.post(self.BASE, json={
            "name": name,
            "responsibilities": ["R"],
            "source_note": "来自HR推荐",
        })
        assert resp.status_code == 201
        assert resp.json().get("source_note") == "来自HR推荐"

    def test_source_note_defaults(self, client):
        name = _unique_name()
        resp = client.post(self.BASE, json={"name": name, "responsibilities": ["R"]})
        assert resp.status_code == 201
        assert resp.json().get("source_note") == "人工录入"

    def test_created_at_present(self, client):
        name = _unique_name()
        resp = client.post(self.BASE, json={"name": name, "responsibilities": ["R"]})
        assert resp.status_code == 201
        assert resp.json().get("created_at") is not None


class TestHttpReviewAfterCreate:
    """Verify the existing review endpoint still works after manual creation."""

    def test_review_after_create(self, client):
        name = _unique_name()
        r = client.post("/api/competition/discoveries", json={"name": name, "responsibilities": ["R"]})
        disc_id = r.json()["id"]

        rev = client.post(f"/api/competition/discoveries/{disc_id}/review", json={
            "status": "approved",
            "editor": "test-http",
        })
        assert rev.status_code == 201
        assert rev.json()["status"] == "approved"

        # Verify discovery was updated
        updated = client.get("/api/competition/discoveries")
        found = [it for it in updated.json()["items"] if it["id"] == disc_id]
        assert len(found) == 1
        assert found[0]["review_status"] == "approved"

    def test_list_reviews_after_create(self, client):
        name = _unique_name()
        r = client.post("/api/competition/discoveries", json={"name": name, "responsibilities": ["R"]})
        disc_id = r.json()["id"]

        client.post(f"/api/competition/discoveries/{disc_id}/review", json={
            "status": "approved",
            "editor": "tester",
        })

        reviews = client.get(f"/api/competition/discoveries/{disc_id}/reviews")
        assert reviews.status_code == 200
        assert isinstance(reviews.json(), list)
        assert len(reviews.json()) >= 1


class TestHttpList:
    """Verify GET /discoveries works with filter."""

    def test_list_with_filter(self, client):
        # Create a pending record
        name = _unique_name()
        client.post("/api/competition/discoveries", json={"name": name, "responsibilities": ["R"]})

        # Filter by pending
        resp = client.get("/api/competition/discoveries?status=pending")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(it["review_status"] == "pending" for it in items)
        assert any(it["name"] == name for it in items)

        # Filter by approved (should not contain our record)
        resp2 = client.get("/api/competition/discoveries?status=approved")
        assert resp2.status_code == 200
        items2 = resp2.json()["items"]
        assert not any(it["name"] == name for it in items2)
