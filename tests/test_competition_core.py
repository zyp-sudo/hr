"""Competition Core — isolated unit tests.

ALL tests use temporary data directories.  The four module‑level path
constants in ``app.services.competition_core`` are patched individually
so writes never reach the production ``data/competition/`` tree.

Production data files are SHA256‑verified at module teardown.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Production data locations
# ---------------------------------------------------------------------------

_PROD_DATA = Path(__file__).resolve().parents[1] / "data" / "competition"
_PROD_FILES = ["discoveries.json", "roles.json", "reviews.json", "panorama.json"]


def _sha256(path: Path) -> str:
    if not path.exists():
        return "FILE_NOT_FOUND"
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Capture production hashes at import time (before any test runs)
_PROD_HASHES_BEFORE: dict[str, str] = {
    f: _sha256(_PROD_DATA / f) for f in _PROD_FILES
}


# ---------------------------------------------------------------------------
# Module‑scoped isolated data directory
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def isolated_data_dir():
    """Copy production JSON files into a temp directory and patch all four
    ``competition_core._*_PATH`` constants so every test in this module uses
    the copies."""
    import app.services.competition_core as svc

    tmp_dir = Path(tempfile.mkdtemp(prefix="comp_core_test_"))
    for fname in _PROD_FILES:
        src = _PROD_DATA / fname
        if src.exists():
            shutil.copy2(src, tmp_dir / fname)
        else:
            placeholder = "[]" if fname != "panorama.json" else '{"nodes":[],"edges":[],"meta":{}}'
            (tmp_dir / fname).write_text(placeholder, encoding="utf-8")

    # Patch every module‑level path constant — _DATA_DIR alone is useless
    patches = [
        patch.object(svc, "_DISCOVERIES_PATH", tmp_dir / "discoveries.json"),
        patch.object(svc, "_ROLES_PATH", tmp_dir / "roles.json"),
        patch.object(svc, "_REVIEWS_PATH", tmp_dir / "reviews.json"),
        patch.object(svc, "_PANORAMA_PATH", tmp_dir / "panorama.json"),
    ]
    for p in patches:
        p.start()

    yield tmp_dir

    for p in patches:
        p.stop()
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Standalone TestClient (read‑only routes) — depends on isolated_data
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client(isolated_data_dir):
    """FastAPI TestClient with only competition_core routes, backed by temp data."""
    from app.api.routes.competition_core import router as competition_router

    app = FastAPI()
    app.include_router(competition_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Convenience: get a service reference with isolated paths
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def svc(isolated_data_dir):
    import app.services.competition_core as _svc
    return _svc


# =============================================================================
# 1) GET /api/competition/discoveries
# =============================================================================


class TestListDiscoveries:
    def test_returns_all_discoveries(self, client):
        resp = client.get("/api/competition/discoveries")
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "items" in body
        assert body["total"] == len(body["items"])
        assert body["total"] >= 3

    def test_items_have_required_fields(self, client):
        resp = client.get("/api/competition/discoveries")
        for item in resp.json()["items"]:
            assert "id" in item
            assert "name" in item
            assert isinstance(item["confidence"], (int, float))
            assert 0.0 <= item["confidence"] <= 1.0
            assert "growth_rate" in item
            assert "source_count" in item
            assert "responsibilities" in item and isinstance(item["responsibilities"], list)
            assert "required_skills" in item and isinstance(item["required_skills"], list)
            assert "bonus_skills" in item and isinstance(item["bonus_skills"], list)
            assert "application_scenarios" in item
            assert "source_ids" in item and isinstance(item["source_ids"], list)
            assert item["review_status"] in ("pending", "approved", "rejected")

    def test_sorted_by_confidence_desc(self, client):
        resp = client.get("/api/competition/discoveries")
        items = resp.json()["items"]
        confidences = [it["confidence"] for it in items]
        assert confidences == sorted(confidences, reverse=True)

    def test_filter_by_status(self, client):
        resp = client.get("/api/competition/discoveries?status=approved")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["review_status"] == "approved"

    def test_filter_by_status_pending(self, client):
        resp = client.get("/api/competition/discoveries?status=pending")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["review_status"] == "pending"

    def test_invalid_status_rejected(self, client):
        resp = client.get("/api/competition/discoveries?status=invalid")
        assert resp.status_code == 422

    def test_ai_agent_engineer_exists(self, client):
        resp = client.get("/api/competition/discoveries")
        names = [it["name"] for it in resp.json()["items"]]
        assert "AI Agent工程师" in names

    def test_skills_have_source_ids(self, client):
        resp = client.get("/api/competition/discoveries")
        for item in resp.json()["items"]:
            for skill in item["required_skills"]:
                assert "source_ids" in skill
                assert len(skill["source_ids"]) > 0
            for skill in item["bonus_skills"]:
                assert "source_ids" in skill
                assert len(skill["source_ids"]) > 0


# =============================================================================
# 2) POST /api/competition/discoveries/{id}/review  (write tests use isolated)
# =============================================================================


class TestReviewDiscovery:
    def test_reject_a_pending_discovery(self, svc):
        review = svc.create_review(
            discovery_id="llm-ops-engineer",
            status="rejected",
            editor="test-admin",
            comment="暂不符合正式岗位标准",
        )
        assert review["discovery_id"] == "llm-ops-engineer"
        assert review["status"] == "rejected"
        assert review["review_id"].startswith("rev-")
        assert review["created_at"] is not None

    def test_review_stores_edits(self, svc):
        review = svc.create_review(
            discovery_id="ai-agent-engineer",
            status="approved",
            editor="expert-zhang",
            edits={
                "required_skills": [
                    {"name": "Python", "level": "expert", "source_ids": ["src-manual-review-001"]},
                    {"name": "Agent框架设计", "level": "expert", "source_ids": ["src-manual-review-001"]},
                ],
            },
            comment="补充Agent框架设计",
        )
        assert review["edits"] is not None
        assert "required_skills" in review["edits"]

    def test_review_updates_discovery_status(self, svc):
        svc.create_review(
            discovery_id="ai-agent-engineer",
            status="approved",
            editor="admin",
            comment="通过审核",
        )
        item = svc.get_discovery("ai-agent-engineer")
        assert item["review_status"] == "approved"
        assert item["reviewed_at"] is not None

    def test_review_nonexistent_discovery(self, svc):
        assert svc.get_discovery("nonexistent-id") is None

    def test_list_reviews_for_discovery(self, svc):
        reviews = svc.list_reviews(discovery_id="ai-agent-engineer")
        assert isinstance(reviews, list)
        for rev in reviews:
            assert rev["discovery_id"] == "ai-agent-engineer"


# =============================================================================
# 3) GET /api/competition/roles/{role_id}/versions
# =============================================================================


class TestRoleVersions:
    def test_java_developer_has_two_versions(self, client):
        resp = client.get("/api/competition/roles/java-developer/versions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["role_id"] == "java-developer"
        assert body["name"] == "Java开发工程师"
        assert len(body["versions"]) >= 2

    def test_version_structure_complete(self, client):
        resp = client.get("/api/competition/roles/java-developer/versions")
        for ver in resp.json()["versions"]:
            assert "version_id" in ver
            assert "timestamp" in ver
            assert "source" in ver
            assert "skills" in ver and isinstance(ver["skills"], list)
            assert "responsibilities" in ver
            assert "source_ids" in ver

    def test_version_skills_have_source_ids(self, client):
        resp = client.get("/api/competition/roles/java-developer/versions")
        for ver in resp.json()["versions"]:
            for skill in ver["skills"]:
                assert "source_ids" in skill
                assert len(skill["source_ids"]) > 0

    def test_nonexistent_role_returns_404(self, client):
        resp = client.get("/api/competition/roles/ghost-role/versions")
        assert resp.status_code == 404

    def test_data_scientist_has_two_versions(self, client):
        resp = client.get("/api/competition/roles/data-scientist/versions")
        assert resp.status_code == 200
        assert len(resp.json()["versions"]) >= 2


# =============================================================================
# 4) GET /api/competition/roles/{role_id}/diff
# =============================================================================


class TestRoleDiff:
    def test_java_v1_to_v2_diff(self, client):
        resp = client.get(
            "/api/competition/roles/java-developer/diff",
            params={"from_version": "v1", "to_version": "v2"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["role_id"] == "java-developer"
        assert body["from_version"] == "v1"
        assert body["to_version"] == "v2"
        added_names = [d["name"] for d in body["added"]]
        assert len(added_names) > 0

    def test_diff_items_have_source_ids_and_reason(self, client):
        resp = client.get(
            "/api/competition/roles/java-developer/diff",
            params={"from_version": "v1", "to_version": "v2"},
        )
        body = resp.json()
        for item in body["added"]:
            assert "source_ids" in item and len(item["source_ids"]) > 0
            assert "reason" in item and item["reason"]
        for item in body["modified"]:
            assert "source_ids" in item and len(item["source_ids"]) > 0
            assert "reason" in item and item["reason"]

    def test_same_version_returns_400(self, client):
        resp = client.get(
            "/api/competition/roles/java-developer/diff",
            params={"from_version": "v1", "to_version": "v1"},
        )
        assert resp.status_code == 400

    def test_nonexistent_role_diff_returns_404(self, client):
        resp = client.get(
            "/api/competition/roles/nonexistent/diff",
            params={"from_version": "v1", "to_version": "v2"},
        )
        assert resp.status_code == 404

    def test_nonexistent_version_returns_404(self, client):
        resp = client.get(
            "/api/competition/roles/java-developer/diff",
            params={"from_version": "v1", "to_version": "v99"},
        )
        assert resp.status_code == 404

    def test_data_scientist_v1_to_v2_diff(self, client):
        resp = client.get(
            "/api/competition/roles/data-scientist/diff",
            params={"from_version": "v1", "to_version": "v2"},
        )
        assert resp.status_code == 200
        added_names = [d["name"] for d in resp.json()["added"]]
        assert "LLM应用开发" in added_names or "深度学习" in added_names


# =============================================================================
# 5) GET /api/competition/panorama
# =============================================================================


class TestPanorama:
    def test_returns_full_panorama(self, client):
        resp = client.get("/api/competition/panorama")
        assert resp.status_code == 200
        body = resp.json()
        assert "meta" in body
        assert "nodes" in body
        assert "edges" in body
        assert len(body["nodes"]) > 0
        assert len(body["edges"]) > 0

    def test_nodes_have_required_fields(self, client):
        resp = client.get("/api/competition/panorama")
        for node in resp.json()["nodes"]:
            assert "id" in node
            assert node["type"] in ("role", "skill", "capability")
            assert "label" in node
            assert "source_ids" in node and len(node["source_ids"]) > 0

    def test_edges_have_required_fields(self, client):
        resp = client.get("/api/competition/panorama")
        for edge in resp.json()["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "relation" in edge
            assert edge["relation"] in ("requires", "demonstrates", "related_to")
            assert "source_ids" in edge and len(edge["source_ids"]) > 0

    def test_filter_by_stack_backend(self, client):
        resp = client.get("/api/competition/panorama?stack=backend")
        assert resp.status_code == 200
        role_nodes = [n for n in resp.json()["nodes"] if n["type"] == "role"]
        for rn in role_nodes:
            assert rn.get("stack") == "backend"

    def test_filter_by_stack_ai(self, client):
        resp = client.get("/api/competition/panorama?stack=ai")
        assert resp.status_code == 200
        role_nodes = [n for n in resp.json()["nodes"] if n["type"] == "role"]
        assert len(role_nodes) == 1
        assert role_nodes[0]["label"] == "AI Agent工程师"

    def test_filter_by_level(self, client):
        resp = client.get("/api/competition/panorama?level=mid")
        assert resp.status_code == 200
        role_nodes = [n for n in resp.json()["nodes"] if n["type"] == "role"]
        for rn in role_nodes:
            assert rn.get("level") == "mid"

    def test_filter_by_version(self, client):
        resp = client.get("/api/competition/panorama?version=v2")
        assert resp.status_code == 200
        role_nodes = [n for n in resp.json()["nodes"] if n["type"] == "role"]
        for rn in role_nodes:
            assert rn.get("version") == "v2"

    def test_combined_filter(self, client):
        resp = client.get("/api/competition/panorama?stack=backend&level=mid&version=v2")
        assert resp.status_code == 200
        role_nodes = [n for n in resp.json()["nodes"] if n["type"] == "role"]
        for rn in role_nodes:
            assert rn.get("stack") == "backend"
            assert rn.get("level") == "mid"
            assert rn.get("version") == "v2"

    def test_edges_reference_existing_nodes(self, client):
        resp = client.get("/api/competition/panorama")
        body = resp.json()
        node_ids = {n["id"] for n in body["nodes"]}
        for edge in body["edges"]:
            assert edge["source"] in node_ids
            assert edge["target"] in node_ids


# =============================================================================
# 6) Service‑layer unit tests (all write via isolated paths)
# =============================================================================


class TestServiceLayer:
    def test_list_discoveries_returns_list(self, svc):
        items = svc.list_discoveries()
        assert isinstance(items, list)
        assert len(items) >= 3

    def test_get_discovery_found(self, svc):
        item = svc.get_discovery("ai-agent-engineer")
        assert item is not None
        assert item["name"] == "AI Agent工程师"

    def test_get_discovery_not_found(self, svc):
        assert svc.get_discovery("nonexistent") is None

    def test_get_role_versions_java(self, svc):
        result = svc.get_role_versions("java-developer")
        assert result is not None
        assert len(result["versions"]) >= 2

    def test_get_role_not_found(self, svc):
        assert svc.get_role("ghost") is None

    def test_diff_role_versions(self, svc):
        result = svc.diff_role_versions("java-developer", "v1", "v2")
        assert result is not None
        assert len(result["added"]) > 0

    def test_diff_nonexistent_role(self, svc):
        assert svc.diff_role_versions("ghost", "v1", "v2") is None

    def test_diff_nonexistent_version(self, svc):
        assert svc.diff_role_versions("java-developer", "v1", "v99") is None

    def test_get_panorama_default(self, svc):
        result = svc.get_panorama()
        assert len(result["nodes"]) > 0
        assert len(result["edges"]) > 0

    def test_get_panorama_filtered(self, svc):
        result = svc.get_panorama(stack="ai")
        nodes = result["nodes"]
        role_nodes = [n for n in nodes if n["type"] == "role"]
        assert all(n["stack"] == "ai" for n in role_nodes)

    def test_create_review_traceable(self, svc):
        review = svc.create_review(
            discovery_id="data-governance-engineer",
            status="approved",
            editor="auditor-li",
            comment="可追溯性测试",
        )
        assert review["review_id"].startswith("rev-")
        assert review["editor"] == "auditor-li"
        assert review["created_at"] is not None
        reviews = svc.list_reviews(discovery_id="data-governance-engineer")
        review_ids = [r["review_id"] for r in reviews]
        assert review["review_id"] in review_ids

    def test_create_review_with_edits_updates_discovery(self, svc):
        svc.create_review(
            discovery_id="data-governance-engineer",
            status="approved",
            editor="editor-wang",
            edits={
                "name": "数据治理工程师(修正)",
                "responsibilities": ["更新后的职责1", "更新后的职责2"],
            },
            comment="名称和职责修正",
        )
        item = svc.get_discovery("data-governance-engineer")
        assert item["name"] == "数据治理工程师(修正)"
        assert item["responsibilities"] == ["更新后的职责1", "更新后的职责2"]
        assert item["review_status"] == "approved"
        assert item["reviewed_at"] is not None

    def test_review_edits_partial_update(self, svc):
        item_before = svc.get_discovery("llm-ops-engineer")
        before_bonus = item_before.get("bonus_skills", [])
        svc.create_review(
            discovery_id="llm-ops-engineer",
            status="pending",
            editor="partial-editor",
            edits={"name": "大模型运维工程师(LLMOps)"},
        )
        item_after = svc.get_discovery("llm-ops-engineer")
        assert item_after["name"] == "大模型运维工程师(LLMOps)"
        assert item_after.get("bonus_skills") == before_bonus


# =============================================================================
# 7) Data integrity (read‑only, uses production files directly)
# =============================================================================


class TestDataIntegrity:
    def test_discoveries_json_valid(self):
        data = json.loads((_PROD_DATA / "discoveries.json").read_text("utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_roles_json_valid(self):
        data = json.loads((_PROD_DATA / "roles.json").read_text("utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_reviews_json_valid(self):
        data = json.loads((_PROD_DATA / "reviews.json").read_text("utf-8"))
        assert isinstance(data, list)

    def test_panorama_json_valid(self):
        data = json.loads((_PROD_DATA / "panorama.json").read_text("utf-8"))
        assert "nodes" in data and "edges" in data

    def test_all_discoveries_have_source_ids(self):
        data = json.loads((_PROD_DATA / "discoveries.json").read_text("utf-8"))
        for item in data:
            assert len(item.get("source_ids", [])) > 0
            for skill in item.get("required_skills", []):
                assert len(skill.get("source_ids", [])) > 0

    def test_all_version_skills_have_source_ids(self):
        data = json.loads((_PROD_DATA / "roles.json").read_text("utf-8"))
        for role in data:
            for ver in role.get("versions", []):
                for skill in ver.get("skills", []):
                    assert len(skill.get("source_ids", [])) > 0

    def test_overlapping_skills_between_versions(self, client):
        resp = client.get("/api/competition/roles/java-developer/versions")
        versions = resp.json()["versions"]
        v1_skills = {s["name"] for s in versions[0]["skills"]}
        v2_skills = {s["name"] for s in versions[1]["skills"]}
        common = v1_skills & v2_skills
        assert len(common) > 0


# =============================================================================
# 8) Production data SHA256 verification — ensures isolation actually worked
# =============================================================================


class TestProdDataIntegrity:
    """Verify production data files were never touched by the test suite."""

    def test_discoveries_unchanged(self):
        after = _sha256(_PROD_DATA / "discoveries.json")
        assert after == _PROD_HASHES_BEFORE["discoveries.json"], (
            f"discoveries.json was modified by tests!\n"
            f"  before: {_PROD_HASHES_BEFORE['discoveries.json']}\n"
            f"  after:  {after}"
        )

    def test_roles_unchanged(self):
        after = _sha256(_PROD_DATA / "roles.json")
        assert after == _PROD_HASHES_BEFORE["roles.json"], (
            f"roles.json was modified by tests!"
        )

    def test_reviews_unchanged(self):
        after = _sha256(_PROD_DATA / "reviews.json")
        assert after == _PROD_HASHES_BEFORE["reviews.json"], (
            f"reviews.json was modified by tests!"
        )

    def test_panorama_unchanged(self):
        after = _sha256(_PROD_DATA / "panorama.json")
        assert after == _PROD_HASHES_BEFORE["panorama.json"], (
            f"panorama.json was modified by tests!"
        )
