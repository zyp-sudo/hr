"""Competition Core API Routes — 赛题核心接口。

提供五组 REST 端点：
1. GET  /api/competition/discoveries            — 新岗位发现列表
2. POST /api/competition/discoveries/{id}/review — 人工审核
3. GET  /api/competition/roles/{id}/versions     — 岗位历史版本
4. GET  /api/competition/roles/{id}/diff         — 版本差异对比
5. GET  /api/competition/panorama                 — 岗位能力全景图谱

注意：此路由模块不在 ``app/api/router.py`` 中注册，
留给最终整合者按需引入。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas.competition import (
    DiffSkillItem,
    DiscoveryItem,
    DiscoveryListResponse,
    PanoramaEdge,
    PanoramaNode,
    PanoramaResponse,
    ReviewEditPayload,
    ReviewRecord,
    ReviewRequest,
    RoleDiffResponse,
    RoleVersionItem,
    RoleVersionsResponse,
)
from app.services import competition_core as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/competition", tags=["competition-core"])

# =============================================================================
# 1) 新岗位发现
# =============================================================================


@router.get("/discoveries", response_model=DiscoveryListResponse)
def list_discoveries(
    status: str | None = Query(None, pattern=r"^(pending|approved|rejected)$"),
) -> dict:
    """返回新岗位候选列表，可按审核状态过滤。"""
    try:
        items = svc.list_discoveries()
    except Exception as exc:
        logger.exception("读取发现列表失败")
        raise HTTPException(status_code=500, detail=f"数据读取失败: {exc}") from exc

    if status:
        items = [it for it in items if it.get("review_status") == status]

    # 按置信度降序排列
    items.sort(key=lambda x: x.get("confidence", 0), reverse=True)

    return {"total": len(items), "items": items}


# =============================================================================
# 2) 人工审核
# =============================================================================


@router.post(
    "/discoveries/{discovery_id}/review",
    response_model=ReviewRecord,
    status_code=201,
)
def review_discovery(discovery_id: str, body: ReviewRequest) -> dict:
    """人工审核新岗位发现。

    支持 approved / rejected / pending 三种状态。
    可附带编辑内容（edits）修改岗位定义。
    审核记录持久化写入并同步更新发现状态。
    """
    # 校验发现记录存在
    discovery = svc.get_discovery(discovery_id)
    if discovery is None:
        raise HTTPException(status_code=404, detail=f"发现记录不存在: {discovery_id}")

    try:
        review = svc.create_review(
            discovery_id=discovery_id,
            status=body.status,
            editor=body.editor,
            edits=body.edits.model_dump(exclude_none=True) if body.edits else None,
            comment=body.comment,
        )
    except Exception as exc:
        logger.exception("创建审核记录失败")
        raise HTTPException(status_code=500, detail=f"审核记录保存失败: {exc}") from exc

    return review


@router.get(
    "/discoveries/{discovery_id}/reviews",
    response_model=list[ReviewRecord],
)
def list_discovery_reviews(discovery_id: str) -> list[dict]:
    """查询某条发现记录的全部审核历史。"""
    if svc.get_discovery(discovery_id) is None:
        raise HTTPException(status_code=404, detail=f"发现记录不存在: {discovery_id}")
    return svc.list_reviews(discovery_id=discovery_id)


# =============================================================================
# 3) 岗位历史版本
# =============================================================================


@router.get("/roles/{role_id}/versions", response_model=RoleVersionsResponse)
def get_role_versions(role_id: str) -> dict:
    """返回岗位的全部历史版本、时间、来源和技能集合。"""
    result = svc.get_role_versions(role_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"岗位不存在: {role_id}")
    return result


# =============================================================================
# 4) 版本差异对比
# =============================================================================


@router.get("/roles/{role_id}/diff", response_model=RoleDiffResponse)
def diff_role_versions(
    role_id: str,
    from_version: str = Query(..., min_length=1, description="基准版本标识"),
    to_version: str = Query(..., min_length=1, description="对比版本标识"),
) -> dict:
    """对比岗位两个版本之间的能力差异。

    返回 added / removed / modified 三类能力项，
    每项包含来源证据（source_ids）和修改原因（reason）。
    """
    if from_version == to_version:
        raise HTTPException(status_code=400, detail="两个版本不能相同")

    result = svc.diff_role_versions(role_id, from_version, to_version)
    if result is None:
        # 尝试区分：岗位不存在还是版本不存在
        role = svc.get_role(role_id)
        if role is None:
            raise HTTPException(status_code=404, detail=f"岗位不存在: {role_id}")
        existing = {v["version_id"] for v in role.get("versions", [])}
        missing = []
        if from_version not in existing:
            missing.append(from_version)
        if to_version not in existing:
            missing.append(to_version)
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"版本不存在: {', '.join(missing)}。可用版本: {', '.join(sorted(existing))}",
            )
    return result


# =============================================================================
# 5) 岗位能力全景图谱
# =============================================================================


@router.get("/panorama", response_model=PanoramaResponse)
def get_panorama(
    stack: str | None = Query(
        None,
        description="技术栈过滤 (backend / frontend / data / ai)",
    ),
    level: str | None = Query(
        None,
        pattern=r"^(junior|mid|senior|staff)$",
        description="级别过滤",
    ),
    version: str | None = Query(
        None,
        min_length=1,
        description="版本过滤 (v1 / v2)",
    ),
) -> dict:
    """返回岗位能力全景图谱数据。

    包含岗位（role）、技能（skill）、能力维度（capability）三类节点
    以及它们之间的 requires / demonstrates / related_to 关系边。
    支持按技术栈、级别和版本过滤。
    """
    try:
        result = svc.get_panorama(stack=stack, level=level, version=version)
    except Exception as exc:
        logger.exception("读取全景图谱失败")
        raise HTTPException(status_code=500, detail=f"图谱数据读取失败: {exc}") from exc

    return result
