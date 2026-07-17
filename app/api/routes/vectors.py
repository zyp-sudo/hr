import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.api.deps import get_graph_repository
from app.services.milvus_talent import TalentVectorStore
from app.services.storage_runtime import Neo4jGraphRepository


router = APIRouter(prefix="/api/talent-vectors", tags=["milvus-talent-rag"])


class TalentProfile(BaseModel):
    id: str
    name: str = "匿名候选人"
    skills: list[str] = Field(default_factory=list)
    experienceYears: float = 0
    education: str = "未填写"
    projectScore: float = 0
    collaborationScore: float = 0
    profileText: str = ""
    resumeText: str = ""
    createdAt: str = ""
    updatedAt: str = ""


class VectorSearch(BaseModel):
    query: str = Field(min_length=2)
    limit: int = Field(default=5, ge=1, le=20)


def store(settings: Settings) -> TalentVectorStore:
    return TalentVectorStore(settings.milvus_uri, settings.milvus_token, settings.milvus_collection, settings.talent_vector_dim)


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return store(settings).health()
    except Exception as exc:
        return {"status": "unavailable", "uri": settings.milvus_uri, "collection": settings.milvus_collection, "detail": type(exc).__name__}


@router.post("/upsert")
def upsert(profile: TalentProfile, settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return store(settings).upsert(profile.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Milvus 人才向量写入失败: {exc}") from exc


@router.post("/search")
def search(request: VectorSearch, settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return {"items": store(settings).search(request.query, request.limit), "query": request.query}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Milvus 人才向量检索失败: {exc}") from exc


@router.post("/hybrid-search")
def hybrid_search(
    request: VectorSearch,
    graph: Annotated[Neo4jGraphRepository, Depends(get_graph_repository)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Combine semantic talent recall with a one-hop Neo4j evidence subgraph."""
    try:
        vector_items = store(settings).search(request.query, request.limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Milvus 人才向量检索失败: {exc}") from exc
    terms = [term for term in re.split(r"[\s,，、;/]+", request.query) if len(term.strip()) >= 2]
    try:
        subgraph = graph.related_subgraph(terms)
        graph_status = "connected"
    except Exception as exc:
        subgraph = {"nodes": [], "edges": [], "storage": "neo4j"}
        graph_status = f"unavailable: {type(exc).__name__}"
    return {
        "query": request.query,
        "talents": vector_items,
        "evidenceSubgraph": subgraph,
        "retrieval": {"vector": "milvus", "graph": graph_status, "strategy": "semantic-recall + one-hop-evidence"},
    }
