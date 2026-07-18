"""Tests for the Company Agent adapter layer.

All tests use mock providers — no real company API is ever called.
"""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.company_agent import _get_provider
from app.schemas.company_agent import (
    CompanyAgentEvaluateRequest,
    CompanyAgentEvaluateResponse,
    CompanyAgentHealthResponse,
)
from app.services.company_agent import (
    CompanyAgentProvider,
    DisabledCompanyAgentProvider,
    HttpCompanyAgentProvider,
    get_company_agent_provider,
)


# ======================================================================
# Mock Providers
# ======================================================================


class MockSuccessProvider(CompanyAgentProvider):
    """Returns a valid success response."""

    async def evaluate(self, request: CompanyAgentEvaluateRequest) -> CompanyAgentEvaluateResponse:
        return CompanyAgentEvaluateResponse(
            status="success",
            request_id=request.request_id,
            trace_id="mock-trace-001",
            agent_score=82,
            recommendation="建议面试",
            summary="候选人整体匹配度较高，核心技能覆盖良好。",
            strengths=["Java 5年经验", "Spring Boot 精通"],
            risks=["缺少云原生项目经验"],
            skill_gaps=["Kubernetes", "Docker"],
            dimensions=[
                {"name": "技术能力", "score": 85},
                {"name": "项目经验", "score": 80},
            ],
            evidence=[
                {"type": "skill_match", "description": "Java 技能与岗位要求高度匹配"},
                {"type": "gap", "description": "缺少 K8s 相关经验"},
            ],
            provider="http",
            model="company-model-v2",
            latency_ms=1240,
        )

    async def health(self) -> CompanyAgentHealthResponse:
        return CompanyAgentHealthResponse(
            enabled=True,
            configured=True,
            status="healthy",
            provider="http",
            endpoint_configured=True,
        )


class MockTimeoutProvider(CompanyAgentProvider):
    """Simulates a timeout."""

    async def evaluate(self, request: CompanyAgentEvaluateRequest) -> CompanyAgentEvaluateResponse:
        return CompanyAgentEvaluateResponse(
            status="failed",
            request_id=request.request_id,
            provider="http",
            latency_ms=30000,
            summary="timeout after 30s",
        )

    async def health(self) -> CompanyAgentHealthResponse:
        return CompanyAgentHealthResponse(
            enabled=True, configured=True, status="degraded",
            provider="http", endpoint_configured=True,
        )


class MockAuthFailProvider(CompanyAgentProvider):
    """Simulates 401."""

    async def evaluate(self, request: CompanyAgentEvaluateRequest) -> CompanyAgentEvaluateResponse:
        return CompanyAgentEvaluateResponse(
            status="failed",
            request_id=request.request_id,
            provider="http",
            latency_ms=200,
            summary="authentication failed (401)",
        )

    async def health(self) -> CompanyAgentHealthResponse:
        return CompanyAgentHealthResponse(
            enabled=True, configured=True, status="degraded",
            provider="http", endpoint_configured=True,
        )


class MockForbiddenProvider(CompanyAgentProvider):
    """Simulates 403."""

    async def evaluate(self, request: CompanyAgentEvaluateRequest) -> CompanyAgentEvaluateResponse:
        return CompanyAgentEvaluateResponse(
            status="failed",
            request_id=request.request_id,
            provider="http",
            latency_ms=200,
            summary="access forbidden (403)",
        )

    async def health(self) -> CompanyAgentHealthResponse:
        return CompanyAgentHealthResponse(
            enabled=True, configured=True, status="degraded",
            provider="http", endpoint_configured=True,
        )


class MockRateLimitedProvider(CompanyAgentProvider):
    """Simulates 429."""

    async def evaluate(self, request: CompanyAgentEvaluateRequest) -> CompanyAgentEvaluateResponse:
        return CompanyAgentEvaluateResponse(
            status="failed",
            request_id=request.request_id,
            provider="http",
            latency_ms=3000,
            summary="rate limited (429)",
        )

    async def health(self) -> CompanyAgentHealthResponse:
        return CompanyAgentHealthResponse(
            enabled=True, configured=True, status="degraded",
            provider="http", endpoint_configured=True,
        )


class MockServerErrorProvider(CompanyAgentProvider):
    """Simulates 500."""

    async def evaluate(self, request: CompanyAgentEvaluateRequest) -> CompanyAgentEvaluateResponse:
        return CompanyAgentEvaluateResponse(
            status="failed",
            request_id=request.request_id,
            provider="http",
            latency_ms=500,
            summary="upstream server error (500)",
        )

    async def health(self) -> CompanyAgentHealthResponse:
        return CompanyAgentHealthResponse(
            enabled=True, configured=True, status="degraded",
            provider="http", endpoint_configured=True,
        )


class MockInvalidJsonProvider(CompanyAgentProvider):
    """Returns a response with an out-of-range score."""

    async def evaluate(self, request: CompanyAgentEvaluateRequest) -> CompanyAgentEvaluateResponse:
        return CompanyAgentEvaluateResponse(
            status="success",
            request_id=request.request_id,
            agent_score=999,  # out of range — should be caught
            provider="http",
            latency_ms=50,
        )

    async def health(self) -> CompanyAgentHealthResponse:
        return CompanyAgentHealthResponse(
            enabled=True, configured=True, status="healthy",
            provider="http", endpoint_configured=True,
        )


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def valid_payload():
    return {
        "candidate_name": "张三",
        "resume_text": "5 years of Java development with Spring Boot...",
        "job_id": "backend",
        "job_title": "高级后端工程师",
        "job_description": "负责后端服务开发与维护",
        "required_skills": ["Java", "Spring Boot", "MySQL"],
        "local_score": 78,
        "local_dimensions": {"技术能力": 80, "项目经验": 75},
        "request_id": "test-req-001",
    }


# ======================================================================
# Test: Disabled provider
# ======================================================================


class TestDisabledProvider:
    def test_health_disabled(self, client):
        """Health should report disabled when provider is disabled."""
        resp = client.get("/api/company-agent/health")
        assert resp.status_code == 200
        data = resp.json()
        # Default: not configured → should be disabled
        assert data["enabled"] is False
        assert data["endpoint_configured"] is False

    def test_evaluate_returns_disabled(self, client, valid_payload):
        """Evaluate should return status=disabled when no agent is configured."""
        resp = client.post("/api/company-agent/evaluate", json=valid_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disabled"
        assert data["agent_score"] is None
        assert data["provider"] == "disabled"

    def test_evaluate_does_not_return_fake_score(self, client, valid_payload):
        """When disabled, agent_score must be null, never 0."""
        resp = client.post("/api/company-agent/evaluate", json=valid_payload)
        data = resp.json()
        assert data["agent_score"] is None
        # agent_score should NOT be 0 (which could be mistaken for a real score)
        assert data["agent_score"] != 0


# ======================================================================
# Test: Success
# ======================================================================


class TestSuccess:
    def test_evaluate_success(self, client, valid_payload):
        """Full success path with mock provider."""
        app.dependency_overrides[_get_provider] = lambda: MockSuccessProvider()
        try:
            resp = client.post("/api/company-agent/evaluate", json=valid_payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"
            assert data["agent_score"] == 82
            assert data["recommendation"] == "建议面试"
            assert len(data["strengths"]) == 2
            assert len(data["risks"]) == 1
            assert len(data["skill_gaps"]) == 2
            assert len(data["dimensions"]) == 2
            assert len(data["evidence"]) == 2
            assert data["provider"] == "http"
            assert data["model"] == "company-model-v2"
            assert data["latency_ms"] >= 0
            assert data["trace_id"] == "mock-trace-001"
            assert data["request_id"] == "test-req-001"
        finally:
            app.dependency_overrides.pop(_get_provider, None)

    def test_health_when_configured(self, client):
        """Health should report healthy when provider returns healthy."""
        app.dependency_overrides[_get_provider] = lambda: MockSuccessProvider()
        try:
            resp = client.get("/api/company-agent/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["enabled"] is True
            assert data["status"] == "healthy"
            assert data["endpoint_configured"] is True
            # Must not leak API key
            assert "api_key" not in data
            assert "token" not in data
            assert "key" not in data
        finally:
            app.dependency_overrides.pop(_get_provider, None)

    def test_score_in_valid_range(self, client, valid_payload):
        """Agent score should be within 0-100."""
        app.dependency_overrides[_get_provider] = lambda: MockSuccessProvider()
        try:
            resp = client.post("/api/company-agent/evaluate", json=valid_payload)
            data = resp.json()
            score = data["agent_score"]
            assert 0 <= score <= 100
        finally:
            app.dependency_overrides.pop(_get_provider, None)


# ======================================================================
# Test: Error scenarios
# ======================================================================


class TestErrors:
    def test_timeout(self, client, valid_payload):
        """Timeout should result in status=failed."""
        app.dependency_overrides[_get_provider] = lambda: MockTimeoutProvider()
        try:
            resp = client.post("/api/company-agent/evaluate", json=valid_payload)
            assert resp.status_code == 200  # Not 500
            data = resp.json()
            assert data["status"] == "failed"
            assert data["agent_score"] is None
        finally:
            app.dependency_overrides.pop(_get_provider, None)

    def test_401(self, client, valid_payload):
        """401 should result in status=failed."""
        app.dependency_overrides[_get_provider] = lambda: MockAuthFailProvider()
        try:
            resp = client.post("/api/company-agent/evaluate", json=valid_payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "failed"
        finally:
            app.dependency_overrides.pop(_get_provider, None)

    def test_403(self, client, valid_payload):
        """403 should result in status=failed."""
        app.dependency_overrides[_get_provider] = lambda: MockForbiddenProvider()
        try:
            resp = client.post("/api/company-agent/evaluate", json=valid_payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "failed"
        finally:
            app.dependency_overrides.pop(_get_provider, None)

    def test_429(self, client, valid_payload):
        """429 should result in status=failed."""
        app.dependency_overrides[_get_provider] = lambda: MockRateLimitedProvider()
        try:
            resp = client.post("/api/company-agent/evaluate", json=valid_payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "failed"
        finally:
            app.dependency_overrides.pop(_get_provider, None)

    def test_500(self, client, valid_payload):
        """500 should result in status=failed."""
        app.dependency_overrides[_get_provider] = lambda: MockServerErrorProvider()
        try:
            resp = client.post("/api/company-agent/evaluate", json=valid_payload)
            assert resp.status_code == 200  # Not propagated as 500
            data = resp.json()
            assert data["status"] == "failed"
        finally:
            app.dependency_overrides.pop(_get_provider, None)


# ======================================================================
# Test: Validation
# ======================================================================


class TestValidation:
    def test_missing_required_field(self, client):
        """Missing resume_text should cause validation error."""
        payload = {
            "job_id": "backend",
            "job_title": "高级后端工程师",
            "local_score": 78,
            "request_id": "test-001",
        }
        resp = client.post("/api/company-agent/evaluate", json=payload)
        assert resp.status_code == 422  # FastAPI validation error

    def test_local_score_out_of_range(self, client):
        """local_score above 100 should be rejected."""
        payload = {
            "resume_text": "test resume text content...",
            "job_id": "backend",
            "job_title": "高级后端工程师",
            "local_score": 150,  # out of range
            "request_id": "test-001",
        }
        resp = client.post("/api/company-agent/evaluate", json=payload)
        assert resp.status_code == 422

    def test_local_score_negative(self, client):
        """Negative local_score should be rejected."""
        payload = {
            "resume_text": "test resume text content...",
            "job_id": "backend",
            "job_title": "高级后端工程师",
            "local_score": -5,
            "request_id": "test-001",
        }
        resp = client.post("/api/company-agent/evaluate", json=payload)
        assert resp.status_code == 422

    def test_agent_score_out_of_range_rejected(self):
        """Pydantic model should reject score > 100."""
        with pytest.raises(ValueError, match="agent_score must be 0–100"):
            CompanyAgentEvaluateResponse(
                status="success",
                request_id="test",
                agent_score=999,
                provider="http",
                latency_ms=10,
            )

    def test_agent_score_negative_rejected(self):
        """Pydantic model should reject negative score."""
        with pytest.raises(ValueError, match="agent_score must be 0–100"):
            CompanyAgentEvaluateResponse(
                status="success",
                request_id="test",
                agent_score=-1,
                provider="http",
                latency_ms=10,
            )

    def test_strengths_wrong_type_rejected(self):
        """Non-string items in strengths should be rejected."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CompanyAgentEvaluateResponse(
                status="success",
                request_id="test",
                strengths=[123, "valid"],  # 123 is not a string
                provider="http",
                latency_ms=10,
            )

    def test_evidence_wrong_type_rejected(self):
        """Non-dict items in evidence should be rejected."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CompanyAgentEvaluateResponse(
                status="success",
                request_id="test",
                evidence=["not a dict", 123],
                provider="http",
                latency_ms=10,
            )


# ======================================================================
# Test: Security — sensitive data not in responses
# ======================================================================


class TestSecurity:
    def test_health_does_not_leak_api_key(self, client):
        """Health endpoint must never return API keys or tokens."""
        resp = client.get("/api/company-agent/health")
        assert resp.status_code == 200
        data = resp.json()
        # Recursively check for sensitive key names
        text = json.dumps(data).lower()
        for sensitive in ("api_key", "token", "secret", "password", "bearer"):
            assert sensitive not in text, f"Leaked '{sensitive}' in health response"

    def test_evaluate_response_does_not_leak_key(self, client, valid_payload):
        """Evaluate response must never return API keys."""
        app.dependency_overrides[_get_provider] = lambda: MockSuccessProvider()
        try:
            resp = client.post("/api/company-agent/evaluate", json=valid_payload)
            data = resp.json()
            text = json.dumps(data).lower()
            assert "api_key" not in text
            assert "token" not in text
        finally:
            app.dependency_overrides.pop(_get_provider, None)


# ======================================================================
# Test: Local scoring unaffected by agent failure
# ======================================================================


class TestIsolation:
    def test_agent_failure_does_not_affect_response(self, client, valid_payload):
        """When agent fails, the response should still be a clean failed status,
        not a 500 — the frontend can safely display local score."""
        app.dependency_overrides[_get_provider] = lambda: MockServerErrorProvider()
        try:
            resp = client.post("/api/company-agent/evaluate", json=valid_payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "failed"
            assert "request_id" in data
            assert "evaluated_at" in data
        finally:
            app.dependency_overrides.pop(_get_provider, None)

    def test_disabled_provider_does_not_block(self, client, valid_payload):
        """Disabled provider should return quickly."""
        resp = client.post("/api/company-agent/evaluate", json=valid_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disabled"
        assert data["latency_ms"] == 0


# ======================================================================
# Test: DisabledCompanyAgentProvider
# ======================================================================


class TestDisabledProviderUnit:
    def test_evaluate_disabled(self):
        async def _run():
            provider = DisabledCompanyAgentProvider()
            req = CompanyAgentEvaluateRequest(
                resume_text="test resume",
                job_id="j1",
                job_title="Engineer",
                local_score=80,
                request_id="r1",
            )
            return await provider.evaluate(req)
        resp = asyncio.run(_run())
        assert resp.status == "disabled"
        assert resp.agent_score is None

    def test_health_disabled(self):
        async def _run():
            provider = DisabledCompanyAgentProvider()
            return await provider.health()
        health = asyncio.run(_run())
        assert health.enabled is False
        assert health.configured is False
        assert health.status == "disabled"
        assert health.endpoint_configured is False


# ======================================================================
# Test: Request / response models
# ======================================================================


class TestModels:
    def test_valid_request_minimal(self):
        req = CompanyAgentEvaluateRequest(
            resume_text="Resume content here...",
            job_id="j1",
            job_title="Dev",
            local_score=75,
            request_id="r1",
        )
        assert req.candidate_name is None
        assert req.job_description is None
        assert req.required_skills == []
        assert req.local_dimensions == {}

    def test_valid_request_full(self):
        req = CompanyAgentEvaluateRequest(
            candidate_id="c1",
            candidate_name="Alice",
            resume_text="Many years of experience...",
            job_id="j1",
            job_title="Senior Dev",
            job_description="Lead the team",
            required_skills=["Python", "Go"],
            local_score=85,
            local_dimensions={"tech": 90, "exp": 80},
            request_id="abc-123",
        )
        assert req.candidate_name == "Alice"
        assert len(req.required_skills) == 2

    def test_response_serialization(self):
        resp = CompanyAgentEvaluateResponse(
            status="success",
            request_id="r1",
            trace_id="tr1",
            agent_score=90,
            recommendation="Hire",
            summary="Good match",
            strengths=["Strong Python"],
            risks=["No Go experience"],
            skill_gaps=["Go"],
            dimensions=[{"name": "tech", "score": 90.0}],
            provider="http",
            model="v2",
            latency_ms=500,
        )
        d = resp.model_dump()
        assert d["status"] == "success"
        assert d["agent_score"] == 90
        assert d["dimensions"][0]["name"] == "tech"


# ======================================================================
# Test: Logging (sensitive data)
# ======================================================================


class TestLogging:
    def test_redact_api_key(self, caplog):
        """API key should be redacted in log output."""
        from app.services.company_agent import _redact_key
        caplog.set_level(logging.INFO, logger="app.services.company_agent")
        key = "sk-abcdefgh12345678"
        redacted = _redact_key(key)
        assert "****" in redacted
        assert redacted != key
        assert len(redacted) < len(key) + 8  # roughly

    def test_sanitize_long_text(self):
        """Sanitize should truncate long text."""
        from app.services.company_agent import _sanitize
        long_text = "x" * 500
        result = _sanitize(long_text, max_len=120)
        # The result length should be max_len + truncation marker (approx)
        assert "truncated" in result
        assert len(result) <= 150  # generous upper bound
        assert "truncated" in result
