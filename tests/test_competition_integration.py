"""Competition integration tests — through ``app.main:app``.

All write operations are isolated: the four ``competition_core`` path
constants AND the RAG service's ``audit_path`` / ``evidence_path`` are
patched to point into a temporary data directory.

Production data SHA256 is verified before and after the suite.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Production data locations
# ---------------------------------------------------------------------------

_PROD_DATA = Path(__file__).resolve().parents[1] / "data" / "competition"
_PROD_FILES = [
    "discoveries.json", "roles.json", "reviews.json",
    "panorama.json", "rag_audit.jsonl",
]


def _sha256(path: Path) -> str:
    if not path.exists():
        return "FILE_NOT_FOUND"
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Production hashes captured at import time
_PROD_HASHES_BEFORE: dict[str, str] = {
    f: _sha256(_PROD_DATA / f) for f in _PROD_FILES
}


# ---------------------------------------------------------------------------
# Module‑scoped isolated data + patched paths
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def isolated_data():
    """Copy all production data into a temp directory, then patch
    competition_core path constants AND the RAG service paths so the
    full ``app.main:app`` uses the temp copies."""
    import app.services.competition_core as svc_core
    import app.services.competition_rag as svc_rag

    tmp_dir = Path(tempfile.mkdtemp(prefix="comp_int_test_"))
    data_dir = tmp_dir

    # Copy files
    for fname in _PROD_FILES:
        src = _PROD_DATA / fname
        if src.exists():
            shutil.copy2(src, data_dir / fname)
        else:
            (data_dir / fname).write_text(
                "[]" if fname != "panorama.json" else '{"nodes":[],"edges":[],"meta":{}}',
                encoding="utf-8",
            )

    # Patch competition_core path constants
    core_patches = [
        patch.object(svc_core, "_DISCOVERIES_PATH", data_dir / "discoveries.json"),
        patch.object(svc_core, "_ROLES_PATH", data_dir / "roles.json"),
        patch.object(svc_core, "_REVIEWS_PATH", data_dir / "reviews.json"),
        patch.object(svc_core, "_PANORAMA_PATH", data_dir / "panorama.json"),
    ]

    # Reset and re‑create the RAG singleton so it picks up the temp paths
    svc_rag._service = None
    rag_patches = [
        patch("app.services.competition_rag.PROJECT_ROOT", tmp_dir),
    ]

    all_patches = core_patches + rag_patches
    for p in all_patches:
        p.start()

    # Force RAG service to use temp evidence + audit
    rag_svc = svc_rag.get_competition_rag_service()
    rag_svc.evidence_path = _PROD_DATA / "evidence_sources.json"  # read-only, OK
    rag_svc.audit_path = data_dir / "rag_audit.jsonl"

    yield data_dir

    for p in all_patches:
        p.stop()
    # Reset RAG singleton so later tests see fresh state
    svc_rag._service = None
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# TestClient from app.main:app — depends on isolated_data
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client(isolated_data):
    from app.main import app
    return TestClient(app)


# =============================================================================
# 1) GET /api/competition/discoveries
# =============================================================================


class TestDiscoveriesIntegration:
    def test_status_code_and_structure(self, client):
        resp = client.get("/api/competition/discoveries")
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "items" in body
        assert body["total"] == len(body["items"])
        assert body["total"] >= 3

    def test_items_use_snake_case_fields(self, client):
        resp = client.get("/api/competition/discoveries")
        for item in resp.json()["items"]:
            assert "name" in item
            assert "review_status" in item
            assert "source_ids" in item
            assert "required_skills" in item
            assert "bonus_skills" in item
            assert "application_scenarios" in item
            assert "growth_rate" in item
            assert "confidence" in item

    def test_confidence_is_ratio(self, client):
        resp = client.get("/api/competition/discoveries")
        for item in resp.json()["items"]:
            assert 0.0 <= item["confidence"] <= 1.0
            assert 0.0 <= item["growth_rate"] <= 1.0

    def test_chinese_not_mojibake(self, client):
        resp = client.get("/api/competition/discoveries")
        names = [it["name"] for it in resp.json()["items"]]
        for name in names:
            encoded = name.encode("utf-8")
            decoded = encoded.decode("utf-8")
            assert decoded == name
            assert any("一" <= c <= "鿿" for c in name)

    def test_required_skills_are_objects(self, client):
        resp = client.get("/api/competition/discoveries")
        for item in resp.json()["items"]:
            for skill in item["required_skills"]:
                assert isinstance(skill, dict)
                assert "name" in skill
                assert "source_ids" in skill


# =============================================================================
# 2) POST /api/competition/discoveries/{id}/review
# =============================================================================


class TestReviewIntegration:
    def test_review_creates_record(self, client, isolated_data):
        resp = client.post(
            "/api/competition/discoveries/llm-ops-engineer/review",
            json={
                "status": "approved",
                "editor": "integration-test",
                "comment": "集成测试审核",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["review_id"].startswith("rev-")
        assert body["discovery_id"] == "llm-ops-engineer"
        assert body["status"] == "approved"

        # Verify review persisted (in temp data)
        resp2 = client.get("/api/competition/discoveries/llm-ops-engineer/reviews")
        assert resp2.status_code == 200
        review_ids = [r["review_id"] for r in resp2.json()]
        assert body["review_id"] in review_ids

    def test_review_with_edits(self, client, isolated_data):
        resp = client.post(
            "/api/competition/discoveries/data-governance-engineer/review",
            json={
                "status": "approved",
                "editor": "integration-test",
                "edits": {
                    "name": "数据治理工程师(已审核)",
                    "responsibilities": ["制定数据标准", "数据质量监控"],
                    "required_skills": [
                        {"name": "SQL", "level": "expert", "source_ids": ["src-test-001"]},
                    ],
                },
                "comment": "编辑审核测试",
            },
        )
        assert resp.status_code == 201

    def test_review_missing_editor_returns_422(self, client):
        resp = client.post(
            "/api/competition/discoveries/ai-agent-engineer/review",
            json={"status": "approved"},
        )
        assert resp.status_code == 422

    def test_review_invalid_status_returns_422(self, client):
        resp = client.post(
            "/api/competition/discoveries/ai-agent-engineer/review",
            json={"status": "deleted", "editor": "test"},
        )
        assert resp.status_code == 422

    def test_review_nonexistent_discovery_returns_404(self, client):
        resp = client.post(
            "/api/competition/discoveries/nonexistent-id/review",
            json={"status": "approved", "editor": "test"},
        )
        assert resp.status_code == 404


# =============================================================================
# 3) GET /api/competition/roles/{role_id}/versions
# =============================================================================


class TestRoleVersionsIntegration:
    def test_java_developer_versions(self, client):
        resp = client.get("/api/competition/roles/java-developer/versions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["role_id"] == "java-developer"
        assert body["name"] == "Java开发工程师"
        assert "current_version" in body
        assert len(body["versions"]) >= 2

    def test_version_has_snake_case_fields(self, client):
        resp = client.get("/api/competition/roles/java-developer/versions")
        for ver in resp.json()["versions"]:
            assert "version_id" in ver
            assert "timestamp" in ver
            assert "source" in ver
            assert "responsibilities" in ver
            assert "skills" in ver
            assert "source_ids" in ver

    def test_frontend_developer_exists(self, client):
        resp = client.get("/api/competition/roles/frontend-developer/versions")
        assert resp.status_code == 200

    def test_data_scientist_exists(self, client):
        resp = client.get("/api/competition/roles/data-scientist/versions")
        assert resp.status_code == 200

    def test_chinese_role_name(self, client):
        resp = client.get("/api/competition/roles/java-developer/versions")
        name = resp.json()["name"]
        assert "开发" in name
        name.encode("utf-8").decode("utf-8")


# =============================================================================
# 4) GET /api/competition/roles/{role_id}/diff
# =============================================================================


class TestRoleDiffIntegration:
    def test_diff_uses_from_version_to_version(self, client):
        resp = client.get(
            "/api/competition/roles/java-developer/diff",
            params={"from_version": "v1", "to_version": "v2"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["role_id"] == "java-developer"
        assert body["from_version"] == "v1"
        assert body["to_version"] == "v2"
        assert len(body["added"]) > 0

    def test_diff_old_param_names_rejected(self, client):
        resp = client.get(
            "/api/competition/roles/java-developer/diff",
            params={"from": "v1", "to": "v2"},
        )
        assert resp.status_code == 422

    def test_diff_items_have_reason_and_source_ids(self, client):
        resp = client.get(
            "/api/competition/roles/java-developer/diff",
            params={"from_version": "v1", "to_version": "v2"},
        )
        body = resp.json()
        for item in body["added"]:
            assert "source_ids" in item and len(item["source_ids"]) > 0
            assert "reason" in item and item["reason"]

    def test_same_version_returns_400(self, client):
        resp = client.get(
            "/api/competition/roles/java-developer/diff",
            params={"from_version": "v1", "to_version": "v1"},
        )
        assert resp.status_code == 400


# =============================================================================
# 5) GET /api/competition/panorama
# =============================================================================


class TestPanoramaIntegration:
    def test_panorama_returns_all_sections(self, client):
        resp = client.get("/api/competition/panorama")
        assert resp.status_code == 200
        body = resp.json()
        assert "meta" in body
        assert "nodes" in body
        assert "edges" in body
        assert len(body["nodes"]) > 0
        assert len(body["edges"]) > 0

    def test_meta_has_filter_options(self, client):
        resp = client.get("/api/competition/panorama")
        meta = resp.json()["meta"]
        assert "stacks" in meta
        assert "levels" in meta
        assert "versions" in meta

    def test_nodes_use_role_skill_capability_types(self, client):
        resp = client.get("/api/competition/panorama")
        for node in resp.json()["nodes"]:
            assert node["type"] in ("role", "skill", "capability")
            # Backend never exposes weight, source, trend, children, updatedAt
            assert "weight" not in node
            assert "source" not in node
            assert "trend" not in node

    def test_edges_use_source_target_relation(self, client):
        resp = client.get("/api/competition/panorama")
        for edge in resp.json()["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "relation" in edge
            assert edge["relation"] in ("requires", "demonstrates", "related_to")
            assert "source_ids" in edge
            assert "weight" not in edge
            assert "from" not in edge
            assert "to" not in edge

    def test_edges_source_and_target_exist_in_nodes(self, client):
        resp = client.get("/api/competition/panorama")
        body = resp.json()
        node_ids = {n["id"] for n in body["nodes"]}
        for edge in body["edges"]:
            assert edge["source"] in node_ids, f"边 source={edge['source']} 不在节点列表中"
            assert edge["target"] in node_ids, f"边 target={edge['target']} 不在节点列表中"

    def test_filter_by_stack(self, client):
        resp = client.get("/api/competition/panorama?stack=backend")
        assert resp.status_code == 200

    def test_chinese_labels_in_nodes(self, client):
        resp = client.get("/api/competition/panorama")
        for node in resp.json()["nodes"]:
            node["label"].encode("utf-8").decode("utf-8")


# =============================================================================
# 6) POST /api/competition/rag/generate
# =============================================================================


class TestRAGIntegration:
    def test_generate_returns_claims_with_source_ids(self, client, isolated_data):
        resp = client.post(
            "/api/competition/rag/generate",
            json={
                "role_id": "ai-agent-engineer",
                "question": "AI Agent工程师需要哪些核心技能？",
                "candidate_claims": [
                    "精通Python编程",
                    "具备LLM应用开发经验",
                    "熟悉RAG架构",
                    "完全虚构的不存在技能XYZ-123",
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert "claims" in body
        assert "blocked_claims" in body
        assert "audit_id" in body
        assert "confidence" in body

        for claim in body["claims"]:
            assert "source_ids" in claim
            assert "text" in claim
            assert "supported" in claim

        for claim in body["blocked_claims"]:
            assert claim["supported"] is False
            assert claim["needs_review"] is True

    def test_generate_answer_contains_chinese(self, client, isolated_data):
        resp = client.post(
            "/api/competition/rag/generate",
            json={
                "role_id": "java-developer",
                "question": "Java开发工程师需要哪些核心技能？",
                "candidate_claims": ["Java编程", "Spring Boot开发"],
            },
        )
        assert resp.status_code == 200
        answer = resp.json()["answer"]
        answer.encode("utf-8").decode("utf-8")
        assert len(answer) > 0

    def test_generate_with_empty_claims(self, client):
        resp = client.post(
            "/api/competition/rag/generate",
            json={
                "role_id": "java-developer",
                "question": "测试问题",
                "candidate_claims": [],
            },
        )
        assert resp.status_code == 422


# =============================================================================
# 7) GET /api/competition/rag/audit
# =============================================================================


class TestRAGAuditIntegration:
    def test_audit_returns_records(self, client, isolated_data):
        resp = client.get("/api/competition/rag/audit")
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "items" in body
        assert isinstance(body["items"], list)

    def test_audit_items_have_required_fields(self, client, isolated_data):
        resp = client.get("/api/competition/rag/audit")
        for item in resp.json()["items"]:
            assert "audit_id" in item
            assert "timestamp" in item
            assert "mode" in item


# =============================================================================
# 8) Production data SHA256 verification
# =============================================================================


class TestProdDataIntegrity:
    """Confirm production data files were never mutated by integration tests."""

    def test_discoveries_unchanged(self):
        after = _sha256(_PROD_DATA / "discoveries.json")
        assert after == _PROD_HASHES_BEFORE["discoveries.json"], (
            f"discoveries.json modified!\nBefore: {_PROD_HASHES_BEFORE['discoveries.json']}\nAfter:  {after}"
        )

    def test_roles_unchanged(self):
        after = _sha256(_PROD_DATA / "roles.json")
        assert after == _PROD_HASHES_BEFORE["roles.json"]

    def test_reviews_unchanged(self):
        after = _sha256(_PROD_DATA / "reviews.json")
        assert after == _PROD_HASHES_BEFORE["reviews.json"]

    def test_panorama_unchanged(self):
        after = _sha256(_PROD_DATA / "panorama.json")
        assert after == _PROD_HASHES_BEFORE["panorama.json"]

    def test_rag_audit_unchanged(self):
        after = _sha256(_PROD_DATA / "rag_audit.jsonl")
        assert after == _PROD_HASHES_BEFORE["rag_audit.jsonl"], (
            f"rag_audit.jsonl modified!\nBefore: {_PROD_HASHES_BEFORE['rag_audit.jsonl']}\nAfter:  {after}"
        )
