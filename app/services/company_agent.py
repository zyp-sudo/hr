"""Company Agent provider abstraction and concrete implementations.

Exports
-------
- ``CompanyAgentProvider``   — abstract base class
- ``DisabledCompanyAgentProvider`` — always returns ``disabled``
- ``HttpCompanyAgentProvider`` — calls the real company agent API
- ``get_company_agent_provider()`` — factory that picks the right impl
"""

from __future__ import annotations

import abc
import asyncio
import json
import logging
import time
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.schemas.company_agent import (
    CompanyAgentEvaluateRequest,
    CompanyAgentEvaluateResponse,
    CompanyAgentHealthResponse,
    CompanyAgentUpstreamResponse,
)

logger = logging.getLogger(__name__)

# ── helpers ────────────────────────────────────────────────────────────


def _sanitize(text: str, max_len: int = 120) -> str:
    """Truncate for safe logging — never log full resume text or tokens."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"…[{len(text) - max_len} chars truncated]"


def _redact_key(key: str) -> str:
    """Return a redacted version of an API key suitable for logging."""
    if not key:
        return "<empty>"
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "****" + key[-4:]


# ── abstract provider ──────────────────────────────────────────────────


class CompanyAgentProvider(abc.ABC):
    """Contract that every company-agent adapter must fulfill."""

    @abc.abstractmethod
    async def evaluate(
        self, request: CompanyAgentEvaluateRequest
    ) -> CompanyAgentEvaluateResponse:
        """Return a validated, normalized evaluation result."""

    @abc.abstractmethod
    async def health(self) -> CompanyAgentHealthResponse:
        """Return health status — never exposes secrets."""


# ── disabled provider (default) ────────────────────────────────────────


class DisabledCompanyAgentProvider(CompanyAgentProvider):
    """Provider used when the company agent is not configured.

    Always returns ``disabled`` — no network calls, no fake scores.
    """

    async def evaluate(
        self, request: CompanyAgentEvaluateRequest
    ) -> CompanyAgentEvaluateResponse:
        logger.info(
            "Company agent disabled — skipping evaluation request_id=%s",
            request.request_id,
        )
        return CompanyAgentEvaluateResponse(
            status="disabled",
            request_id=request.request_id,
            provider="disabled",
            latency_ms=0,
        )

    async def health(self) -> CompanyAgentHealthResponse:
        settings = get_settings()
        return CompanyAgentHealthResponse(
            enabled=settings.company_agent_enabled,
            configured=False,
            status="disabled",
            provider="disabled",
            endpoint_configured=False,
        )


# ── HTTP provider ──────────────────────────────────────────────────────


class HttpCompanyAgentProvider(CompanyAgentProvider):
    """Talks to the real company agent API over HTTPS.

    - Timeout, retry, and error mapping are all handled here.
    - API key is sent as ``Authorization: Bearer <key>``.
    - The upstream response body is validated with Pydantic *before*
      it enters the normalised response model.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._base = settings.company_agent_base_url.rstrip("/")
        self._api_key = settings.company_agent_api_key
        self._timeout = settings.company_agent_timeout_seconds
        self._max_retries = max(0, min(settings.company_agent_max_retries, 3))
        self._client = client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def evaluate(
        self, request: CompanyAgentEvaluateRequest
    ) -> CompanyAgentEvaluateResponse:
        t0 = time.perf_counter()
        url = f"{self._base}/evaluate"

        payload = self._build_payload(request)
        headers = self._auth_headers()
        headers.setdefault("Content-Type", "application/json")

        logger.info(
            "Company agent → POST %s  request_id=%s  resume_len=%d",
            url,
            request.request_id,
            len(request.resume_text),
        )

        last_error: str | None = None
        last_status: int | None = None

        for attempt in range(self._max_retries + 1):
            try:
                if attempt > 0:
                    await asyncio.sleep(min(2 ** (attempt - 1), 4))
                    logger.info(
                        "Company agent retry %d/%d request_id=%s",
                        attempt,
                        self._max_retries,
                        request.request_id,
                    )

                client = self._client or httpx.AsyncClient(
                    timeout=httpx.Timeout(self._timeout)
                )
                should_close = self._client is None

                try:
                    resp = await client.post(url, json=payload, headers=headers)
                finally:
                    if should_close:
                        await client.aclose()

                elapsed_ms = int((time.perf_counter() - t0) * 1000)

                if resp.is_success:
                    return self._handle_success(
                        resp, request.request_id, elapsed_ms
                    )

                # -- map HTTP errors -----------------------------------
                last_status = resp.status_code
                raw_body = resp.text[:500]
                last_error = self._map_http_error(resp.status_code, raw_body)

                # 4xx errors are not retried
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    break

            except httpx.TimeoutException:
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                last_error = f"timeout after {self._timeout}s"
                logger.warning(
                    "Company agent timeout request_id=%s attempt=%d/%d",
                    request.request_id,
                    attempt,
                    self._max_retries + 1,
                )
            except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                last_error = f"connection failed: {type(exc).__name__}"
                logger.warning(
                    "Company agent connection error request_id=%s: %s",
                    request.request_id,
                    exc,
                )
            except Exception as exc:
                last_error = f"unexpected: {type(exc).__name__}"
                logger.exception(
                    "Company agent unexpected error request_id=%s",
                    request.request_id,
                )
                break  # don't retry unexpected errors

        # All attempts exhausted
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return CompanyAgentEvaluateResponse(
            status="failed",
            request_id=request.request_id,
            provider="http",
            latency_ms=elapsed_ms,
            summary=last_error or "unknown error",
        )

    async def health(self) -> CompanyAgentHealthResponse:
        settings = get_settings()
        base_health = CompanyAgentHealthResponse(
            enabled=settings.company_agent_enabled,
            configured=bool(settings.company_agent_base_url),
            status="healthy",
            provider="http",
            endpoint_configured=bool(settings.company_agent_base_url),
        )

        if not settings.company_agent_base_url:
            base_health.status = "degraded"
            return base_health

        # Try a quick ping to the remote
        try:
            url = f"{self._base}/health"
            client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(10))
            should_close = self._client is None
            try:
                resp = await client.get(url, headers=self._auth_headers())
                if resp.is_success:
                    base_health.status = "healthy"
                else:
                    base_health.status = "degraded"
            finally:
                if should_close:
                    await client.aclose()
        except Exception:
            base_health.status = "degraded"

        return base_health

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_payload(self, request: CompanyAgentEvaluateRequest) -> dict[str, Any]:
        """Construct the upstream request body.

        NOTE: We intentionally only forward the fields the company agent
        needs.  Raw resume text, phone numbers, emails etc. are NOT sent
        unless they are part of the resume_text (which the user consented
        to share).
        """
        return {
            "request_id": request.request_id,
            "candidate_id": request.candidate_id,
            "candidate_name": request.candidate_name,
            "resume_text": request.resume_text,
            "job_id": request.job_id,
            "job_title": request.job_title,
            "job_description": request.job_description or "",
            "required_skills": request.required_skills,
            "local_score": request.local_score,
            "local_dimensions": request.local_dimensions,
        }

    def _auth_headers(self) -> dict[str, str]:
        """Return Authorization header — never logged at this level."""
        if not self._api_key:
            return {}
        return {"Authorization": f"Bearer {self._api_key}"}

    def _map_http_error(self, status_code: int, body: str) -> str:
        """Human-readable error from HTTP status."""
        _body = _sanitize(body, 200)
        if status_code == 401:
            return f"authentication failed (401)"
        if status_code == 403:
            return f"access forbidden (403)"
        if status_code == 429:
            return f"rate limited (429)"
        if 500 <= status_code < 600:
            return f"upstream server error ({status_code}): {_body}"
        return f"HTTP {status_code}: {_body}"

    def _handle_success(
        self,
        resp: httpx.Response,
        request_id: str,
        elapsed_ms: int,
    ) -> CompanyAgentEvaluateResponse:
        """Parse, validate, and normalise a 2xx upstream response."""
        raw_text = resp.text

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Company agent returned invalid JSON request_id=%s: %s",
                request_id,
                exc,
            )
            return CompanyAgentEvaluateResponse(
                status="failed",
                request_id=request_id,
                provider="http",
                latency_ms=elapsed_ms,
                summary=f"invalid JSON response: {_sanitize(str(exc), 180)}",
            )

        # Validate upstream shape
        try:
            upstream = CompanyAgentUpstreamResponse(**data)
        except Exception as exc:
            logger.warning(
                "Company agent response validation failed request_id=%s: %s",
                request_id,
                exc,
            )
            return CompanyAgentEvaluateResponse(
                status="failed",
                request_id=request_id,
                provider="http",
                latency_ms=elapsed_ms,
                summary=f"response validation failed: {_sanitize(str(exc), 200)}",
            )

        # Build normalised response
        return CompanyAgentEvaluateResponse(
            status="success",
            request_id=request_id,
            trace_id=upstream.trace_id,
            agent_score=upstream.score,
            recommendation=upstream.recommendation,
            summary=upstream.summary,
            strengths=upstream.strengths,
            risks=upstream.risks,
            skill_gaps=upstream.skill_gaps,
            dimensions=[
                {"name": d.get("name", "unknown"), "score": float(d.get("score", 0))}
                for d in upstream.dimensions
            ] if upstream.dimensions else [],
            evidence=[
                {"type": d.get("type", ""), "description": d.get("description", "")}
                for d in upstream.evidence
            ] if upstream.evidence else [],
            provider="http",
            model=upstream.model,
            latency_ms=elapsed_ms,
        )


# ── factory ─────────────────────────────────────────────────────────────


def get_company_agent_provider() -> CompanyAgentProvider:
    """Return the configured provider.

    - ``COMPANY_AGENT_ENABLED=false`` → ``DisabledCompanyAgentProvider``
    - ``COMPANY_AGENT_ENABLED=true`` + valid URL → ``HttpCompanyAgentProvider``
    - ``COMPANY_AGENT_ENABLED=true`` but no URL → ``DisabledCompanyAgentProvider``
      (logs a warning at import time)
    """
    settings = get_settings()

    if not settings.company_agent_enabled:
        return DisabledCompanyAgentProvider()

    if not settings.company_agent_base_url:
        logger.warning(
            "COMPANY_AGENT_ENABLED=true but COMPANY_AGENT_BASE_URL is empty — "
            "falling back to disabled provider"
        )
        return DisabledCompanyAgentProvider()

    logger.info(
        "Company agent provider initialised: url=%s  timeout=%ds  retries=%d  key=%s",
        settings.company_agent_base_url,
        settings.company_agent_timeout_seconds,
        settings.company_agent_max_retries,
        _redact_key(settings.company_agent_api_key),
    )
    return HttpCompanyAgentProvider(settings)
