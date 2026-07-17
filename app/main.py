"""XH-202621 Talent-Match Intelligent Assessment System — FastAPI entry point.

Serves:
- REST API at ``/api/*`` (search, analysis, storage, vectors)
- Swagger docs at ``/docs``
- Health check at ``/api/health``
- Landing page at ``/``
- Catch-all proxy to the legacy Java backend on port 8081 for older analytical routes
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Side-effect: installs structured logging before anything else touches a logger.
import app.core.logging_config  # noqa: F401  pylint: disable=unused-import

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.middleware import RequestContextMiddleware
from app.core.exceptions import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.api.routes.admin import page_router as admin_page_router
from app.api.routes.proxy import router as proxy_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    settings: Settings = get_settings()
    logger.info("Starting  %s  v1.0.0", settings.app_name_en)
    logger.info("Java proxy → %s", settings.java_backend_url)
    logger.info("ES  hosts  → %s", settings.es_hosts)
    logger.info("Milvus     → %s", settings.milvus_uri)
    logger.info("Neo4j      → %s", settings.neo4j_uri)
    yield
    logger.info("Shutting down  %s", settings.app_name_en)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name_en,
        description=(
            "Dual-engine job–talent matching API powered by MySQL, Neo4j, "
            "Elasticsearch, and Milvus vector search. "
            "Frontend UI → http://localhost:3000"
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ------------------------------------------------------------------
    # Middleware (registered LIFO — last-added runs outermost)
    # ------------------------------------------------------------------
    app.add_middleware(RequestContextMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time-ms"],
    )

    # ------------------------------------------------------------------
    # Exception handlers
    # ------------------------------------------------------------------
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from fastapi.exceptions import RequestValidationError

    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ------------------------------------------------------------------
    # Routes — exact routes first, parameterized routes last
    # ------------------------------------------------------------------
    app.include_router(api_router)

    # Admin panel page routes (before proxy)
    app.include_router(admin_page_router)

    # Static files (CSS, JS for admin panel)
    _static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(_static_dir):
        app.mount("/static", StaticFiles(directory=_static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def landing_page():
        """Friendly landing page in English with links to UI and docs."""
        from fastapi.responses import HTMLResponse
        return HTMLResponse(_LANDING_HTML)

    # Catch-all proxy MUST be the last registered route so it never
    # shadows concrete routes like ``/``, ``/docs`` or ``/api/*``.
    # The proxy's own guard also skips empty paths for extra safety.
    app.include_router(proxy_router)

    return app


# ---------------------------------------------------------------------------
# Landing page HTML
# ---------------------------------------------------------------------------

_LANDING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Talent-Match API — XH-202621</title>
<style>
  *, *::before, *::after { box-sizing: border-box; }
  body {
    font-family: 'Space Grotesk', system-ui, -apple-system, sans-serif;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh; margin: 0;
    background: #131318; color: #e4e1e8;
  }
  .card {
    text-align: center; padding: 48px 56px;
    border: 1px solid rgba(147,142,161,.25);
    border-radius: 16px;
    background: rgba(31,31,36,.55);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    max-width: 520px;
    box-shadow: 0 0 60px rgba(124,92,255,.08), inset 0 0 40px rgba(124,92,255,.03);
  }
  h1 { color: #cabeff; font-weight: 700; font-size: 28px; margin: 0 0 6px; letter-spacing: -.5px; }
  .tagline { color: #938ea1; font-size: 14px; margin: 0 0 32px; }
  .status {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    margin-bottom: 28px; font-size: 13px; color: #9cd0d2;
  }
  .status .dot { width: 8px; height: 8px; border-radius: 50%; background: #7fd5cd; box-shadow: 0 0 6px #7fd5cd; }
  .links { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; margin-bottom: 28px; }
  .links a {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 12px 28px; border-radius: 10px;
    text-decoration: none; font-weight: 600; font-size: 14px;
    transition: transform .2s, box-shadow .2s;
  }
  .links a:hover { transform: translateY(-1px); }
  .link-frontend { background: #cabeff; color: #1c0062; box-shadow: 0 4px 20px rgba(124,92,255,.35); }
  .link-admin   { background: linear-gradient(135deg, rgba(92,219,139,.25), rgba(127,213,205,.2)); border: 1px solid rgba(92,219,139,.4); color: #5cdb8b; box-shadow: 0 4px 20px rgba(92,219,139,.2); }
  .link-docs    { border: 1px solid #484555; color: #e4e1e8; }
  .link-health  { border: 1px solid rgba(127,213,205,.3); color: #9cd0d2; }
  hr { border: none; border-top: 1px solid rgba(147,142,161,.15); margin: 24px 0; }
  .endpoints { text-align: left; font-size: 12px; color: #938ea1; }
  .endpoints b { color: #c9c4d8; display: block; margin-bottom: 8px; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }
  .endpoints code { color: #9cd0d2; font-family: 'JetBrains Mono', monospace; font-size: 11px; }
  .endpoints .row { display: flex; justify-content: space-between; padding: 3px 0; }
</style>
</head>
<body>
<div class="card">
  <h1>Talent-Match API</h1>
  <p class="tagline">XH-202621 &middot; Dual-engine job–talent matching service</p>

  <div class="status"><span class="dot"></span> Storage API — online</div>

  <div class="links">
    <a class="link-admin" href="/admin">⚙ Admin Panel</a>
    <a class="link-frontend" href="http://localhost:3000">&#8599; Open Frontend UI</a>
    <a class="link-docs" href="/docs">API Docs</a>
    <a class="link-health" href="/api/health">Health</a>
  </div>

  <hr/>

  <div class="endpoints">
    <b>API Endpoints</b>
    <div class="row"><code>GET  /api/health</code><span>All storage checks</span></div>
    <div class="row"><code>GET  /api/search/jobs</code><span>Full-text job search</span></div>
    <div class="row"><code>GET  /api/jobs</code><span>MySQL role summary</span></div>
    <div class="row"><code>GET  /api/graph</code><span>Neo4j knowledge graph</span></div>
    <div class="row"><code>GET  /api/analysis/skills</code><span>Hot skill trends</span></div>
    <div class="row"><code>POST /api/talent-vectors/search</code><span>Milvus vector recall</span></div>
  </div>
  <div class="endpoints" style="margin-top:16px;">
    <b>Admin Panel</b>
    <div class="row"><code>/admin</code><span>Dashboard · Health · Logs</span></div>
    <div class="row"><code>/admin/logs</code><span>Log viewer · SSE live stream</span></div>
    <div class="row"><code>/admin/data-quality</code><span>Quality reports · Field coverage</span></div>
    <div class="row"><code>/admin/etl</code><span>ETL governance · Sync trigger</span></div>
    <div class="row"><code>/admin/samples</code><span>Job & skill sample browser</span></div>
    <div class="row"><code>/admin/settings</code><span>Config · Full health check</span></div>
  </div>
</div>
</body>
</html>"""

# ---------------------------------------------------------------------------
# App instance (used by uvicorn: ``app.main:app``)
# ---------------------------------------------------------------------------
app = create_app()
