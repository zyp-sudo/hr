"""Pydantic schemas for competition evidence-based generation and hallucination prevention."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class CandidateClaim(BaseModel):
    """A single claim that needs evidence verification."""

    text: str = Field(..., min_length=1, max_length=2000, description="候选能力声明文本")
    source_ids: list[str] = Field(default_factory=list, description="已有的来源 ID")


class EvidenceGenerateRequest(BaseModel):
    """Request body for evidence-based generation."""

    role_id: str = Field(..., min_length=1, max_length=128, description="岗位角色 ID")
    question: str = Field(..., min_length=1, max_length=5000, description="评估问题")
    candidate_claims: list[str] = Field(
        ..., min_length=1, max_length=50, description="待验证的能力声明列表"
    )


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class EvidenceClaim(BaseModel):
    """A verified or blocked claim with evidence metadata."""

    text: str = Field(..., description="原始声明文本")
    source_ids: list[str] = Field(default_factory=list, description="证据来源 ID 列表")
    supported: bool = Field(default=False, description="是否有证据支持")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="证据匹配置信度")
    needs_review: bool = Field(default=False, description="是否需要人工复核")


class EvidenceGenerateResponse(BaseModel):
    """Response from evidence-based generation."""

    answer: str = Field(..., description="基于证据生成的回答文本")
    claims: list[EvidenceClaim] = Field(default_factory=list, description="已证实的声明")
    blocked_claims: list[EvidenceClaim] = Field(
        default_factory=list, description="因无证据而被阻断的声明"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="整体置信度")
    audit_id: str = Field(..., description="审计记录 ID")
    mode: str = Field(default="offline", description="运行模式：offline | milvus | neo4j | hybrid")


# ---------------------------------------------------------------------------
# Audit record (written to JSONL, not returned directly)
# ---------------------------------------------------------------------------

class AuditRecord(BaseModel):
    """Immutable audit trail entry written to rag_audit.jsonl."""

    audit_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    mode: str = "offline"
    request_summary: dict[str, Any] = Field(default_factory=dict)
    sources_used: list[str] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)
    review_status: str = Field(default="auto", description="auto | needs_review | reviewed")
