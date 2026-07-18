"""Competition evidence-based generation endpoint.

POST  /api/competition/evidence/generate

This router is intentionally NOT registered in ``app/api/router.py`` — the
integration owner will add it when ready.

Design:
- Every claim is verified against local evidence sources.
- Claims without ``source_ids`` are moved to ``blocked_claims``.
- Low-confidence results are flagged ``needs_review``.
- All runs produce an immutable audit record in ``data/competition/rag_audit.jsonl``.
- Milvus / Neo4j are optional and gated behind connectivity; the default path
  is deterministic offline matching — no external network calls.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas.competition_rag import EvidenceGenerateRequest, EvidenceGenerateResponse
from app.services.competition_rag import CompetitionRAGService, get_competition_rag_service

router = APIRouter(prefix="/api/competition/rag", tags=["competition-rag"])


# ---------------------------------------------------------------------------
# Dependency — allows test override via dependency_overrides
# ---------------------------------------------------------------------------


def _get_service(
    settings: Settings = Depends(get_settings),
) -> CompetitionRAGService:
    """Build service, optionally wiring Milvus / Neo4j when available."""
    service = get_competition_rag_service()

    # Wire optional Milvus — lazy, only if the URI looks real
    if settings.milvus_uri and "mock" not in settings.milvus_uri:
        try:
            from app.services.milvus_talent import TalentVectorStore

            store = TalentVectorStore(
                settings.milvus_uri,
                settings.milvus_token,
                settings.milvus_collection,
                settings.talent_vector_dim,
            )
            service._milvus.store = store
        except Exception:
            pass

    # Wire optional Neo4j — lazy
    if settings.neo4j_uri and "mock" not in settings.neo4j_uri:
        try:
            from app.api.deps import get_graph_repository

            service._neo4j.graph = get_graph_repository()
        except Exception:
            pass

    return service


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=EvidenceGenerateResponse)
def evidence_generate(
    body: EvidenceGenerateRequest,
    service: CompetitionRAGService = Depends(_get_service),
) -> EvidenceGenerateResponse:
    """Generate evidence‑backed answer with hallucination prevention.

    Every claim in ``candidate_claims`` is verified against structured evidence:
    - supported claims include ``source_ids`` ← evidence found
    - unsupported claims go to ``blocked_claims`` ← no evidence → cannot publish
    - low-confidence results are flagged ``needs_review``

    An audit record is written to ``data/competition/rag_audit.jsonl``.
    """
    try:
        return service.generate(body)
    except ValidationError:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"证据生成服务不可用: {type(exc).__name__}",
        ) from exc


# ---------------------------------------------------------------------------
# Health probe (informational — not required by spec but useful for ops)
# ---------------------------------------------------------------------------


@router.get("/health")
def evidence_health(
    service: CompetitionRAGService = Depends(_get_service),
) -> dict[str, Any]:
    """Return evidence-source health summary."""
    return {
        "status": "ok",
        "sources_loaded": list(service._sources_used),
        "competencies_indexed": len(service._comp_by_id),
        "roles_indexed": len(service._role_index),
        "alias_entries": len(service._alias_index),
        "milvus_wired": service._milvus.store is not None,
        "neo4j_wired": service._neo4j.graph is not None,
        "audit_path": str(service.audit_path),
    }


# ---------------------------------------------------------------------------
# Audit trail retrieval
# ---------------------------------------------------------------------------


@router.get("/audit")
def get_audit_trail(
    limit: int = Query(50, ge=1, le=500, description="返回最近 N 条审计记录"),
    service: CompetitionRAGService = Depends(_get_service),
) -> dict[str, Any]:
    """Return recent audit trail entries from rag_audit.jsonl.

    Each entry records a generate request with its evidence sources,
    blocked claims, and confidence scores.
    """
    import json

    entries: list[dict[str, Any]] = []
    audit_path = service.audit_path
    if audit_path.exists():
        with open(audit_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    # Return most recent first
    entries.reverse()
    return {
        "total": len(entries),
        "items": entries[:limit],
    }
