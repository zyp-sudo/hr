"""AI Hub — Pydantic request / response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ======================================================================
# Provider
# ======================================================================


class ProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="供应商名称")
    provider_type: str = Field(
        ...,
        pattern=r"^(openai|anthropic|google|azure|ollama|deepseek|custom)$",
        description="供应商类型",
    )
    base_url: str | None = Field(None, max_length=512, description="API 基础地址")
    api_key: str | None = Field(None, description="API Key（明文传入，后端加密存储）")
    extra_config: dict | None = Field(None, description="额外配置")
    description: str | None = Field(None, description="备注说明")
    sort_order: int = Field(0, description="排序")


class ProviderUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    provider_type: str | None = Field(None, pattern=r"^(openai|anthropic|google|azure|ollama|deepseek|custom)$")
    base_url: str | None = Field(None, max_length=512)
    api_key: str | None = Field(None, description="API Key（传了才会更新，不传保持原值）")
    extra_config: dict | None = None
    description: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class ProviderResponse(BaseModel):
    id: int
    name: str
    provider_type: str
    base_url: str | None
    api_key_configured: bool
    api_key_preview: str
    extra_config: dict | None
    is_active: bool
    description: str | None
    sort_order: int
    model_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class ProviderListResponse(BaseModel):
    total: int
    items: list[ProviderResponse]


# ======================================================================
# Model
# ======================================================================


class ModelCreate(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=255, description="API 模型标识符")
    display_name: str | None = Field(None, max_length=255, description="展示名称")
    model_type: str = Field("llm", pattern=r"^(llm|embedding|vision|audio)$")
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    supports_vision: bool = False
    supports_tools: bool = False
    supports_streaming: bool = True
    pricing_input_per_1k: float | None = None
    pricing_output_per_1k: float | None = None
    extra_params: dict | None = None
    sort_order: int = 0


class ModelUpdate(BaseModel):
    model_id: str | None = Field(None, min_length=1, max_length=255)
    display_name: str | None = Field(None, max_length=255)
    model_type: str | None = Field(None, pattern=r"^(llm|embedding|vision|audio)$")
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    supports_vision: bool | None = None
    supports_tools: bool | None = None
    supports_streaming: bool | None = None
    pricing_input_per_1k: float | None = None
    pricing_output_per_1k: float | None = None
    extra_params: dict | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class ModelResponse(BaseModel):
    id: int
    provider_id: int
    provider_name: str = ""
    provider_type: str = ""
    model_id: str
    display_name: str | None
    model_type: str
    max_input_tokens: int | None
    max_output_tokens: int | None
    supports_vision: bool
    supports_tools: bool
    supports_streaming: bool
    pricing_input_per_1k: float | None
    pricing_output_per_1k: float | None
    extra_params: dict | None
    is_active: bool
    sort_order: int
    created_at: str | None = None
    updated_at: str | None = None


class ModelListResponse(BaseModel):
    total: int
    items: list[ModelResponse]


# ======================================================================
# Chat Completion
# ======================================================================


class ChatMessage(BaseModel):
    role: str = Field(..., pattern=r"^(system|user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatCompletionRequest(BaseModel):
    provider_id: int | None = Field(None, description="供应商 ID，与 model_id 二选一")
    model_id: int | None = Field(None, description="模型记录 ID（ai_models.id），与 provider_id+model_name 互斥")
    model_name: str | None = Field(None, description="直接传模型标识符，需要同时传 provider_id")
    messages: list[ChatMessage] = Field(..., min_length=1)
    temperature: float | None = Field(None, ge=0, le=2)
    max_tokens: int | None = Field(None, ge=1)
    top_p: float | None = Field(None, ge=0, le=1)
    stream: bool = False
    extra_body: dict | None = Field(None, description="透传给上游 API 的额外参数")


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str | None = None


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    provider: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage | None = None


# ======================================================================
# Health
# ======================================================================


class AiHealthResponse(BaseModel):
    status: str
    total_providers: int
    active_providers: int
    total_models: int
    active_models: int
