"""Tests for competition evidence-based generation and hallucination prevention.

Covers four mandatory scenarios:
1. Claims WITH evidence → supported, source_ids populated
2. Claims WITHOUT evidence → blocked_claims, cannot publish
3. Low confidence → needs_review flag
4. Service unavailable → graceful degradation, built-in fallback

Route-level tests use a minimal FastAPI app (not the full app) because
the competition_rag router is intentionally NOT registered in ``router.py``
and the full app's catch-all proxy would intercept unregistered routes.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.competition_rag import router as competition_router
from app.schemas.competition_rag import EvidenceGenerateRequest
from app.services.competition_rag import (
    CONFIDENCE_THRESHOLD,
    CompetitionRAGService,
    MilvusEvidenceRetriever,
    Neo4jEvidenceRetriever,
)


# ======================================================================
# Helpers
# ======================================================================


def _minimal_evidence() -> dict:
    """Evidence with a few known competencies for deterministic testing."""
    return {
        "version": "1.0.0",
        "competencies": [
            {
                "id": "comp_python",
                "name": "Python",
                "category": "skill",
                "aliases": ["python3", "py", "Python编程"],
                "job_count": 5000,
                "source_files": ["data/etl/unified_job_skills.csv"],
                "related_roles": ["software-engineer"],
                "confidence": 0.95,
            },
            {
                "id": "comp_java",
                "name": "Java",
                "category": "skill",
                "aliases": ["java8", "spring"],
                "job_count": 6000,
                "source_files": ["data/etl/unified_job_skills.csv"],
                "related_roles": ["software-engineer", "backend-engineer"],
                "confidence": 0.95,
            },
            {
                "id": "comp_sql",
                "name": "SQL",
                "category": "skill",
                "aliases": ["mysql", "数据库"],
                "job_count": 7000,
                "source_files": ["data/etl/unified_job_skills.csv"],
                "related_roles": ["software-engineer", "data-analyst"],
                "confidence": 0.92,
            },
            {
                "id": "comp_comm",
                "name": "沟通能力",
                "category": "requirement",
                "aliases": ["团队协作", "沟通"],
                "job_count": 3000,
                "source_files": ["data/etl/unified_job_skills.csv"],
                "related_roles": ["software-engineer"],
                "confidence": 0.70,
            },
            {
                "id": "comp_ml",
                "name": "机器学习",
                "category": "skill",
                "aliases": ["Machine Learning", "深度学习"],
                "job_count": 1500,
                "source_files": ["data/etl/unified_job_skills.csv"],
                "related_roles": ["algorithm-engineer"],
                "confidence": 0.80,
            },
        ],
        "roles": [
            {
                "id": "software-engineer",
                "name": "软件工程师",
                "aliases": ["SWE"],
                "typical_skills": ["comp_python", "comp_java", "comp_sql"],
                "typical_requirements": ["comp_comm"],
            }
        ],
    }


def _make_service(
    evidence: dict | None = None,
    audit_dir: str | Path | None = None,
    milvus=None,
    neo4j_graph=None,
) -> CompetitionRAGService:
    """Create a service backed by a temporary evidence file."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(evidence or _minimal_evidence(), tmp)
    tmp.close()

    audit_path = Path(audit_dir or tempfile.mkdtemp()) / "rag_audit.jsonl"

    return CompetitionRAGService(
        evidence_path=tmp.name,
        audit_path=audit_path,
        milvus=milvus,
        neo4j_graph=neo4j_graph,
    )


def _test_app(service: CompetitionRAGService | None = None) -> TestClient:
    """Minimal FastAPI app with only the competition_rag router (standalone)."""
    test_app = FastAPI()

    # Wire the service dependency
    if service is not None:
        from app.api.routes.competition_rag import _get_service

        test_app.dependency_overrides[_get_service] = lambda: service

    test_app.include_router(competition_router)
    return TestClient(test_app)


# ======================================================================
# Scenario 1: claims WITH evidence → supported
# ======================================================================


def test_evidence_supported_claims():
    """Claims matching known competencies should be supported with source_ids."""
    svc = _make_service()
    result = svc.generate(
        EvidenceGenerateRequest(
            role_id="software-engineer",
            question="请评估该候选人的技术能力是否符合软件工程师岗位要求",
            candidate_claims=[
                "精通Python编程，有5年开发经验",
                "熟悉Java和Spring框架",
                "具备SQL数据库开发能力",
            ],
        )
    )

    assert len(result.claims) == 3
    assert all(c.supported for c in result.claims)
    assert all(len(c.source_ids) > 0 for c in result.claims)
    assert len(result.blocked_claims) == 0
    assert result.confidence > CONFIDENCE_THRESHOLD
    assert result.mode == "offline"
    assert len(result.audit_id) == 16

    assert "✅" in result.answer
    assert "证据型评估报告" in result.answer


def test_evidence_supported_via_route():
    """Same scenario exercised through the HTTP route (minimal test app)."""
    svc = _make_service()
    client = _test_app(svc)
    resp = client.post(
        "/api/competition/rag/generate",
        json={
            "role_id": "software-engineer",
            "question": "评估技术能力",
            "candidate_claims": ["精通Python编程", "熟悉Java开发", "掌握SQL"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["claims"]) == 3
    assert len(data["blocked_claims"]) == 0
    assert data["confidence"] > CONFIDENCE_THRESHOLD
    assert data["mode"] == "offline"


# ======================================================================
# Scenario 2: claims WITHOUT evidence → blocked_claims (cannot publish)
# ======================================================================


def test_evidence_blocked_claims_no_sources():
    """Claims with zero source_ids MUST go to blocked_claims."""
    svc = _make_service()
    result = svc.generate(
        EvidenceGenerateRequest(
            role_id="software-engineer",
            question="评估",
            candidate_claims=[
                "精通Rust编程语言，有10年系统编程经验",
                "具备量子计算研究背景",
                "拥有FAA飞行执照",
            ],
        )
    )

    assert len(result.claims) == 0
    assert len(result.blocked_claims) == 3
    for bc in result.blocked_claims:
        assert bc.supported is False
        assert bc.source_ids == []
        assert bc.needs_review is True
        assert bc.confidence == 0.0

    assert result.confidence == 0.0
    assert "🚫" in result.answer


def test_evidence_blocked_via_route():
    """Blocked-claim scenario through HTTP."""
    svc = _make_service()
    client = _test_app(svc)
    resp = client.post(
        "/api/competition/rag/generate",
        json={
            "role_id": "software-engineer",
            "question": "评估",
            "candidate_claims": ["精通Rust编程", "量子计算经验", "飞行执照"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["claims"]) == 0
    assert len(data["blocked_claims"]) == 3
    assert data["confidence"] == 0.0


# ======================================================================
# Scenario 3: low confidence → needs_review
# ======================================================================


def test_low_confidence_needs_review():
    """Partial matches with confidence below threshold should be flagged."""
    evidence = _minimal_evidence()
    evidence["competencies"][0]["confidence"] = 0.40
    evidence["competencies"][2]["confidence"] = 0.45

    svc = _make_service(evidence=evidence)
    result = svc.generate(
        EvidenceGenerateRequest(
            role_id="software-engineer",
            question="评估",
            candidate_claims=["会一点Python", "了解SQL"],
        ),
    )

    if result.claims:
        for c in result.claims:
            if c.confidence < CONFIDENCE_THRESHOLD:
                assert c.needs_review is True

    assert result.confidence < CONFIDENCE_THRESHOLD
    assert "需人工复核" in result.answer


def test_mixed_confidence_partial_blocked():
    """Mix of strong, weak, and no-evidence claims."""
    svc = _make_service()
    result = svc.generate(
        EvidenceGenerateRequest(
            role_id="software-engineer",
            question="综合评估",
            candidate_claims=[
                "精通Python",  # strong match
                "具备沟通能力",  # moderate match
                "精通Rust语言",  # no evidence
            ],
        ),
    )

    assert len(result.claims) >= 1
    assert len(result.blocked_claims) >= 1

    rust_blocked = [b for b in result.blocked_claims if "Rust" in b.text]
    assert len(rust_blocked) == 1
    assert rust_blocked[0].source_ids == []


# ======================================================================
# Scenario 4: service unavailable → graceful degradation
# ======================================================================


def test_service_graceful_fallback_missing_evidence_file():
    """When evidence_sources.json is missing, service loads CSV or built-in fallback."""
    svc = CompetitionRAGService(
        evidence_path="/nonexistent/path/evidence_sources.json",
        audit_path=Path(tempfile.mkdtemp()) / "rag_audit.jsonl",
    )
    # Must have loaded some competencies (either from CSV or built-in)
    assert len(svc._comp_by_id) > 0

    # Should still work for common claims
    result = svc.generate(
        EvidenceGenerateRequest(
            role_id="software-engineer",
            question="评估",
            candidate_claims=["精通Python编程"],
        ),
    )
    assert len(result.claims) == 1
    assert result.claims[0].supported is True


def test_service_corrupt_evidence_file_fallback():
    """Corrupt JSON should trigger CSV or built-in fallback."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    tmp.write("{this is not valid json [[[")
    tmp.close()

    svc = CompetitionRAGService(
        evidence_path=tmp.name,
        audit_path=Path(tempfile.mkdtemp()) / "rag_audit.jsonl",
    )
    # Must have loaded some competencies
    assert len(svc._comp_by_id) > 0

    result = svc.generate(
        EvidenceGenerateRequest(
            role_id="software-engineer",
            question="评估",
            candidate_claims=["熟悉Git版本控制"],
        ),
    )
    # Should find Git evidence or at minimum not crash
    assert result.audit_id


def test_route_503_on_service_exception():
    """HTTP 503 when the service layer raises an unexpected exception."""
    svc = _make_service()
    client = _test_app(svc)

    with patch.object(
        CompetitionRAGService, "generate", side_effect=RuntimeError("simulated crash")
    ):
        resp = client.post(
            "/api/competition/rag/generate",
            json={
                "role_id": "swe",
                "question": "test",
                "candidate_claims": ["test claim"],
            },
        )
        assert resp.status_code == 503
        data = resp.json()
        assert "detail" in data


# ======================================================================
# Audit trail
# ======================================================================


def test_audit_record_written():
    """Each generate call must write an audit record to JSONL."""
    audit_dir = tempfile.mkdtemp()
    svc = _make_service(audit_dir=audit_dir)
    result = svc.generate(
        EvidenceGenerateRequest(
            role_id="software-engineer",
            question="评估Python能力",
            candidate_claims=["精通Python"],
        ),
    )

    audit_file = Path(audit_dir) / "rag_audit.jsonl"
    assert audit_file.exists()

    lines = audit_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) >= 1

    record = json.loads(lines[-1])
    assert record["audit_id"] == result.audit_id
    assert record["mode"] == "offline"
    assert record["request_summary"]["role_id"] == "software-engineer"
    assert record["results"]["supported_count"] == 1
    assert record["results"]["blocked_count"] == 0


# ======================================================================
# Edge cases
# ======================================================================


def test_empty_claims_list_validation():
    """Request validation should reject empty candidate_claims."""
    client = _test_app(_make_service())
    resp = client.post(
        "/api/competition/rag/generate",
        json={
            "role_id": "swe",
            "question": "test",
            "candidate_claims": [],
        },
    )
    assert resp.status_code == 422


def test_missing_required_fields():
    """Request without role_id should fail validation."""
    client = _test_app(_make_service())
    resp = client.post(
        "/api/competition/rag/generate",
        json={
            "question": "test",
            "candidate_claims": ["claim"],
        },
    )
    assert resp.status_code == 422


def test_health_endpoint():
    """Health endpoint returns source metadata — all paths are safe filenames only."""
    audit_dir = tempfile.mkdtemp()
    svc = _make_service(audit_dir=audit_dir)

    # Explicitly inject every path shape that _safe_name must handle,
    # independently of the host OS.
    svc._sources_used = [
        r"C:\Users\name\windows-backslash.json",    # Windows backslash abs
        "C:/Users/name/windows-forward.json",        # Windows forward-slash abs
        "/tmp/unix-abs.json",                         # Unix absolute
        "data/etl/relative.json",                     # POSIX relative
        "plain-name.json",                            # bare filename
        "built-in",                                   # non-path identifier
    ]

    client = _test_app(svc)
    resp = client.get("/api/competition/rag/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["competencies_indexed"] > 0
    # audit_path must be the bare filename, never an absolute path
    assert data["audit_path"] == "rag_audit.jsonl"
    assert "/" not in data["audit_path"]
    assert "\\" not in data["audit_path"]
    # Every injected path must reduce to the bare filename or stay unchanged
    expected = [
        "windows-backslash.json",
        "windows-forward.json",
        "unix-abs.json",
        "relative.json",
        "plain-name.json",
        "built-in",
    ]
    assert data["sources_loaded"] == expected
    # No entry in the whole response body should contain a path separator
    raw_text = resp.text
    assert "C:\\" not in raw_text
    assert "C:/" not in raw_text
    assert "/tmp/" not in raw_text
    assert "data/etl/" not in raw_text
    # The specific temp directory must not leak anywhere in the response
    assert audit_dir not in raw_text, "Temporary directory leaked in health response"


def test_health_endpoint_no_absolute_path_leak():
    """Health response must never expose absolute paths, usernames, or temp dirs."""
    audit_dir = tempfile.mkdtemp()
    svc = _make_service(audit_dir=audit_dir)

    # Another explicit set covering edge cases
    svc._sources_used = [
        r"D:\Projects\secret\key.json",
        "/home/user/secret.json",
        "C:/Users/name/Projects/secret.json",
        "sub/deep/nested/file.csv",
        "just-a-name",
        "built-in",
    ]

    client = _test_app(svc)
    resp = client.get("/api/competition/rag/health")
    assert resp.status_code == 200
    data = resp.json()
    raw_text = resp.text

    import re
    # No Windows absolute paths  (C:\…  D:\…)
    assert not re.search(r"[A-Za-z]:\\\\", raw_text), (
        "Windows absolute path leaked in health response"
    )
    # No Unix absolute paths
    assert "/home/" not in raw_text, "Unix /home/ path leaked"
    assert "/Users/" not in raw_text, "Unix /Users/ path leaked"
    assert "/tmp/" not in raw_text, "Unix /tmp/ path leaked"
    # No relative path segments
    assert "data/etl/" not in raw_text, "Relative path leaked"
    assert "sub/deep/" not in raw_text, "Relative path leaked"
    # No tempfile prefix leaked
    assert tempfile.gettempdir() not in raw_text, (
        "System temp directory leaked in health response"
    )
    # Verify the specific temp directory is NOT present
    assert audit_dir not in raw_text, "Temporary directory leaked in health response"

    # Every entry must be a safe bare name
    for entry in data["sources_loaded"]:
        assert "\\" not in entry, f"Backslash leaked: {entry}"
        assert "/" not in entry, f"Forward slash leaked: {entry}"


def test_answer_marks_non_llm():
    """The answer must clearly state it is NOT an LLM output."""
    svc = _make_service()
    result = svc.generate(
        EvidenceGenerateRequest(
            role_id="software-engineer",
            question="评估",
            candidate_claims=["精通Python"],
        ),
    )
    assert "非大语言模型输出" in result.answer or "自动生成" in result.answer


def test_claim_with_multiple_source_ids():
    """A claim matching multiple competencies should aggregate source_ids."""
    svc = _make_service()
    result = svc.generate(
        EvidenceGenerateRequest(
            role_id="software-engineer",
            question="评估",
            candidate_claims=["精通Python和Java开发"],
        ),
    )
    assert len(result.claims) == 1
    claim = result.claims[0]
    assert len(claim.source_ids) >= 2
    assert claim.supported is True


def test_confidence_boost_for_role_relevant_evidence():
    """Evidence related to the requested role should get a confidence boost."""
    svc = _make_service()
    result_sw = svc.generate(
        EvidenceGenerateRequest(
            role_id="software-engineer",
            question="评估",
            candidate_claims=["机器学习"],
        ),
    )
    result_algo = svc.generate(
        EvidenceGenerateRequest(
            role_id="algorithm-engineer",
            question="评估",
            candidate_claims=["机器学习"],
        ),
    )

    assert len(result_sw.claims) == 1
    assert len(result_algo.claims) == 1
    assert result_algo.claims[0].confidence >= result_sw.claims[0].confidence


def test_deterministic_output():
    """Same input should produce identical confidence and audit structure."""
    svc = _make_service()
    req = EvidenceGenerateRequest(
        role_id="software-engineer",
        question="确定性测试",
        candidate_claims=["精通Python", "熟悉Java"],
    )
    r1 = svc.generate(req)
    r2 = svc.generate(req)

    assert r1.confidence == r2.confidence
    assert len(r1.claims) == len(r2.claims)
    assert len(r1.blocked_claims) == len(r2.blocked_claims)
    assert r1.audit_id != r2.audit_id


def test_milvus_neo4j_optional_interfaces():
    """Milvus and Neo4j retrievers should gracefully return empty on None."""
    milvus = MilvusEvidenceRetriever(None)
    assert milvus.search("test") == []

    neo4j = Neo4jEvidenceRetriever(None)
    assert neo4j.related_subgraph(["test"]) == {
        "nodes": [],
        "edges": [],
        "storage": "neo4j",
    }


def test_milvus_neo4j_graceful_on_exception():
    """Retrievers should catch exceptions and return empty."""
    failing_store = MagicMock()
    failing_store.search.side_effect = ConnectionError("milvus down")
    milvus = MilvusEvidenceRetriever(failing_store)
    assert milvus.search("test") == []

    failing_graph = MagicMock()
    failing_graph.related_subgraph.side_effect = ConnectionError("neo4j down")
    neo4j = Neo4jEvidenceRetriever(failing_graph)
    assert neo4j.related_subgraph(["test"]) == {
        "nodes": [],
        "edges": [],
        "storage": "neo4j",
    }


# ======================================================================
# Tokenization / embedding helpers
# ======================================================================


def test_tokenize_chinese_english():
    from app.services.competition_rag import _tokenize

    tokens = _tokenize("精通Python编程和Java开发")
    assert "python" in tokens
    assert "java" in tokens


def test_cosine_similarity():
    from app.services.competition_rag import _cosine_similarity

    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert 0.6 < _cosine_similarity([1.0, 1.0], [1.0, 0.5]) < 1.0


def test_hash_embed_deterministic():
    from app.services.competition_rag import _hash_embed

    v1 = _hash_embed("Python programming")
    v2 = _hash_embed("Python programming")
    assert v1 == v2
    assert len(v1) == 128
    assert abs(sum(x * x for x in v1) - 1.0) < 0.0001
