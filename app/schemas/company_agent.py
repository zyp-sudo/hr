"""Company Agent — Pydantic request / response schemas.

All models enforce strict validation so that malformed upstream
responses are caught before they reach the frontend.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ======================================================================
# Evaluate Request
# ======================================================================


class CompanyAgentEvaluateRequest(BaseModel):
    """Payload sent to POST /api/company-agent/evaluate.

    Only the fields the company agent actually needs are included —
    we never forward unrelated user data such as phone, email, or full
    profile text.
    """

    candidate_id: str | None = Field(None, description="候选人 ID（可选）")
    candidate_name: str | None = Field(None, description="候选人姓名（可选）")
    resume_text: str = Field(..., min_length=1, description="简历正文")
    job_id: str = Field(..., min_length=1, description="岗位 ID")
    job_title: str = Field(..., min_length=1, description="岗位名称")
    job_description: str | None = Field(None, description="岗位描述")
    required_skills: list[str] = Field(default_factory=list, description="岗位要求技能列表")
    local_score: int = Field(..., ge=0, le=100, description="本地规则评分 0–100")
    local_dimensions: dict = Field(default_factory=dict, description="本地评分各维度得分")
    request_id: str = Field(..., min_length=1, description="请求追踪 ID")


# ======================================================================
# Evaluate Response (from the company agent)
# ======================================================================


class DimensionScore(BaseModel):
    """A single dimension scored by the agent."""

    name: str
    score: float = Field(..., ge=0, le=100)


class EvidenceItem(BaseModel):
    """One piece of evidence backing the agent's conclusion."""

    type: str = Field(..., description="Evidence category, e.g. skill_gap / strength / risk")
    description: str = Field(..., min_length=1)


class CompanyAgentEvaluateResponse(BaseModel):
    """Normalised response returned to the frontend.

    Every field is validated; ``agent_score`` is strictly clamped to
    0–100 and will cause a validation error if it falls outside.
    """

    status: Literal["success", "disabled", "failed"]
    request_id: str
    trace_id: str | None = Field(None, description="公司智能体返回的 trace_id")
    agent_score: int | None = Field(None, description="智能体评分 0–100")
    recommendation: str | None = Field(None, description="推荐结论")
    summary: str | None = Field(None, description="评估摘要")
    strengths: list[str] = Field(default_factory=list, description="核心优势")
    risks: list[str] = Field(default_factory=list, description="风险点")
    skill_gaps: list[str] = Field(default_factory=list, description="能力缺口")
    dimensions: list[DimensionScore] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list, description="评分依据")
    provider: str = Field("disabled", description="Provider 标识")
    model: str | None = Field(None, description="使用的模型（如有）")
    latency_ms: int = Field(0, ge=0, description="智能体响应耗时（毫秒）")
    evaluated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="评估时间 ISO-8601",
    )

    @field_validator("agent_score")
    @classmethod
    def _check_agent_score_range(cls, v: int | None) -> int | None:
        if v is not None and not (0 <= v <= 100):
            raise ValueError(f"agent_score must be 0–100, got {v}")
        return v

    @field_validator("strengths", "risks", "skill_gaps")
    @classmethod
    def _check_string_list(cls, v: list) -> list:
        for item in v:
            if not isinstance(item, str):
                raise ValueError(f"Expected list of strings, got item {item!r} of type {type(item).__name__}")
        return v

    @field_validator("evidence")
    @classmethod
    def _check_evidence_list(cls, v: list) -> list:
        for item in v:
            if not isinstance(item, (dict, EvidenceItem)):
                raise ValueError(
                    f"Expected list of evidence dicts, got item {item!r} "
                    f"of type {type(item).__name__}"
                )
        return v


# ======================================================================
# Raw upstream response (before normalisation)
# ======================================================================


class CompanyAgentUpstreamResponse(BaseModel):
    """What we expect the company agent API to return.

    This is *validated* after parsing and then mapped to
    ``CompanyAgentEvaluateResponse``.  If the upstream returns illegal
    values the request is treated as failed.
    """

    status: str = Field(default="success")
    request_id: str = ""
    trace_id: str | None = None
    score: int | None = Field(None, ge=0, le=100)
    recommendation: str | None = None
    summary: str | None = None
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)
    dimensions: list[dict] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    provider: str = "company_agent"
    model: str | None = None


# ======================================================================
# Health
# ======================================================================


class CompanyAgentHealthResponse(BaseModel):
    """Never exposes API keys or tokens."""

    enabled: bool
    configured: bool
    status: str = Field(description="healthy / disabled / degraded")
    provider: str = Field(default="http", description="Provider type")
    endpoint_configured: bool = Field(default=False)
