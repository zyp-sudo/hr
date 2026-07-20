"""Competition Core — Pydantic request / response schemas.

定义赛题核心模块的全部数据模型：
- 新岗位发现
- 岗位能力版本管理
- 岗位能力全景图谱
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# 公共子模型
# =============================================================================


class SkillItem(BaseModel):
    """技能项 — 包含名称、等级和来源证据。"""

    name: str = Field(..., description="技能名称")
    level: str | None = Field(
        None,
        pattern=r"^(beginner|intermediate|advanced|expert)$",
        description="技能等级",
    )
    source_ids: list[str] = Field(default_factory=list, description="该技能项的来源 ID 列表")


class BonusSkillItem(BaseModel):
    """加分技能项 — 不含等级维度。"""

    name: str = Field(..., description="加分技能名称")
    source_ids: list[str] = Field(default_factory=list, description="来源 ID 列表")


# =============================================================================
# 1) 新岗位发现
# =============================================================================


class DiscoveryItem(BaseModel):
    """新岗位候选。"""

    id: str = Field(..., description="发现记录唯一标识")
    name: str = Field(..., description="岗位名称")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度 0~1")
    growth_rate: float = Field(..., description="需求增长率")
    source_count: int = Field(..., ge=0, description="来源数据条数")
    responsibilities: list[str] = Field(default_factory=list, description="核心职责列表")
    required_skills: list[SkillItem] = Field(default_factory=list, description="必备技能列表")
    bonus_skills: list[BonusSkillItem] = Field(default_factory=list, description="加分技能列表")
    application_scenarios: list[str] = Field(default_factory=list, description="应用场景列表")
    source_ids: list[str] = Field(default_factory=list, description="外部来源 ID 列表")
    review_status: str = Field(
        default="pending",
        pattern=r"^(pending|approved|rejected)$",
        description="审核状态",
    )
    reviewed_at: str | None = Field(None, description="最近审核时间 (ISO-8601)")
    source_note: str | None = Field(None, description="来源说明（人工录入时填写）")
    created_at: str | None = Field(None, description="记录创建时间 (ISO-8601)")


class DiscoveryListResponse(BaseModel):
    """新岗位候选列表响应。"""

    total: int = Field(..., description="总条数")
    items: list[DiscoveryItem] = Field(default_factory=list, description="候选列表")


class CreateDiscoveryRequest(BaseModel):
    """手动创建新岗位发现记录。"""

    name: str = Field(..., min_length=1, max_length=200, description="岗位名称")
    responsibilities: list[str] = Field(
        default_factory=list,
        min_length=1,
        max_length=20,
        description="岗位职责列表，至少一条",
    )
    required_skills: list[str] = Field(
        default_factory=list,
        max_length=30,
        description="必备技能名称列表（普通字符串，非 SkillItem）",
    )
    bonus_skills: list[str] = Field(
        default_factory=list,
        max_length=30,
        description="加分技能名称列表（普通字符串，非 BonusSkillItem）",
    )
    application_scenarios: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="应用场景列表",
    )
    source_note: str = Field(
        default="人工录入",
        max_length=200,
        description="来源说明",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="置信度，默认 0.5",
    )
    growth_rate: float = Field(
        default=0.05,
        ge=-1.0,
        le=10.0,
        description="增长率，默认 0.05",
    )

    @field_validator("name", mode="after")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        """Reject whitespace-only or empty names at the Pydantic level."""
        if not isinstance(v, str):
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("岗位名称不能为空或全为空格")
        return stripped

    @field_validator("responsibilities", mode="after")
    @classmethod
    def _validate_responsibilities(cls, v: list[str]) -> list[str]:
        """Reject if all responsibilities are empty or whitespace-only."""
        if not isinstance(v, list):
            return v
        result = [r.strip() for r in v if isinstance(r, str) and r.strip()]
        if not result:
            raise ValueError("岗位职责至少需要填写一条有效内容")
        return result

    @model_validator(mode="after")
    def _strip_optional_fields(self) -> "CreateDiscoveryRequest":
        """Strip whitespace from optional fields (skills, scenarios, source_note)."""
        if isinstance(self.required_skills, list):
            self.required_skills = [
                s.strip() for s in self.required_skills
                if isinstance(s, str) and s.strip()
            ]
        if isinstance(self.bonus_skills, list):
            self.bonus_skills = [
                s.strip() for s in self.bonus_skills
                if isinstance(s, str) and s.strip()
            ]
        if isinstance(self.application_scenarios, list):
            self.application_scenarios = [
                s.strip() for s in self.application_scenarios
                if isinstance(s, str) and s.strip()
            ]
        if isinstance(self.source_note, str):
            self.source_note = self.source_note.strip() or "人工录入"
        return self


# =============================================================================
# 2) 审核记录
# =============================================================================


class ReviewEditPayload(BaseModel):
    """审核时对岗位定义的修改内容。"""

    name: str | None = Field(None, description="修正后的岗位名称")
    responsibilities: list[str] | None = Field(None, description="修正后的职责列表")
    required_skills: list[SkillItem] | None = Field(None, description="修正后的必备技能")
    bonus_skills: list[BonusSkillItem] | None = Field(None, description="修正后的加分技能")


class ReviewRequest(BaseModel):
    """人工审核请求体。"""

    status: str = Field(..., pattern=r"^(approved|rejected|pending)$", description="审核结论")
    editor: str = Field(..., min_length=1, max_length=64, description="审核人标识")
    edits: ReviewEditPayload | None = Field(None, description="人工修改内容")
    comment: str | None = Field(None, max_length=2000, description="审核备注")


class ReviewRecord(BaseModel):
    """审核记录。"""

    review_id: str = Field(..., description="审核记录唯一标识")
    discovery_id: str = Field(..., description="关联的发现记录 ID")
    status: str = Field(..., description="审核结论")
    editor: str = Field(..., description="审核人")
    edits: dict[str, Any] | None = Field(None, description="修改内容快照")
    comment: str | None = Field(None, description="审核备注")
    created_at: str = Field(..., description="审核时间 (ISO-8601)")


# =============================================================================
# 3) 岗位能力版本
# =============================================================================


class RoleVersionItem(BaseModel):
    """单个历史版本。"""

    version_id: str = Field(..., description="版本标识")
    timestamp: str = Field(..., description="版本时间 (ISO-8601)")
    source: str = Field(..., description="版本来源说明")
    responsibilities: list[str] = Field(default_factory=list, description="该版本职责列表")
    skills: list[SkillItem] = Field(default_factory=list, description="该版本技能集合")
    source_ids: list[str] = Field(default_factory=list, description="版本级别的来源 ID")


class RoleVersionsResponse(BaseModel):
    """岗位历史版本列表。"""

    role_id: str = Field(..., description="岗位唯一标识")
    name: str = Field(..., description="岗位名称")
    current_version: str = Field(..., description="当前最新版本号")
    versions: list[RoleVersionItem] = Field(default_factory=list, description="历史版本列表")


# =============================================================================
# 4) 版本差异
# =============================================================================


class DiffSkillItem(BaseModel):
    """差异中的单个能力项 — 扩展了修改原因和来源证据。"""

    name: str = Field(..., description="能力项名称")
    level: str | None = Field(None, description="技能等级")
    source_ids: list[str] = Field(default_factory=list, description="来源证据 ID 列表")
    reason: str | None = Field(None, description="修改原因说明")


class RoleDiffResponse(BaseModel):
    """两个版本之间的能力差异。"""

    role_id: str = Field(..., description="岗位 ID")
    from_version: str = Field(..., description="基准版本")
    to_version: str = Field(..., description="对比版本")
    added: list[DiffSkillItem] = Field(default_factory=list, description="新增能力项")
    removed: list[DiffSkillItem] = Field(default_factory=list, description="移除能力项")
    modified: list[DiffSkillItem] = Field(default_factory=list, description="修改能力项（等级变化等）")


# =============================================================================
# 5) 全景图谱
# =============================================================================


class PanoramaNode(BaseModel):
    """图谱节点。"""

    id: str = Field(..., description="节点唯一标识")
    type: str = Field(..., pattern=r"^(role|skill|capability)$", description="节点类型：岗位/技能/能力维度")
    label: str = Field(..., description="节点显示标签")
    stack: str | None = Field(None, description="技术栈（仅 role 节点）")
    level: str | None = Field(None, description="级别（仅 role 节点）")
    version: str | None = Field(None, description="版本（仅 role 节点）")
    source_ids: list[str] = Field(default_factory=list, description="来源 ID 列表")


class PanoramaEdge(BaseModel):
    """图谱关系边。"""

    source: str = Field(..., description="起始节点 ID")
    target: str = Field(..., description="目标节点 ID")
    relation: str = Field(..., pattern=r"^(requires|demonstrates|related_to)$", description="关系类型")
    source_ids: list[str] = Field(default_factory=list, description="来源 ID 列表")


class PanoramaResponse(BaseModel):
    """岗位能力全景图谱响应。"""

    meta: dict[str, Any] = Field(default_factory=dict, description="图谱元信息")
    nodes: list[PanoramaNode] = Field(default_factory=list, description="图谱节点列表")
    edges: list[PanoramaEdge] = Field(default_factory=list, description="图谱边列表")
