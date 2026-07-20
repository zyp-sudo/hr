"""Global exception handlers that return consistent JSON error bodies."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("xh.api")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logger.warning("HTTP %s on %s %s — %s", exc.status_code, request.method, request.url.path, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Validation error on %s %s — %s", request.method, request.url.path, exc.errors())
    # Sanitize errors: remove non-JSON-serializable exception objects from ctx
    clean_errors: list[dict[str, Any]] = []
    for e in exc.errors():
        clean: dict[str, Any] = {}
        for k, v in e.items():
            if k == "ctx" and isinstance(v, dict):
                # Keep ctx but strip the 'error' key (contains a non-serializable ValueError)
                safe_ctx = {ck: cv for ck, cv in v.items() if ck != "error"}
                if safe_ctx:
                    clean["ctx"] = safe_ctx
            elif k != "ctx":
                clean[k] = v
        clean_errors.append(clean)
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "status": 422,
            "detail": "Request validation failed",
            "errors": clean_errors,
            "path": request.url.path,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "status": 500,
            "detail": "Internal server error",
            "path": request.url.path,
        },
    )
