"""Competition Core Service — JSON file–based data access layer.

无外部数据库依赖，纯基于 ``data/competition/*.json`` 的演示数据存储。
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 数据目录
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "competition"

_DISCOVERIES_PATH = _DATA_DIR / "discoveries.json"
_ROLES_PATH = _DATA_DIR / "roles.json"
_REVIEWS_PATH = _DATA_DIR / "reviews.json"
_PANORAMA_PATH = _DATA_DIR / "panorama.json"


# ---------------------------------------------------------------------------
# 通用 JSON 读写
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> Any:
    """读取 JSON 文件，文件不存在时返回默认空结构。"""
    if not path.exists():
        logger.warning("数据文件不存在: %s，返回空列表", path)
        return [] if path.suffix == ".json" and path != _PANORAMA_PATH else {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, data: Any) -> None:
    """原子写入 JSON 文件（使用唯一临时文件 + os.replace）。"""
    tmp = path.with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 1) 新岗位发现
# ---------------------------------------------------------------------------


def list_discoveries() -> list[dict[str, Any]]:
    """返回全部新岗位候选列表。"""
    return _read_json(_DISCOVERIES_PATH)


def get_discovery(discovery_id: str) -> dict[str, Any] | None:
    """按 ID 获取单条发现记录。"""
    for item in _read_json(_DISCOVERIES_PATH):
        if item.get("id") == discovery_id:
            return item
    return None


# ---------------------------------------------------------------------------
# 2) 审核记录
# ---------------------------------------------------------------------------


def list_reviews(discovery_id: str | None = None) -> list[dict[str, Any]]:
    """返回审核记录列表，可按 discovery_id 过滤。"""
    reviews = _read_json(_REVIEWS_PATH)
    if discovery_id:
        reviews = [r for r in reviews if r.get("discovery_id") == discovery_id]
    return reviews


def create_review(
    discovery_id: str,
    status: str,
    editor: str,
    edits: dict[str, Any] | None = None,
    comment: str | None = None,
) -> dict[str, Any]:
    """创建一条审核记录并更新对应发现记录的状态。"""
    reviews = _read_json(_REVIEWS_PATH)
    discoveries = _read_json(_DISCOVERIES_PATH)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    review_id = f"rev-{uuid.uuid4().hex[:8]}"

    review: dict[str, Any] = {
        "review_id": review_id,
        "discovery_id": discovery_id,
        "status": status,
        "editor": editor,
        "edits": edits,
        "comment": comment,
        "created_at": now,
    }
    reviews.append(review)
    _write_json(_REVIEWS_PATH, reviews)

    # 同步更新发现记录的审核状态
    for item in discoveries:
        if item.get("id") == discovery_id:
            item["review_status"] = status
            item["reviewed_at"] = now

            # 如审核时提供了编辑内容，则合并到发现记录
            if edits:
                if edits.get("name") is not None:
                    item["name"] = edits["name"]
                if edits.get("responsibilities") is not None:
                    item["responsibilities"] = edits["responsibilities"]
                if edits.get("required_skills") is not None:
                    item["required_skills"] = edits["required_skills"]
                if edits.get("bonus_skills") is not None:
                    item["bonus_skills"] = edits["bonus_skills"]

            _write_json(_DISCOVERIES_PATH, discoveries)
            break

    return review


# ---------------------------------------------------------------------------
# 3) 岗位能力版本
# ---------------------------------------------------------------------------


def get_role(role_id: str) -> dict[str, Any] | None:
    """按 ID 获取岗位定义（含所有历史版本）。"""
    for role in _read_json(_ROLES_PATH):
        if role.get("role_id") == role_id:
            return role
    return None


def get_role_versions(role_id: str) -> dict[str, Any] | None:
    """返回岗位历史版本信息。"""
    role = get_role(role_id)
    if role is None:
        return None
    return {
        "role_id": role["role_id"],
        "name": role["name"],
        "current_version": role.get("current_version", ""),
        "versions": role.get("versions", []),
    }


def diff_role_versions(
    role_id: str,
    from_version: str,
    to_version: str,
) -> dict[str, Any] | None:
    """对比两个版本的能力差异。

    返回 added / removed / modified 三类差异项，
    每项包含来源证据和修改原因。
    """
    role = get_role(role_id)
    if role is None:
        return None

    versions = {v["version_id"]: v for v in role.get("versions", [])}
    v_from = versions.get(from_version)
    v_to = versions.get(to_version)

    if v_from is None or v_to is None:
        return None

    # 构建技能名 → 技能项映射
    skills_from: dict[str, dict[str, Any]] = {
        s["name"]: s for s in v_from.get("skills", [])
    }
    skills_to: dict[str, dict[str, Any]] = {
        s["name"]: s for s in v_to.get("skills", [])
    }

    added = []
    removed = []
    modified = []

    # 新增: v_to 有而 v_from 无
    for name, skill in skills_to.items():
        if name not in skills_from:
            added.append({
                "name": name,
                "level": skill.get("level"),
                "source_ids": skill.get("source_ids", []),
                "reason": _build_reason("added", name, v_from, v_to),
            })

    # 移除: v_from 有而 v_to 无
    for name, skill in skills_from.items():
        if name not in skills_to:
            removed.append({
                "name": name,
                "level": skill.get("level"),
                "source_ids": skill.get("source_ids", []),
                "reason": _build_reason("removed", name, v_from, v_to),
            })

    # 修改: 两者都有但等级不同（或 source_ids 变化）
    for name, skill_to in skills_to.items():
        skill_from = skills_from.get(name)
        if skill_from is None:
            continue  # already handled as "added"
        if skill_from.get("level") != skill_to.get("level") or \
           set(skill_from.get("source_ids", [])) != set(skill_to.get("source_ids", [])):
            modified.append({
                "name": name,
                "level": skill_to.get("level"),
                "source_ids": skill_to.get("source_ids", []),
                "reason": _build_reason("modified", name, v_from, v_to),
            })

    return {
        "role_id": role_id,
        "from_version": from_version,
        "to_version": to_version,
        "added": added,
        "removed": removed,
        "modified": modified,
    }


def _build_reason(
    change_type: str,
    skill_name: str,
    v_from: dict[str, Any],
    v_to: dict[str, Any],
) -> str:
    """根据变更类型和版本元信息生成可读的修改原因。"""
    if change_type == "added":
        return (
            f"新增能力项「{skill_name}」，"
            f"来源于 {v_to.get('source', '未知来源')} "
            f"({v_to.get('timestamp', '')}) 的市场分析"
        )
    elif change_type == "removed":
        return (
            f"能力项「{skill_name}」在新版本中不再要求，"
            f"可能因技术栈更新或职责调整而移除"
        )
    else:
        return (
            f"能力项「{skill_name}」等级要求发生变化，"
            f"基于 {v_to.get('source', '未知来源')} 的最新市场数据更新"
        )


# ---------------------------------------------------------------------------
# 5) 全景图谱
# ---------------------------------------------------------------------------


def get_panorama(
    stack: str | None = None,
    level: str | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    """返回岗位能力全景图谱数据，支持按 stack/level/version 过滤。"""
    raw = _read_json(_PANORAMA_PATH)

    nodes: list[dict[str, Any]] = raw.get("nodes", [])
    edges: list[dict[str, Any]] = raw.get("edges", [])

    # 过滤节点
    if stack or level or version:
        filtered_nodes: list[dict[str, Any]] = []
        for node in nodes:
            if stack and node.get("stack") and node.get("stack") != stack:
                continue
            if level and node.get("level") and node.get("level") != level:
                continue
            if version and node.get("version") and node.get("version") != version:
                continue
            filtered_nodes.append(node)
        nodes = filtered_nodes

        # 仅保留两端节点都在过滤结果中的边
        node_ids = {n["id"] for n in nodes}
        edges = [
            e for e in edges
            if e.get("source") in node_ids and e.get("target") in node_ids
        ]

    return {
        "meta": raw.get("meta", {}),
        "nodes": nodes,
        "edges": edges,
    }
