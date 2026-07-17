"""Catch-all reverse proxy to the legacy Java backend (port 8081).

This router MUST be included last so it never shadows concrete
``/api/*``, ``/docs``, or ``/`` routes.  It is excluded from the
OpenAPI schema to keep generated docs clean.
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.request

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(include_in_schema=False)

# ---------------------------------------------------------------------------
# Well-known paths that should never be forwarded (explicit safety net)
# ---------------------------------------------------------------------------
_NEVER_PROXY: frozenset[str] = frozenset({
    "",
    "docs",
    "redoc",
    "openapi.json",
})


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy_legacy_java(path: str, request: Request) -> Response:
    """Forward unmatched requests to the Java analytical backend."""
    if path in _NEVER_PROXY:
        return JSONResponse(
            status_code=404,
            content={"error": True, "status": 404, "detail": f"Route not found: /{path}"},
        )

    settings = get_settings()
    target_url = f"{settings.java_backend_url.rstrip('/')}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    body = await request.body()
    headers: dict[str, str] = {}
    content_type = request.headers.get("content-type")
    if content_type:
        headers["Content-Type"] = content_type

    logger.debug("Proxy → %s %s", request.method, target_url)

    try:
        proxy_req = urllib.request.Request(
            target_url,
            data=body or None,
            headers=headers,
            method=request.method,
        )
        with urllib.request.urlopen(proxy_req, timeout=settings.proxy_timeout) as upstream:
            return Response(
                content=upstream.read(),
                status_code=upstream.status,
                media_type=upstream.headers.get_content_type(),
            )
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read()
        return Response(
            content=body_bytes,
            status_code=exc.code,
            media_type="application/json",
        )
    except urllib.error.URLError as exc:
        detail = f"Java analytical service unavailable: {exc.reason}"
        logger.warning("Proxy unreachable: %s", exc.reason)
        return JSONResponse(
            status_code=503,
            content={"error": True, "status": 503, "detail": detail},
        )
