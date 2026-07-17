"""AI Hub — 多供应商 API 与模型管理路由.

提供:
- 供应商 CRUD
- 模型 CRUD
- 统一聊天代理（含流式）
- 连接测试 & 健康检查
- 种子数据

管理类端点无认证要求，与 /api/admin/* 保持一致（admin panel 本地访问）。
聊天代理端点和种子数据需要登录认证。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from app.core.security import get_current_user
from app.db.session import engine
from app.schemas.ai import (
    ChatCompletionRequest,
    ModelCreate,
    ModelUpdate,
    ProviderCreate,
    ProviderUpdate,
)
from app.services import ai_hub as hub

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai-hub"])

# ══════════════════════════════════════════════════════════════════════
# Providers (no auth — matches /api/admin/* pattern)
# ══════════════════════════════════════════════════════════════════════


@router.get("/providers")
def list_providers(
    is_active: bool | None = Query(None, description="按启用状态筛选"),
    provider_type: str | None = Query(None, description="按类型筛选"),
    search: str | None = Query(None, description="搜索名称或备注"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    """列出所有 AI 供应商。"""
    return hub.get_providers(
        is_active=is_active,
        provider_type=provider_type,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get("/providers/{provider_id}")
def get_provider(provider_id: int) -> dict:
    """获取单个供应商详情。"""
    provider = hub.get_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return provider


@router.post("/providers", status_code=201)
def create_provider(body: ProviderCreate) -> dict:
    """新增 AI 供应商。"""
    try:
        return hub.create_provider(body.model_dump(exclude_none=True))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"创建供应商失败: {exc}") from exc


@router.put("/providers/{provider_id}")
def update_provider(provider_id: int, body: ProviderUpdate) -> dict:
    """更新 AI 供应商。"""
    result = hub.update_provider(provider_id, body.model_dump(exclude_none=True))
    if result is None:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return result


@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: int) -> dict:
    """删除 AI 供应商及其所有模型。"""
    ok = hub.delete_provider(provider_id)
    if not ok:
        raise HTTPException(status_code=404, detail="供应商不存在或已删除")
    return {"deleted": True, "provider_id": provider_id}


@router.post("/providers/{provider_id}/test")
def test_provider_connection(provider_id: int) -> dict:
    """测试供应商连接。"""
    return hub.test_provider_connection(provider_id)


# ══════════════════════════════════════════════════════════════════════
# Models (no auth — matches /api/admin/* pattern)
# ══════════════════════════════════════════════════════════════════════


@router.get("/models")
def list_models(
    provider_id: int | None = Query(None, description="按供应商筛选"),
    model_type: str | None = Query(None, description="按模型类型筛选"),
    is_active: bool | None = Query(None, description="按启用状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    """列出所有模型。"""
    return hub.get_models(
        provider_id=provider_id,
        model_type=model_type,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.get("/providers/{provider_id}/models")
def list_provider_models(
    provider_id: int,
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    """列出某供应商下的模型。"""
    return hub.get_models(
        provider_id=provider_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.get("/models/{model_id}")
def get_model(model_id: int) -> dict:
    """获取单个模型详情。"""
    model = hub.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    return model


@router.post("/providers/{provider_id}/models", status_code=201)
def create_model(provider_id: int, body: ModelCreate) -> dict:
    """为供应商新增模型。"""
    provider = hub.get_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="供应商不存在")
    try:
        return hub.create_model(body.model_dump(exclude_none=True), provider_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"创建模型失败: {exc}") from exc


@router.put("/models/{model_id}")
def update_model(model_id: int, body: ModelUpdate) -> dict:
    """更新模型。"""
    result = hub.update_model(model_id, body.model_dump(exclude_none=True))
    if result is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    return result


@router.delete("/models/{model_id}")
def delete_model(model_id: int) -> dict:
    """删除模型。"""
    ok = hub.delete_model(model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模型不存在或已删除")
    return {"deleted": True, "model_id": model_id}


# ══════════════════════════════════════════════════════════════════════
# Unified Chat Proxy (auth required — costs real money)
# ══════════════════════════════════════════════════════════════════════


@router.post("/chat/completions")
async def chat_completions(
    req: ChatCompletionRequest,
    _user: dict = Depends(get_current_user),
) -> dict:
    """统一聊天代理 — 需登录。

    支持通过 model_id（ai_models 表 ID）或 provider_id + model_name 指定模型。
    stream=True 时返回 SSE 流式响应。
    """
    try:
        if req.stream:
            return StreamingResponse(
                hub.proxy_chat_completion_stream(req),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        result = await hub.proxy_chat_completion(req)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Chat completion proxy failed")
        raise HTTPException(status_code=502, detail=f"AI 代理调用失败: {exc}") from exc


# ══════════════════════════════════════════════════════════════════════
# Public endpoints
# ══════════════════════════════════════════════════════════════════════


@router.get("/public/providers")
def public_list_providers() -> dict:
    """公开端点 — 列出已启用的供应商和模型（供前端下拉选择）。"""
    result = hub.get_providers(is_active=True, page_size=200)
    items = []
    for p in result["items"]:
        models = hub.get_models(provider_id=p["id"], is_active=True, page_size=200)
        items.append({
            "id": p["id"],
            "name": p["name"],
            "provider_type": p["provider_type"],
            "api_key_configured": p["api_key_configured"],
            "models": [
                {
                    "id": m["id"],
                    "model_id": m["model_id"],
                    "display_name": m["display_name"] or m["model_id"],
                    "model_type": m["model_type"],
                    "supports_vision": m["supports_vision"],
                    "supports_tools": m["supports_tools"],
                    "pricing_input_per_1k": m["pricing_input_per_1k"],
                    "pricing_output_per_1k": m["pricing_output_per_1k"],
                }
                for m in models["items"]
            ],
        })
    return {"providers": items}


@router.get("/health")
def ai_health() -> dict:
    """AI Hub 健康检查。"""
    return hub.ai_health()


# ══════════════════════════════════════════════════════════════════════
# Seed data (auth required — destructive potential)
# ══════════════════════════════════════════════════════════════════════

_SEED_DATA = [
    {
        "name": "OpenAI",
        "provider_type": "openai",
        "base_url": "https://api.openai.com",
        "description": "OpenAI 官方 API",
        "models": [
            {"model_id": "gpt-4o", "display_name": "GPT-4o", "max_input_tokens": 128000, "max_output_tokens": 16384, "supports_vision": True, "supports_tools": True, "pricing_input_per_1k": 0.0025, "pricing_output_per_1k": 0.01},
            {"model_id": "gpt-4o-mini", "display_name": "GPT-4o Mini", "max_input_tokens": 128000, "max_output_tokens": 16384, "supports_vision": True, "supports_tools": True, "pricing_input_per_1k": 0.00015, "pricing_output_per_1k": 0.0006},
            {"model_id": "gpt-4.1", "display_name": "GPT-4.1", "max_input_tokens": 1000000, "max_output_tokens": 32768, "supports_vision": True, "supports_tools": True, "pricing_input_per_1k": 0.002, "pricing_output_per_1k": 0.008},
            {"model_id": "o4-mini", "display_name": "o4-mini", "max_input_tokens": 200000, "max_output_tokens": 100000, "supports_vision": True, "supports_tools": False, "pricing_input_per_1k": 0.0011, "pricing_output_per_1k": 0.0044},
        ],
    },
    {
        "name": "DeepSeek",
        "provider_type": "deepseek",
        "base_url": "https://api.deepseek.com",
        "description": "DeepSeek 官方 API",
        "models": [
            {"model_id": "deepseek-chat", "display_name": "DeepSeek V3", "max_input_tokens": 128000, "max_output_tokens": 8192, "supports_tools": True, "pricing_input_per_1k": 0.00027, "pricing_output_per_1k": 0.0011},
            {"model_id": "deepseek-reasoner", "display_name": "DeepSeek R1", "max_input_tokens": 128000, "max_output_tokens": 8192, "supports_tools": False, "pricing_input_per_1k": 0.00055, "pricing_output_per_1k": 0.00219},
        ],
    },
    {
        "name": "Anthropic",
        "provider_type": "anthropic",
        "base_url": "https://api.anthropic.com",
        "description": "Anthropic Claude API",
        "models": [
            {"model_id": "claude-sonnet-4-5", "display_name": "Claude Sonnet 4.5", "max_input_tokens": 200000, "max_output_tokens": 16384, "supports_vision": True, "supports_tools": True},
            {"model_id": "claude-opus-4-8", "display_name": "Claude Opus 4.8", "max_input_tokens": 200000, "max_output_tokens": 16384, "supports_vision": True, "supports_tools": True},
            {"model_id": "claude-haiku-4-5", "display_name": "Claude Haiku 4.5", "max_input_tokens": 200000, "max_output_tokens": 8192, "supports_vision": True, "supports_tools": True},
        ],
    },
    {
        "name": "Google Gemini",
        "provider_type": "google",
        "base_url": "https://generativelanguage.googleapis.com",
        "description": "Google Gemini API",
        "models": [
            {"model_id": "gemini-2.5-flash", "display_name": "Gemini 2.5 Flash", "max_input_tokens": 1048576, "max_output_tokens": 8192, "supports_vision": True, "supports_tools": True},
            {"model_id": "gemini-2.5-pro", "display_name": "Gemini 2.5 Pro", "max_input_tokens": 1048576, "max_output_tokens": 16384, "supports_vision": True, "supports_tools": True},
        ],
    },
    {
        "name": "Ollama",
        "provider_type": "ollama",
        "base_url": "http://localhost:11434",
        "description": "本地 Ollama 服务（无需 API Key）",
        "models": [
            {"model_id": "qwen3", "display_name": "Qwen 3", "max_input_tokens": 32768, "max_output_tokens": 8192},
            {"model_id": "llama4", "display_name": "Llama 4", "max_input_tokens": 32768, "max_output_tokens": 8192},
            {"model_id": "deepseek-r1:8b", "display_name": "DeepSeek R1 8B", "max_input_tokens": 32768, "max_output_tokens": 8192},
        ],
    },
]


@router.post("/seed")
def seed_ai_data() -> dict:
    """预置常见 AI 供应商和模型。

    幂等操作：已存在的供应商和模型不会被重复创建。
    """
    created_providers = 0
    updated_providers = 0
    created_models = 0

    for pdata in _SEED_DATA:
        provider_type = pdata["provider_type"]

        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM ai_providers WHERE name = :nm"),
                {"nm": pdata["name"]},
            ).fetchone()

        if existing:
            with engine.connect() as conn:
                conn.execute(
                    text(
                        "UPDATE ai_providers SET provider_type = :pt, base_url = :bu, "
                        "description = :desc WHERE id = :pid"
                    ),
                    {"pt": provider_type, "bu": pdata["base_url"], "desc": pdata["description"], "pid": existing.id},
                )
                conn.commit()
            provider_id = existing.id
            updated_providers += 1
        else:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "INSERT INTO ai_providers (name, provider_type, base_url, description) "
                        "VALUES (:nm, :pt, :bu, :desc)"
                    ),
                    {"nm": pdata["name"], "pt": provider_type, "bu": pdata["base_url"], "desc": pdata["description"]},
                )
                conn.commit()
                provider_id = result.lastrowid
            created_providers += 1

        for mdata in pdata["models"]:
            with engine.connect() as conn:
                mexist = conn.execute(
                    text("SELECT id FROM ai_models WHERE provider_id = :pid AND model_id = :mid"),
                    {"pid": provider_id, "mid": mdata["model_id"]},
                ).fetchone()

            if mexist is None:
                with engine.connect() as conn:
                    conn.execute(
                        text(
                            "INSERT INTO ai_models (provider_id, model_id, display_name, "
                            "max_input_tokens, max_output_tokens, supports_vision, supports_tools, "
                            "pricing_input_per_1k, pricing_output_per_1k) "
                            "VALUES (:pid, :mid, :dname, :max_in, :max_out, :vision, :tools, "
                            ":price_in, :price_out)"
                        ),
                        {
                            "pid": provider_id,
                            "mid": mdata["model_id"],
                            "dname": mdata.get("display_name"),
                            "max_in": mdata.get("max_input_tokens"),
                            "max_out": mdata.get("max_output_tokens"),
                            "vision": mdata.get("supports_vision", False),
                            "tools": mdata.get("supports_tools", False),
                            "price_in": mdata.get("pricing_input_per_1k"),
                            "price_out": mdata.get("pricing_output_per_1k"),
                        },
                    )
                    conn.commit()
                created_models += 1

    logger.info(
        "AI seed complete: providers (%d created, %d updated), models (%d created)",
        created_providers, updated_providers, created_models,
    )

    return {
        "message": f"AI 种子数据已就绪（供应商: {created_providers} 新建 / {updated_providers} 更新, 模型: {created_models} 新建）",
        "providers_created": created_providers,
        "providers_updated": updated_providers,
        "models_created": created_models,
    }
