import urllib.error
import urllib.request

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_legacy_java(path: str, request: Request) -> Response:
    """Keep legacy analytical endpoints while storage endpoints run on Python."""
    query = f"?{request.url.query}" if request.url.query else ""
    target = f"{settings.java_backend_url.rstrip('/')}/{path}{query}"
    body = await request.body()
    headers = {"Content-Type": request.headers.get("content-type", "application/json")}
    proxy_request = urllib.request.Request(target, data=body or None, headers=headers, method=request.method)
    try:
        with urllib.request.urlopen(proxy_request, timeout=60) as upstream:
            return Response(
                content=upstream.read(),
                status_code=upstream.status,
                media_type=upstream.headers.get_content_type(),
            )
    except urllib.error.HTTPError as exc:
        return Response(content=exc.read(), status_code=exc.code, media_type="application/json")
    except urllib.error.URLError as exc:
        return Response(
            content=f'{{"detail":"Java 分析服务不可用: {exc.reason}"}}',
            status_code=503,
            media_type="application/json",
        )
