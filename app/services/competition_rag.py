"""Evidence-based generation and hallucination prevention for competition scenarios.

Core design:
- Priority 1: Load evidence from ``data/competition/evidence_sources.json`` and
  existing job-evidence files (unified_job_skills.csv, KG nodes/edges).
- Priority 2 (optional): Milvus / Neo4j retrieval — designed but gated behind
  connectivity; tests never depend on real services.
- Priority 3: Deterministic offline fallback using the built‑in competency index
  and SHA‑256 feature‑hash embedding (same family as ``milvus_talent.py``).

Rule: any claim without at least one ``source_id`` MUST be moved to
``blocked_claims`` — it cannot be published.  Low‑confidence claims are flagged
``needs_review``.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import math
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.competition_rag import (
    AuditRecord,
    CandidateClaim,
    EvidenceClaim,
    EvidenceGenerateRequest,
    EvidenceGenerateResponse,
)

logger = logging.getLogger("xh.competition_rag")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.60  # overall confidence below this → needs_review on answer
CLAIM_CONFIDENCE_FLOOR = 0.30  # claims below this confidence → blocked
PARTIAL_MATCH_CONFIDENCE = 0.55  # partial / single-token matches
HIGH_MATCH_CONFIDENCE = 0.90  # strong multi-token / exact-alias matches
DEFAULT_EMBED_DIM = 128

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # E:\202676

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Extract Chinese and English tokens (mirrors ``milvus_talent.embed``)."""
    return re.findall(
        r"[A-Za-z][A-Za-z0-9+.#-]*|[一-鿿]{1,4}|\d+(?:\.\d+)?",
        text.lower(),
    )


def _hash_embed(text: str, dim: int = DEFAULT_EMBED_DIM) -> list[float]:
    """Deterministic SHA‑256 feature‑hash embedding (same algorithm as TalentVectorStore.embed)."""
    vector = [0.0] * dim
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Optional Milvus / Neo4j retrieval interfaces
# ---------------------------------------------------------------------------


class MilvusEvidenceRetriever:
    """Optional Milvus‑backed evidence retrieval.

    Designed as a composable component — if ``store`` is ``None`` or the
    connection fails the caller falls back to local evidence.
    """

    def __init__(self, store: Any | None = None):
        self.store = store

    def search(self, claim: str, limit: int = 5) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        try:
            return self.store.search(claim, limit)
        except Exception:
            logger.debug("Milvus evidence retrieval unavailable", exc_info=True)
            return []


class Neo4jEvidenceRetriever:
    """Optional Neo4j‑backed knowledge‑graph evidence.

    Designed as a composable component — graceful degradation on absence/failure.
    """

    def __init__(self, graph: Any | None = None):
        self.graph = graph

    def related_subgraph(self, terms: list[str], limit: int = 40) -> dict[str, Any]:
        if self.graph is None:
            return {"nodes": [], "edges": [], "storage": "neo4j"}
        try:
            return self.graph.related_subgraph(terms, limit)
        except Exception:
            logger.debug("Neo4j evidence retrieval unavailable", exc_info=True)
            return {"nodes": [], "edges": [], "storage": "neo4j"}


# ---------------------------------------------------------------------------
# Built‑in minimal evidence (last-resort fallback)
# ---------------------------------------------------------------------------

_BUILTIN_COMPETENCIES: list[dict[str, Any]] = [
    {
        "id": "builtin_python",
        "name": "Python",
        "category": "skill",
        "aliases": ["python", "python3", "py"],
        "job_count": 1000,
        "source_files": ["built-in"],
        "related_roles": ["software-engineer"],
        "confidence": 0.70,
    },
    {
        "id": "builtin_java",
        "name": "Java",
        "category": "skill",
        "aliases": ["java", "spring"],
        "job_count": 1000,
        "source_files": ["built-in"],
        "related_roles": ["software-engineer"],
        "confidence": 0.70,
    },
    {
        "id": "builtin_sql",
        "name": "SQL",
        "category": "skill",
        "aliases": ["sql", "mysql", "数据库"],
        "job_count": 1000,
        "source_files": ["built-in"],
        "related_roles": ["software-engineer", "data-analyst"],
        "confidence": 0.70,
    },
    {
        "id": "builtin_linux",
        "name": "Linux",
        "category": "skill",
        "aliases": ["linux"],
        "job_count": 1000,
        "source_files": ["built-in"],
        "related_roles": ["software-engineer"],
        "confidence": 0.70,
    },
    {
        "id": "builtin_git",
        "name": "Git",
        "category": "skill",
        "aliases": ["git", "版本控制"],
        "job_count": 1000,
        "source_files": ["built-in"],
        "related_roles": ["software-engineer"],
        "confidence": 0.70,
    },
    {
        "id": "builtin_communication",
        "name": "沟通能力",
        "category": "requirement",
        "aliases": ["沟通", "团队协作", "表达能力"],
        "job_count": 1000,
        "source_files": ["built-in"],
        "related_roles": ["software-engineer", "product-manager"],
        "confidence": 0.60,
    },
    {
        "id": "builtin_bachelor",
        "name": "本科学历",
        "category": "requirement",
        "aliases": ["本科", "学士", "本科及以上"],
        "job_count": 1000,
        "source_files": ["built-in"],
        "related_roles": ["software-engineer", "data-analyst"],
        "confidence": 0.65,
    },
    {
        "id": "builtin_js",
        "name": "JavaScript",
        "category": "skill",
        "aliases": ["javascript", "js", "typescript", "前端"],
        "job_count": 1000,
        "source_files": ["built-in"],
        "related_roles": ["software-engineer", "frontend-engineer"],
        "confidence": 0.70,
    },
]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CompetitionRAGService:
    """Evidence‑based generation with hallucination prevention.

    Loads structured evidence from local files; every claim is verified against
    that evidence.  Claims without sources are blocked from publication.
    """

    def __init__(
        self,
        evidence_path: str | Path | None = None,
        audit_path: str | Path | None = None,
        milvus: Any | None = None,
        neo4j_graph: Any | None = None,
    ):
        self.evidence_path = Path(evidence_path or PROJECT_ROOT / "data" / "competition" / "evidence_sources.json")
        self.audit_path = Path(audit_path or PROJECT_ROOT / "data" / "competition" / "rag_audit.jsonl")
        self._milvus = MilvusEvidenceRetriever(milvus)
        self._neo4j = Neo4jEvidenceRetriever(neo4j_graph)

        # Indexes built at init
        self._alias_index: dict[str, dict[str, Any]] = {}
        self._comp_by_id: dict[str, dict[str, Any]] = {}
        self._role_index: dict[str, dict[str, Any]] = {}
        self._sources_used: list[str] = []
        self._load_evidence()

    # ------------------------------------------------------------------
    # Evidence loading
    # ------------------------------------------------------------------

    def _load_evidence(self) -> None:
        """Load evidence sources with layered fallback."""
        competencies: list[dict[str, Any]] = []
        roles: list[dict[str, Any]] = []

        # Layer 1: evidence_sources.json
        try:
            if self.evidence_path.exists():
                with open(self.evidence_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                competencies = data.get("competencies", [])
                roles = data.get("roles", [])
                self._sources_used.append(str(self.evidence_path))
                logger.info("Loaded %d competencies, %d roles from %s", len(competencies), len(roles), self.evidence_path)
            else:
                logger.warning("Evidence file not found: %s", self.evidence_path)
        except Exception:
            logger.exception("Failed to load %s", self.evidence_path)

        # Layer 2: unified_job_skills.csv (lightweight — sample first N rows)
        csv_comp = self._load_csv_competencies()
        if csv_comp:
            competencies.extend(csv_comp)
            self._sources_used.append("data/etl/unified_job_skills.csv")

        # Fallback: built-in
        if not competencies:
            competencies = _BUILTIN_COMPETENCIES
            self._sources_used.append("built-in")
            logger.warning("Using built-in minimal evidence (last-resort fallback)")

        # Build indexes
        self._comp_by_id = {}
        self._alias_index = {}
        for comp in competencies:
            cid = comp.get("id", "")
            self._comp_by_id[cid] = comp
            # Index by name + aliases (normalized)
            for alias in [comp.get("name", "")] + comp.get("aliases", []):
                key = alias.strip().lower()
                if key and key not in self._alias_index:
                    self._alias_index[key] = comp

        self._role_index = {r.get("id", ""): r for r in roles}
        # Also index role aliases
        for role in roles:
            for alias in role.get("aliases", []):
                key = alias.strip().lower()
                if key and key not in self._role_index:
                    self._role_index[key] = role

    def _load_csv_competencies(self) -> list[dict[str, Any]]:
        """Lightweight parse of unified_job_skills.csv for top skills."""
        csv_path = PROJECT_ROOT / "data" / "etl" / "unified_job_skills.csv"
        if not csv_path.exists():
            return []
        try:
            skill_counts: dict[str, int] = {}
            with open(csv_path, encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    skill = (row.get("normalized_skill") or row.get("skill") or "").strip()
                    if not skill:
                        continue
                    role = (row.get("role_id") or row.get("role_name") or "").strip()
                    skill_counts[skill] = skill_counts.get(skill, 0) + 1
            # Keep top N
            top = sorted(skill_counts.items(), key=lambda x: -x[1])[:200]
            competencies: list[dict[str, Any]] = []
            for skill_name, count in top:
                cid = f"csv_{_short_hash(skill_name)}"
                competencies.append(
                    {
                        "id": cid,
                        "name": skill_name,
                        "category": "skill",
                        "aliases": [],
                        "job_count": count,
                        "source_files": ["data/etl/unified_job_skills.csv"],
                        "related_roles": [],
                        "confidence": min(0.95, 0.5 + count / 10000),
                    }
                )
            return competencies
        except Exception:
            logger.debug("Could not parse CSV evidence", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Claim verification
    # ------------------------------------------------------------------

    def _find_evidence(
        self, claim_text: str, role_id: str
    ) -> tuple[list[dict[str, Any]], float]:
        """Return (matched_competencies, confidence) for a single claim."""
        tokens = _tokenize(claim_text)
        if not tokens:
            return [], 0.0

        matched: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        # Strategy 1: direct alias lookups
        for token in tokens:
            comp = self._alias_index.get(token)
            if comp and comp["id"] not in seen_ids:
                matched.append(comp)
                seen_ids.add(comp["id"])

        # Strategy 2: substring matching for longer Chinese tokens
        for token in tokens:
            if len(token) < 3:
                continue
            for alias, comp in self._alias_index.items():
                if comp["id"] in seen_ids:
                    continue
                if token in alias or alias in token:
                    matched.append(comp)
                    seen_ids.add(comp["id"])

        # Strategy 3: optional Milvus semantic search
        if not matched and self._milvus.store is not None:
            try:
                milvus_results = self._milvus.search(claim_text, limit=3)
                for mr in milvus_results:
                    mrid = mr.get("candidate_id") or mr.get("id") or ""
                    if mrid not in seen_ids:
                        matched.append(
                            {
                                "id": mrid,
                                "name": mr.get("name", ""),
                                "category": "milvus_match",
                                "aliases": [],
                                "job_count": 0,
                                "source_files": ["milvus"],
                                "related_roles": [],
                                "confidence": mr.get("score", 0.5),
                            }
                        )
                        seen_ids.add(mrid)
            except Exception:
                logger.debug("Milvus fallback search failed", exc_info=True)

        # Strategy 4: optional Neo4j evidence
        if not matched and self._neo4j.graph is not None:
            try:
                graph_evidence = self._neo4j.related_subgraph(tokens, limit=10)
                for node in graph_evidence.get("nodes", []):
                    nid = node.get("id", "")
                    if nid not in seen_ids:
                        matched.append(
                            {
                                "id": nid,
                                "name": node.get("label", ""),
                                "category": "kg_node",
                                "aliases": [],
                                "job_count": 0,
                                "source_files": ["neo4j"],
                                "related_roles": [],
                                "confidence": 0.60,
                            }
                        )
                        seen_ids.add(nid)
            except Exception:
                logger.debug("Neo4j fallback search failed", exc_info=True)

        # Calculate confidence
        if not matched:
            return [], 0.0

        # Confidence = weighted average of individual competency confidences
        # Boosted by match count (more matches → higher confidence)
        confidences = [c.get("confidence", 0.5) for c in matched]
        avg_conf = sum(confidences) / len(confidences)
        # Small bonus for multi-source corroboration
        unique_sources = len({s for c in matched for s in c.get("source_files", [])})
        corroboration_bonus = min(0.10, 0.02 * unique_sources)
        raw_confidence = min(1.0, avg_conf + corroboration_bonus)

        # Role relevance check: if evidence relates to the requested role, boost
        for c in matched:
            if role_id in c.get("related_roles", []):
                raw_confidence = min(1.0, raw_confidence + 0.05)
                break

        return matched, round(raw_confidence, 4)

    # ------------------------------------------------------------------
    # Answer generation
    # ------------------------------------------------------------------

    def _build_answer(
        self,
        claims: list[EvidenceClaim],
        blocked: list[EvidenceClaim],
        request: EvidenceGenerateRequest,
    ) -> str:
        """Build a deterministic, structured answer (NOT LLM-generated)."""
        parts: list[str] = []

        parts.append(f"【证据型评估报告】")
        parts.append(f"岗位角色：{request.role_id}")
        parts.append(f"评估问题：{request.question}")
        parts.append("")

        if claims:
            parts.append(f"## ✅ 已证实的声明（{len(claims)} 项）")
            for i, c in enumerate(claims, 1):
                sources = ", ".join(c.source_ids[:5]) if c.source_ids else "（来源已索引）"
                review_note = " ⚠️ 需人工复核" if c.needs_review else ""
                parts.append(f"{i}. {c.text}")
                parts.append(f"   置信度：{c.confidence:.0%} | 证据来源：{sources}{review_note}")
            parts.append("")

        if blocked:
            parts.append(f"## 🚫 因无证据被阻断的声明（{len(blocked)} 项）")
            parts.append("以下声明无法在现有证据源中找到支持，不予发布：")
            for i, c in enumerate(blocked, 1):
                parts.append(f"{i}. {c.text}  [无证据来源]")
            parts.append("")

        supported_count = len(claims)
        blocked_count = len(blocked)
        total = supported_count + blocked_count
        overall_conf = (
            sum(c.confidence for c in claims) / supported_count if supported_count else 0.0
        )

        parts.append("## 📊 质量评估")
        parts.append(f"- 申报声明总数：{total}")
        parts.append(f"- 证据支持：{supported_count} 项")
        parts.append(f"- 证据阻断：{blocked_count} 项")
        parts.append(f"- 整体置信度：{overall_conf:.1%}")

        if overall_conf < CONFIDENCE_THRESHOLD:
            parts.append(f"- ⚠️ 状态：需人工复核（置信度低于阈值 {CONFIDENCE_THRESHOLD:.0%}）")
        else:
            parts.append("- ✅ 状态：通过自动验证")

        parts.append("")
        parts.append(f"运行模式：离线证据匹配 | 时间：{datetime.now(UTC).isoformat()}")
        parts.append("注：本报告由证据型生成引擎自动生成，非大语言模型输出。")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def _write_audit(
        self,
        request: EvidenceGenerateRequest,
        claims: list[EvidenceClaim],
        blocked: list[EvidenceClaim],
        overall_confidence: float,
    ) -> str:
        """Write immutable audit record to JSONL and return audit_id."""
        audit_id = uuid.uuid4().hex[:16]
        supported_count = len(claims)
        blocked_count = len(blocked)

        needs_review = (
            overall_confidence < CONFIDENCE_THRESHOLD
            or blocked_count > 0
            or any(c.needs_review for c in claims)
        )

        record = AuditRecord(
            audit_id=audit_id,
            timestamp=datetime.now(UTC).isoformat(),
            mode="offline",
            request_summary={
                "role_id": request.role_id,
                "question_hash": _short_hash(request.question),
                "claim_count": len(request.candidate_claims),
            },
            sources_used=list(self._sources_used),
            results={
                "supported_count": supported_count,
                "blocked_count": blocked_count,
                "overall_confidence": overall_confidence,
                "needs_review": needs_review,
                "blocked_claims_text": [c.text for c in blocked],
            },
            review_status="needs_review" if needs_review else "auto",
        )

        try:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.audit_path, "a", encoding="utf-8") as fh:
                fh.write(record.model_dump_json() + "\n")
            logger.info("Audit record written: %s", audit_id)
        except Exception:
            logger.exception("Failed to write audit record")

        return audit_id

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def generate(self, request: EvidenceGenerateRequest) -> EvidenceGenerateResponse:
        """Run evidence-based generation for all claims."""
        claims: list[EvidenceClaim] = []
        blocked: list[EvidenceClaim] = []

        for claim_text in request.candidate_claims:
            matched, confidence = self._find_evidence(claim_text, request.role_id)

            if matched and confidence >= CLAIM_CONFIDENCE_FLOOR:
                source_ids = [
                    f"{c.get('id')}@{c.get('source_files', ['unknown'])[0]}"
                    for c in matched
                ]
                claims.append(
                    EvidenceClaim(
                        text=claim_text,
                        source_ids=source_ids,
                        supported=True,
                        confidence=confidence,
                        needs_review=confidence < CONFIDENCE_THRESHOLD,
                    )
                )
            else:
                # No evidence or confidence too low → blocked
                if matched:
                    # Had matches but below confidence floor
                    source_ids = [
                        f"{c.get('id')}@{c.get('source_files', ['unknown'])[0]}"
                        for c in matched
                    ]
                else:
                    source_ids = []
                blocked.append(
                    EvidenceClaim(
                        text=claim_text,
                        source_ids=source_ids,
                        supported=False,
                        confidence=confidence,
                        needs_review=True,
                    )
                )

        # Overall confidence
        supported_confidences = [c.confidence for c in claims]
        overall = (
            sum(supported_confidences) / len(supported_confidences)
            if supported_confidences
            else 0.0
        )
        overall = round(overall, 4)

        # Generate answer
        answer = self._build_answer(claims, blocked, request)

        # Write audit
        audit_id = self._write_audit(request, claims, blocked, overall)

        # Determine mode string
        mode_parts = ["offline"]
        if self._milvus.store is not None:
            mode_parts.append("milvus")
        if self._neo4j.graph is not None:
            mode_parts.append("neo4j")
        mode = "+".join(mode_parts)

        return EvidenceGenerateResponse(
            answer=answer,
            claims=claims,
            blocked_claims=blocked,
            confidence=overall,
            audit_id=audit_id,
            mode=mode,
        )


# ---------------------------------------------------------------------------
# Singleton convenience
# ---------------------------------------------------------------------------

_service: CompetitionRAGService | None = None


def get_competition_rag_service() -> CompetitionRAGService:
    """Return a module-level singleton (lazy init)."""
    global _service
    if _service is None:
        _service = CompetitionRAGService()
    return _service
