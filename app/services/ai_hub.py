"""AI Hub — service layer: encryption, CRUD, and unified chat proxy."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
import uuid
from typing import AsyncIterator

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine
from app.schemas.ai import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionUsage,
    ChatMessage,
)

logger = logging.getLogger(__name__)

# ======================================================================
# Encryption helpers
# ======================================================================

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazy-init a Fernet instance from a derived key.

    Key derivation priority:
    1. ``AI_ENCRYPTION_KEY`` env var (raw Fernet key, base64-encoded 32 bytes)
    2. Derived from ``JWT_SECRET`` via SHA-256 → base64
    """
    global _fernet
    if _fernet is not None:
        return _fernet

    settings = get_settings()
    raw = os.getenv("AI_ENCRYPTION_KEY", "")
    if raw and len(raw) >= 44:
        try:
            _fernet = Fernet(raw.encode() if len(raw) == 44 else base64.urlsafe_b64encode(raw.encode()[:32]))
            return _fernet
        except Exception:
            pass

    # Fallback: derive from JWT_SECRET
    secret = os.getenv("JWT_SECRET", "xh202621-dev-secret-change-in-production")
    key_bytes = hashlib.sha256(secret.encode()).digest()
    key_b64 = base64.urlsafe_b64encode(key_bytes)
    _fernet = Fernet(key_b64)
    return _fernet


def encrypt_api_key(plain: str) -> str:
    """Encrypt an API key string. Returns base64-encoded ciphertext."""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    """Decrypt an API key string. Returns the original plaintext."""
    return _get_fernet().decrypt(encrypted.encode()).decode()


def mask_api_key(plain: str) -> str:
    """Return a masked preview of the key, e.g. ``sk-***abcd``."""
    if len(plain) <= 8:
        return plain[:2] + "***"
    return plain[:4] + "***" + plain[-4:]


# ======================================================================
# Provider CRUD
# ======================================================================


def _provider_row_to_dict(row) -> dict:
    """Convert a DB row proxy to a dict for JSON serialization."""
    return {
        "id": row.id,
        "name": row.name,
        "provider_type": row.provider_type,
        "base_url": row.base_url,
        "api_key_encrypted": row.api_key_encrypted,
        "extra_config": row.extra_config,
        "is_active": bool(row.is_active),
        "description": row.description,
        "sort_order": row.sort_order,
        "created_at": str(row.created_at) if row.created_at else None,
        "updated_at": str(row.updated_at) if row.updated_at else None,
    }


def get_providers(
    *,
    is_active: bool | None = None,
    provider_type: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Paginated list of providers."""
    conditions = []
    params: dict = {}

    if is_active is not None:
        conditions.append("p.is_active = :is_active")
        params["is_active"] = is_active
    if provider_type:
        conditions.append("p.provider_type = :ptype")
        params["ptype"] = provider_type
    if search:
        conditions.append("(p.name LIKE :search OR p.description LIKE :search)")
        params["search"] = f"%{search}%"

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) AS cnt FROM ai_providers p {where}"), params
        ).fetchone().cnt

        offset = (page - 1) * page_size
        rows = conn.execute(
            text(
                f"SELECT p.*, "
                f"(SELECT COUNT(*) FROM ai_models m WHERE m.provider_id = p.id) AS model_count "
                f"FROM ai_providers p {where} "
                f"ORDER BY p.sort_order, p.id "
                f"LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": page_size, "offset": offset},
        ).fetchall()

    items = []
    for r in rows:
        d = _provider_row_to_dict(r)
        d["model_count"] = r.model_count
        # Replace encrypted key with preview
        encrypted = d.pop("api_key_encrypted", None)
        d["api_key_configured"] = bool(encrypted)
        d["api_key_preview"] = ""
        if encrypted:
            try:
                plain = decrypt_api_key(encrypted)
                d["api_key_preview"] = mask_api_key(plain)
            except Exception:
                d["api_key_preview"] = "***（解密失败）"
        items.append(d)

    return {"total": total, "items": items}


def get_provider(provider_id: int) -> dict | None:
    """Get a single provider by id."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT p.*, (SELECT COUNT(*) FROM ai_models m WHERE m.provider_id = p.id) AS model_count "
                "FROM ai_providers p WHERE p.id = :pid"
            ),
            {"pid": provider_id},
        ).fetchone()

    if row is None:
        return None

    d = _provider_row_to_dict(row)
    d["model_count"] = row.model_count
    encrypted = d.pop("api_key_encrypted", None)
    d["api_key_configured"] = bool(encrypted)
    d["api_key_preview"] = ""
    if encrypted:
        try:
            plain = decrypt_api_key(encrypted)
            d["api_key_preview"] = mask_api_key(plain)
        except Exception:
            d["api_key_preview"] = "***（解密失败）"
    return d


def create_provider(data: dict) -> dict:
    """Insert a new provider. *data* must include an optional ``api_key`` plaintext."""
    api_key = data.pop("api_key", None)
    encrypted = encrypt_api_key(api_key) if api_key else None
    extra = data.get("extra_config")
    extra_json = json.dumps(extra, ensure_ascii=False) if extra else None

    with engine.connect() as conn:
        result = conn.execute(
            text(
                "INSERT INTO ai_providers (name, provider_type, base_url, api_key_encrypted, "
                "extra_config, description, sort_order) "
                "VALUES (:name, :ptype, :base_url, :enc, :extra, :desc, :sort)"
            ),
            {
                "name": data["name"],
                "ptype": data["provider_type"],
                "base_url": data.get("base_url"),
                "enc": encrypted,
                "extra": extra_json,
                "desc": data.get("description"),
                "sort": data.get("sort_order", 0),
            },
        )
        conn.commit()
        new_id = result.lastrowid

    return get_provider(new_id)


def update_provider(provider_id: int, data: dict) -> dict | None:
    """Update an existing provider. Only fields present in *data* are updated."""
    existing = get_provider(provider_id)
    if existing is None:
        return None

    set_clauses = []
    params: dict = {"pid": provider_id}

    field_map = {
        "name": "name",
        "provider_type": "ptype",
        "base_url": "base_url",
        "description": "desc",
        "sort_order": "sort",
        "is_active": "is_active",
    }

    for key, param in field_map.items():
        if key in data and data[key] is not None:
            set_clauses.append(f"{key} = :{param}")
            params[param] = data[key]

    if "api_key" in data and data["api_key"] is not None:
        if data["api_key"] == "":
            set_clauses.append("api_key_encrypted = NULL")
        else:
            set_clauses.append("api_key_encrypted = :enc")
            params["enc"] = encrypt_api_key(data["api_key"])

    if "extra_config" in data:
        extra = data["extra_config"]
        set_clauses.append("extra_config = :extra")
        params["extra"] = json.dumps(extra, ensure_ascii=False) if extra else None

    if not set_clauses:
        return existing

    with engine.connect() as conn:
        conn.execute(
            text(f"UPDATE ai_providers SET {', '.join(set_clauses)} WHERE id = :pid"),
            params,
        )
        conn.commit()

    return get_provider(provider_id)


def delete_provider(provider_id: int) -> bool:
    """Delete a provider and its models (CASCADE)."""
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM ai_providers WHERE id = :pid"),
            {"pid": provider_id},
        )
        conn.commit()
        return result.rowcount > 0


def test_provider_connection(provider_id: int) -> dict:
    """Test connectivity to the provider's API.

    Sends a minimal models list request to verify the API key and base URL.
    """
    provider = get_provider(provider_id)
    if provider is None:
        return {"ok": False, "error": "供应商不存在"}

    if not provider["api_key_configured"]:
        return {"ok": False, "error": "未配置 API Key"}

    # Get the plaintext key
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT api_key_encrypted FROM ai_providers WHERE id = :pid"),
            {"pid": provider_id},
        ).fetchone()

    if not row or not row.api_key_encrypted:
        return {"ok": False, "error": "无法读取 API Key"}

    try:
        api_key = decrypt_api_key(row.api_key_encrypted)
    except Exception as exc:
        return {"ok": False, "error": f"API Key 解密失败: {exc}"}

    base_url = (provider.get("base_url") or "").rstrip("/")
    if not base_url:
        # Default base URLs per provider type
        defaults = {
            "openai": "https://api.openai.com",
            "deepseek": "https://api.deepseek.com",
            "anthropic": "https://api.anthropic.com",
            "google": "https://generativelanguage.googleapis.com",
            "ollama": "http://localhost:11434",
        }
        base_url = defaults.get(provider["provider_type"], "")

    settings = get_settings()
    timeout = settings.ai_proxy_timeout

    # Try listing models (OpenAI-compatible endpoint)
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(
                f"{base_url}/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code in (200, 401, 403):
                # 200 = auth ok; 401/403 = auth failed but endpoint exists
                ok = resp.status_code == 200
                return {
                    "ok": ok,
                    "status_code": resp.status_code,
                    "message": "连接成功，认证通过" if ok else f"端点可达但认证失败（HTTP {resp.status_code}）",
                    "models_available": resp.json().get("data", [])[:5] if ok else [],
                }
            return {
                "ok": False,
                "status_code": resp.status_code,
                "message": f"端点返回异常状态码 HTTP {resp.status_code}",
            }
    except httpx.ConnectError:
        return {"ok": False, "error": f"无法连接到 {base_url}，请检查 base_url 和网络"}
    except httpx.TimeoutException:
        return {"ok": False, "error": f"连接 {base_url} 超时（{timeout}s）"}
    except Exception as exc:
        return {"ok": False, "error": f"连接测试异常: {exc}"}


# ======================================================================
# Model CRUD
# ======================================================================


def _model_row_to_dict(row, provider_name: str = "", provider_type: str = "") -> dict:
    return {
        "id": row.id,
        "provider_id": row.provider_id,
        "provider_name": provider_name,
        "provider_type": provider_type,
        "model_id": row.model_id,
        "display_name": row.display_name,
        "model_type": row.model_type,
        "max_input_tokens": row.max_input_tokens,
        "max_output_tokens": row.max_output_tokens,
        "supports_vision": bool(row.supports_vision),
        "supports_tools": bool(row.supports_tools),
        "supports_streaming": bool(row.supports_streaming),
        "pricing_input_per_1k": row.pricing_input_per_1k,
        "pricing_output_per_1k": row.pricing_output_per_1k,
        "extra_params": row.extra_params,
        "is_active": bool(row.is_active),
        "sort_order": row.sort_order,
        "created_at": str(row.created_at) if row.created_at else None,
        "updated_at": str(row.updated_at) if row.updated_at else None,
    }


def get_models(
    *,
    provider_id: int | None = None,
    model_type: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Paginated list of models, optionally filtered."""
    conditions = []
    params: dict = {}

    if provider_id is not None:
        conditions.append("m.provider_id = :pid")
        params["pid"] = provider_id
    if model_type:
        conditions.append("m.model_type = :mtype")
        params["mtype"] = model_type
    if is_active is not None:
        conditions.append("m.is_active = :is_active")
        params["is_active"] = is_active

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) AS cnt FROM ai_models m {where}"), params
        ).fetchone().cnt

        offset = (page - 1) * page_size
        rows = conn.execute(
            text(
                f"SELECT m.*, p.name AS provider_name, p.provider_type "
                f"FROM ai_models m "
                f"LEFT JOIN ai_providers p ON p.id = m.provider_id "
                f"{where} "
                f"ORDER BY m.sort_order, m.id "
                f"LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": page_size, "offset": offset},
        ).fetchall()

    items = [
        _model_row_to_dict(r, provider_name=r.provider_name or "", provider_type=r.provider_type or "")
        for r in rows
    ]
    return {"total": total, "items": items}


def get_model(model_id: int) -> dict | None:
    """Get a single model by its DB id."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT m.*, p.name AS provider_name, p.provider_type "
                "FROM ai_models m "
                "LEFT JOIN ai_providers p ON p.id = m.provider_id "
                "WHERE m.id = :mid"
            ),
            {"mid": model_id},
        ).fetchone()

    if row is None:
        return None

    return _model_row_to_dict(row, provider_name=row.provider_name or "", provider_type=row.provider_type or "")


def create_model(data: dict, provider_id: int) -> dict:
    """Insert a new model under the given provider."""
    extra = data.get("extra_params")
    extra_json = json.dumps(extra, ensure_ascii=False) if extra else None

    with engine.connect() as conn:
        result = conn.execute(
            text(
                "INSERT INTO ai_models (provider_id, model_id, display_name, model_type, "
                "max_input_tokens, max_output_tokens, supports_vision, supports_tools, "
                "supports_streaming, pricing_input_per_1k, pricing_output_per_1k, "
                "extra_params, sort_order) "
                "VALUES (:pid, :mid, :dname, :mtype, :max_in, :max_out, :vision, "
                ":tools, :stream, :price_in, :price_out, :extra, :sort)"
            ),
            {
                "pid": provider_id,
                "mid": data["model_id"],
                "dname": data.get("display_name"),
                "mtype": data.get("model_type", "llm"),
                "max_in": data.get("max_input_tokens"),
                "max_out": data.get("max_output_tokens"),
                "vision": data.get("supports_vision", False),
                "tools": data.get("supports_tools", False),
                "stream": data.get("supports_streaming", True),
                "price_in": data.get("pricing_input_per_1k"),
                "price_out": data.get("pricing_output_per_1k"),
                "extra": extra_json,
                "sort": data.get("sort_order", 0),
            },
        )
        conn.commit()
        new_id = result.lastrowid

    return get_model(new_id)


def update_model(model_db_id: int, data: dict) -> dict | None:
    """Update an existing model."""
    existing = get_model(model_db_id)
    if existing is None:
        return None

    set_clauses = []
    params: dict = {"mid": model_db_id}

    field_map = {
        "model_id": "model_id",
        "display_name": "dname",
        "model_type": "mtype",
        "max_input_tokens": "max_in",
        "max_output_tokens": "max_out",
        "supports_vision": "vision",
        "supports_tools": "tools",
        "supports_streaming": "stream",
        "pricing_input_per_1k": "price_in",
        "pricing_output_per_1k": "price_out",
        "sort_order": "sort",
        "is_active": "is_active",
    }

    for key, param in field_map.items():
        if key in data and data[key] is not None:
            set_clauses.append(f"{key} = :{param}")
            params[param] = data[key]

    if "extra_params" in data:
        extra = data["extra_params"]
        set_clauses.append("extra_params = :extra")
        params["extra"] = json.dumps(extra, ensure_ascii=False) if extra else None

    if not set_clauses:
        return existing

    with engine.connect() as conn:
        conn.execute(
            text(f"UPDATE ai_models SET {', '.join(set_clauses)} WHERE id = :mid"),
            params,
        )
        conn.commit()

    return get_model(model_db_id)


def delete_model(model_db_id: int) -> bool:
    """Delete a model."""
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM ai_models WHERE id = :mid"),
            {"mid": model_db_id},
        )
        conn.commit()
        return result.rowcount > 0


# ======================================================================
# Unified Chat Completion Proxy
# ======================================================================


def _resolve_target(req: ChatCompletionRequest) -> tuple[dict, dict]:
    """Resolve provider + model from the request.

    Returns ``(provider_dict, model_dict)``.
    Raises ``ValueError`` when resolution fails.
    """
    provider_dict: dict | None = None
    model_dict: dict | None = None

    # Priority: model_id (DB id) > model_name + provider_id
    if req.model_id:
        model_dict = get_model(req.model_id)
        if model_dict is None:
            raise ValueError(f"模型记录不存在: id={req.model_id}")
        provider_dict = get_provider(model_dict["provider_id"])
    elif req.model_name and req.provider_id:
        provider_dict = get_provider(req.provider_id)
        if provider_dict is None:
            raise ValueError(f"供应商不存在: id={req.provider_id}")
        # Look up model by name under this provider
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT m.*, p.name AS provider_name, p.provider_type "
                    "FROM ai_models m "
                    "LEFT JOIN ai_providers p ON p.id = m.provider_id "
                    "WHERE m.provider_id = :pid AND m.model_id = :mid AND m.is_active = 1"
                ),
                {"pid": req.provider_id, "mid": req.model_name},
            ).fetchone()
        if row is None:
            raise ValueError(f"供应商 {provider_dict['name']} 下未找到模型: {req.model_name}")
        model_dict = _model_row_to_dict(
            row, provider_name=row.provider_name or "", provider_type=row.provider_type or ""
        )
    else:
        raise ValueError("请指定 model_id（模型记录 ID）或 provider_id + model_name")

    if provider_dict is None:
        raise ValueError("无法解析供应商信息")

    if not provider_dict.get("is_active"):
        raise ValueError(f"供应商「{provider_dict['name']}」已被禁用")

    if not model_dict.get("is_active"):
        raise ValueError(f"模型「{model_dict.get('model_id')}」已被禁用")

    return provider_dict, model_dict


def _get_api_key(provider_id: int) -> str:
    """Fetch and decrypt the API key for a provider."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT api_key_encrypted FROM ai_providers WHERE id = :pid"),
            {"pid": provider_id},
        ).fetchone()

    if not row or not row.api_key_encrypted:
        raise ValueError("供应商未配置 API Key")

    return decrypt_api_key(row.api_key_encrypted)


async def proxy_chat_completion(req: ChatCompletionRequest) -> ChatCompletionResponse:
    """Send a chat completion request to the resolved provider and return the response.

    Supports streaming via the returned response object — callers should
    use ``proxy_chat_completion_stream`` for SSE streaming.
    """
    provider, model = _resolve_target(req)
    api_key = _get_api_key(provider["id"])
    base_url = (provider.get("base_url") or "").rstrip("/")

    if not base_url:
        defaults = {
            "openai": "https://api.openai.com",
            "deepseek": "https://api.deepseek.com",
            "anthropic": "https://api.anthropic.com",
            "google": "https://generativelanguage.googleapis.com",
            "ollama": "http://localhost:11434",
        }
        base_url = defaults.get(provider["provider_type"], "")

    if not base_url:
        raise ValueError(f"供应商 {provider['name']} 未配置 base_url，且无默认地址")

    model_name = model["model_id"]

    # Build request body (OpenAI-compatible)
    body: dict = {
        "model": model_name,
        "messages": [{"role": m.role, "content": m.content} for m in req.messages],
    }
    if req.temperature is not None:
        body["temperature"] = req.temperature
    if req.max_tokens is not None:
        body["max_tokens"] = req.max_tokens
    if req.top_p is not None:
        body["top_p"] = req.top_p
    if req.stream:
        body["stream"] = True

    # Merge extra params from model config
    if model.get("extra_params"):
        for k, v in model["extra_params"].items():
            if k not in body:
                body[k] = v

    # Merge extra_body from request
    if req.extra_body:
        body.update(req.extra_body)

    settings = get_settings()
    timeout = httpx.Timeout(settings.ai_proxy_timeout, connect=10.0)

    endpoint = f"{base_url}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info(
        "AI proxy: %s/%s → %s (stream=%s)",
        provider["name"], model_name, endpoint, req.stream,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(endpoint, json=body, headers=headers)

        if resp.status_code != 200:
            error_detail = resp.text[:500]
            logger.error("AI proxy error %s: %s", resp.status_code, error_detail)
            raise ValueError(f"上游 API 返回错误 HTTP {resp.status_code}: {error_detail}")

        data = resp.json()

    choices = []
    for c in data.get("choices", []):
        msg = c.get("message", {})
        choices.append(
            ChatCompletionChoice(
                index=c.get("index", 0),
                message=ChatMessage(
                    role=msg.get("role", "assistant"),
                    content=msg.get("content", ""),
                ),
                finish_reason=c.get("finish_reason"),
            )
        )

    usage_raw = data.get("usage", {}) or {}
    usage = ChatCompletionUsage(
        prompt_tokens=usage_raw.get("prompt_tokens"),
        completion_tokens=usage_raw.get("completion_tokens"),
        total_tokens=usage_raw.get("total_tokens"),
    )

    return ChatCompletionResponse(
        id=data.get("id", f"chatcmpl-{uuid.uuid4().hex[:12]}"),
        created=data.get("created", int(time.time())),
        model=data.get("model", model_name),
        provider=provider["name"],
        choices=choices,
        usage=usage,
    )


async def proxy_chat_completion_stream(req: ChatCompletionRequest) -> AsyncIterator[str]:
    """Stream SSE chunks from the upstream provider.

    Yields raw SSE lines that can be wrapped in a ``StreamingResponse``.
    """
    provider, model = _resolve_target(req)
    api_key = _get_api_key(provider["id"])
    base_url = (provider.get("base_url") or "").rstrip("/")

    if not base_url:
        defaults = {
            "openai": "https://api.openai.com",
            "deepseek": "https://api.deepseek.com",
            "anthropic": "https://api.anthropic.com",
            "google": "https://generativelanguage.googleapis.com",
            "ollama": "http://localhost:11434",
        }
        base_url = defaults.get(provider["provider_type"], "")

    model_name = model["model_id"]

    body: dict = {
        "model": model_name,
        "messages": [{"role": m.role, "content": m.content} for m in req.messages],
        "stream": True,
    }
    if req.temperature is not None:
        body["temperature"] = req.temperature
    if req.max_tokens is not None:
        body["max_tokens"] = req.max_tokens
    if req.top_p is not None:
        body["top_p"] = req.top_p
    if model.get("extra_params"):
        for k, v in model["extra_params"].items():
            if k not in body:
                body[k] = v
    if req.extra_body:
        body.update(req.extra_body)

    settings = get_settings()
    timeout = httpx.Timeout(settings.ai_proxy_timeout, connect=10.0)
    endpoint = f"{base_url}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info(
        "AI proxy stream: %s/%s → %s",
        provider["name"], model_name, endpoint,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", endpoint, json=body, headers=headers) as resp:
            if resp.status_code != 200:
                error_body = await resp.aread()
                error_detail = error_body.decode()[:500]
                logger.error("AI proxy stream error %s: %s", resp.status_code, error_detail)
                yield f"data: {{\"error\": \"上游 API 返回错误 HTTP {resp.status_code}\"}}\n\n"
                yield "data: [DONE]\n\n"
                return

            async for line in resp.aiter_lines():
                yield line + "\n"


# ======================================================================
# Health
# ======================================================================


def ai_health() -> dict:
    """Return AI Hub health summary."""
    with engine.connect() as conn:
        tp = conn.execute(text("SELECT COUNT(*) AS cnt FROM ai_providers")).fetchone().cnt
        ta = conn.execute(text("SELECT COUNT(*) AS cnt FROM ai_providers WHERE is_active = 1")).fetchone().cnt
        tm = conn.execute(text("SELECT COUNT(*) AS cnt FROM ai_models")).fetchone().cnt
        ma = conn.execute(text("SELECT COUNT(*) AS cnt FROM ai_models WHERE is_active = 1")).fetchone().cnt

    return {
        "status": "ok",
        "total_providers": tp,
        "active_providers": ta,
        "total_models": tm,
        "active_models": ma,
    }
