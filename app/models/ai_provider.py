"""AI Hub — Provider & Model ORM models.

Tables:
- ``ai_providers`` — AI 供应商（OpenAI, DeepSeek, Anthropic …）
- ``ai_models``    — 每个供应商下的模型列表
"""

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AiProvider(TimestampMixin, Base):
    __tablename__ = "ai_providers"
    __table_args__ = (
        Index("idx_ai_providers_type", "provider_type"),
        {"comment": "AI 供应商表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="供应商ID")
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True, comment="显示名称，如 OpenAI / DeepSeek")
    provider_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="供应商类型: openai / anthropic / google / azure / ollama / deepseek / custom",
    )
    base_url: Mapped[str | None] = mapped_column(String(512), comment="API 基础地址")
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, comment="Fernet 加密后的 API Key")
    extra_config: Mapped[dict | None] = mapped_column(JSON, comment="额外配置 (org_id, api_version …)")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    description: Mapped[str | None] = mapped_column(Text, comment="备注说明")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序权重，越小越靠前")

    models = relationship("AiModel", back_populates="provider", cascade="all, delete-orphan")


class AiModel(TimestampMixin, Base):
    __tablename__ = "ai_models"
    __table_args__ = (
        Index("idx_ai_models_provider", "provider_id"),
        Index("idx_ai_models_type", "model_type"),
        {"comment": "AI 模型表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="模型ID")
    provider_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ai_providers.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="所属供应商",
    )
    model_id: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="API 模型标识符，如 gpt-4o / claude-sonnet-4-5",
    )
    display_name: Mapped[str | None] = mapped_column(String(255), comment="前端展示名称")
    model_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="llm",
        comment="模型类型: llm / embedding / vision / audio",
    )
    max_input_tokens: Mapped[int | None] = mapped_column(Integer, comment="最大输入 token 数")
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, comment="最大输出 token 数")
    supports_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否支持图片识别")
    supports_tools: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否支持 function calling")
    supports_streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否支持流式输出")
    pricing_input_per_1k: Mapped[float | None] = mapped_column(Float, comment="输入价格 / 1k tokens")
    pricing_output_per_1k: Mapped[float | None] = mapped_column(Float, comment="输出价格 / 1k tokens")
    extra_params: Mapped[dict | None] = mapped_column(JSON, comment="默认参数 (temperature, top_p …)")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序权重，越小越靠前")

    provider = relationship("AiProvider", back_populates="models")
