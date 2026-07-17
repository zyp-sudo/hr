"""Request middleware — ID, timing, and structured access logging."""

from __future__ import annotations

import time
import uuid
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a unique request-id and measure wall-clock latency.

    Injects ``X-Request-ID`` into the response and logs every request as one
    structured line at INFO level so observability tooling can ingest it
    without parsing multi-line traces.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        # Expose request-id to route handlers via request.state
        request.state.request_id = request_id

        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-ms"] = f"{elapsed_ms:.1f}"

        logger.info(
            "%-6s  %3s  %-7s  %s%s",
            request.method,
            response.status_code,
            f"{elapsed_ms:.0f}ms",
            request.url.path,
            f"?{request.url.query}" if request.url.query else "",
        )
        return response
