"""Company Agent — REST endpoints.

Provides
--------
- ``GET  /api/company-agent/health``   — status (no secrets exposed)
- ``POST /api/company-agent/evaluate`` — invoke the company agent
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from app.schemas.company_agent import (
    CompanyAgentEvaluateRequest,
    CompanyAgentEvaluateResponse,
    CompanyAgentHealthResponse,
)
from app.services.company_agent import (
    CompanyAgentProvider,
    get_company_agent_provider,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/company-agent", tags=["company-agent"])


def _get_provider() -> CompanyAgentProvider:
    """Resolve the current provider — overridable in tests."""
    return get_company_agent_provider()


@router.get("/health", response_model=CompanyAgentHealthResponse)
async def health(
    request: Request,
    provider: CompanyAgentProvider = Depends(_get_provider),
) -> CompanyAgentHealthResponse:
    """Health check — never returns API keys or tokens.

    Example response when **disabled**::

        {
          "enabled": false,
          "configured": false,
          "status": "disabled",
          "provider": "disabled",
          "endpoint_configured": false
        }

    Example when **enabled but unreachable**::

        {
          "enabled": true,
          "configured": true,
          "status": "degraded",
          "provider": "http",
          "endpoint_configured": true
        }
    """
    return await provider.health()


@router.post("/evaluate", response_model=CompanyAgentEvaluateResponse)
async def evaluate(
    payload: CompanyAgentEvaluateRequest,
    request: Request,
    provider: CompanyAgentProvider = Depends(_get_provider),
) -> CompanyAgentEvaluateResponse:
    """Ask the company agent for an enhanced score.

    Returns ``status: "disabled"`` when the agent is not configured.

    Returns ``status: "failed"`` on timeout, 401, 403, 429, 5xx, or
    malformed upstream responses — the local assessment is **never**
    affected by this call.

    ---
    **Example request**::

        POST /api/company-agent/evaluate
        {
          "candidate_name": "张三",
          "resume_text": "5 years of Java…",
          "job_id": "backend",
          "job_title": "高级后端工程师",
          "local_score": 78,
          "local_dimensions": {"技术能力": 80},
          "request_id": "abc123"
        }

    **Example success response**::

        {
          "status": "success",
          "request_id": "abc123",
          "trace_id": "trace-xyz",
          "agent_score": 82,
          "recommendation": "建议面试",
          "summary": "候选人整体匹配度较高…",
          "strengths": ["Java 经验丰富"],
          "risks": ["缺少云原生经验"],
          "skill_gaps": ["Kubernetes"],
          "dimensions": [{"name": "技术能力", "score": 85}],
          "evidence": [{"type": "skill_match", "description": "Java 5yr"}],
          "provider": "http",
          "model": "company-model-v2",
          "latency_ms": 1240,
          "evaluated_at": "2026-07-17T12:00:00+00:00"
        }

    **Disabled response**::

        {
          "status": "disabled",
          "request_id": "abc123",
          "agent_score": null,
          "provider": "disabled",
          "latency_ms": 0
        }
    """
    # Use middleware request-id if the caller didn't provide one
    if not payload.request_id:
        payload.request_id = getattr(request.state, "request_id", "unknown")

    logger.info(
        "Company agent evaluate request_id=%s candidate=%s job=%s local_score=%d",
        payload.request_id,
        payload.candidate_name or "(anon)",
        payload.job_title,
        payload.local_score,
    )

    try:
        result = await provider.evaluate(payload)
    except Exception as exc:
        logger.exception(
            "Company agent provider raised exception request_id=%s",
            payload.request_id,
        )
        result = CompanyAgentEvaluateResponse(
            status="failed",
            request_id=payload.request_id,
            provider="http",
            latency_ms=0,
            summary=f"provider error: {type(exc).__name__}",
        )

    logger.info(
        "Company agent evaluate done request_id=%s status=%s score=%s latency=%dms",
        result.request_id,
        result.status,
        result.agent_score,
        result.latency_ms,
    )

    return result
