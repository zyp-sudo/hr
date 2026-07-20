"""Competition Core Service — JSON file–based data access layer.

无外部数据库依赖，纯基于 ``data/competition/*.json`` 的演示数据存储。
所有 read-modify-write 操作均受 per-file 线程锁保护，避免并发覆盖丢失。
"""

from __future__ import annotations

import json
import logging
import os
import threading
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
# Per-file locks — protect full read-modify-write cycles
# ---------------------------------------------------------------------------

_discoveries_lock = threading.Lock()
_reviews_lock = threading.Lock()


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
    """原子写入 JSON 文件（使用唯一临时文件 + os.replace）。

    注意：本函数只保证单次写入的原子性。调用方必须在外层持有对应的
    per-file 锁来保护完整的 read-modify-write 临界区。
    """
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


def create_discovery(
    name: str,
    responsibilities: list[str],
    required_skills: list[str],
    bonus_skills: list[str],
    application_scenarios: list[str],
    source_note: str = "人工录入",
    confidence: float = 0.5,
    growth_rate: float = 0.05,
) -> dict[str, Any] | None:
    """创建一条新的岗位发现记录（人工录入）。

    返回创建后的完整 DiscoveryItem。
    如岗位名称已存在则返回 None 表示重复。

    整个 read→check→append→write 在当前 per-file 锁内完成。
    """
    # ── 防御性校验（即使 Pydantic 已经校验过，service 层仍保护）──
    normalized_name = name.strip()
    if not normalized_name:
        logger.error("create_discovery 收到空岗位名，拒绝创建")
        return None
    resp = [r.strip() for r in responsibilities if r.strip()]
    if not resp:
        logger.error("create_discovery 收到空职责列表，拒绝创建")
        return None

    with _discoveries_lock:
        discoveries = _read_json(_DISCOVERIES_PATH)

        # 去重检查：岗位名称（忽略大小写和首尾空白）
        for item in discoveries:
            if item.get("name", "").strip().lower() == normalized_name.lower():
                logger.warning("发现记录名称重复: %s", normalized_name)
                return None

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        discovery_id = f"disc-{uuid.uuid4().hex[:8]}"

        def _make_skill(skill_name: str) -> dict[str, Any]:
            return {"name": skill_name.strip(), "level": None, "source_ids": ["manual-entry"]}

        def _make_bonus(skill_name: str) -> dict[str, Any]:
            return {"name": skill_name.strip(), "source_ids": ["manual-entry"]}

        req_skills = [_make_skill(s) for s in required_skills if s.strip()]
        bon_skills = [_make_bonus(s) for s in bonus_skills if s.strip()]
        scenarios = [s.strip() for s in application_scenarios if s.strip()]

        discovery: dict[str, Any] = {
            "id": discovery_id,
            "name": normalized_name,
            "confidence": confidence,
            "growth_rate": growth_rate,
            "source_count": 1,
            "responsibilities": resp,
            "required_skills": req_skills,
            "bonus_skills": bon_skills,
            "application_scenarios": scenarios,
            "source_ids": ["manual-entry"],
            "review_status": "pending",
            "reviewed_at": None,
            "source_note": source_note.strip(),
            "created_at": now,
        }

        discoveries.append(discovery)
        _write_json(_DISCOVERIES_PATH, discoveries)
        logger.info("创建发现记录成功: %s (%s)", normalized_name, discovery_id)
        return discovery


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
    """创建一条审核记录并更新对应发现记录的状态。

    review 写入和 discovery 状态更新通过各自 per-file 锁串行化：
    先锁定 reviews 写入，再在 discoveries 锁内更新状态。
    两个操作都已受保护，但非跨文件事务（无两阶段提交）。
    """
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

    # Step 1: 原子追加 review
    with _reviews_lock:
        reviews = _read_json(_REVIEWS_PATH)
        reviews.append(review)
        _write_json(_REVIEWS_PATH, reviews)

    # Step 2: 更新 discovery 状态
    with _discoveries_lock:
        discoveries = _read_json(_DISCOVERIES_PATH)
        for item in discoveries:
            if item.get("id") == discovery_id:
                item["review_status"] = status
                item["reviewed_at"] = now

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

    skills_from: dict[str, dict[str, Any]] = {
        s["name"]: s for s in v_from.get("skills", [])
    }
    skills_to: dict[str, dict[str, Any]] = {
        s["name"]: s for s in v_to.get("skills", [])
    }

    added = []
    removed = []
    modified = []

    for name, skill in skills_to.items():
        if name not in skills_from:
            added.append({
                "name": name,
                "level": skill.get("level"),
                "source_ids": skill.get("source_ids", []),
                "reason": _build_reason("added", name, v_from, v_to),
            })

    for name, skill in skills_from.items():
        if name not in skills_to:
            removed.append({
                "name": name,
                "level": skill.get("level"),
                "source_ids": skill.get("source_ids", []),
                "reason": _build_reason("removed", name, v_from, v_to),
            })

    for name, skill_to in skills_to.items():
        skill_from = skills_from.get(name)
        if skill_from is None:
            continue
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
