import hashlib
import math
import re
from typing import Any

from pymilvus import DataType, MilvusClient


class TalentVectorStore:
    """Milvus-backed structured talent vectors for matching and RAG retrieval."""

    def __init__(self, uri: str, token: str, collection: str, dimension: int = 128):
        self.uri = uri
        self.token = token
        self.collection = collection
        self.dimension = dimension

    def _client(self) -> MilvusClient:
        kwargs: dict[str, Any] = {"uri": self.uri}
        if self.token:
            kwargs["token"] = self.token
        return MilvusClient(**kwargs)

    def _ensure_collection(self, client: MilvusClient) -> None:
        if client.has_collection(self.collection):
            return
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("candidate_id", DataType.VARCHAR, is_primary=True, max_length=128)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self.dimension)
        schema.add_field("name", DataType.VARCHAR, max_length=256)
        schema.add_field("profile_text", DataType.VARCHAR, max_length=8192)
        schema.add_field("updated_at", DataType.VARCHAR, max_length=64)
        indexes = client.prepare_index_params()
        indexes.add_index("vector", index_type="AUTOINDEX", metric_type="COSINE")
        client.create_collection(collection_name=self.collection, schema=schema, index_params=indexes)

    def embed(self, text: str) -> list[float]:
        """Deterministic feature-hashing embedding; replaceable with an external model later."""
        vector = [0.0] * self.dimension
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9+.#-]*|[\u4e00-\u9fff]{1,4}|\d+(?:\.\d+)?", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def upsert(self, candidate: dict[str, Any]) -> dict[str, Any]:
        client = self._client()
        self._ensure_collection(client)
        skills = candidate.get("skills") or []
        profile_text = "；".join(
            [
                f"姓名 {candidate.get('name') or '匿名候选人'}",
                f"技能 {'、'.join(map(str, skills))}",
                f"经验 {candidate.get('experienceYears') or 0} 年",
                f"学历 {candidate.get('education') or '未填写'}",
                f"项目能力 {candidate.get('projectScore') or 0}",
                f"协作能力 {candidate.get('collaborationScore') or 0}",
                str(candidate.get("profileText") or candidate.get("resumeText") or ""),
            ]
        )[:8192]
        row = {
            "candidate_id": str(candidate["id"]),
            "vector": self.embed(profile_text),
            "name": str(candidate.get("name") or "匿名候选人")[:256],
            "profile_text": profile_text,
            "updated_at": str(candidate.get("updatedAt") or candidate.get("createdAt") or "")[:64],
        }
        client.upsert(collection_name=self.collection, data=[row])
        return {"status": "stored", "collection": self.collection, "candidateId": row["candidate_id"]}

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        client = self._client()
        self._ensure_collection(client)
        rows = client.search(
            collection_name=self.collection,
            data=[self.embed(query)],
            limit=limit,
            output_fields=["candidate_id", "name", "profile_text", "updated_at"],
            search_params={"metric_type": "COSINE"},
        )
        return rows[0] if rows else []

    def health(self) -> dict[str, Any]:
        client = self._client()
        collections = client.list_collections()
        return {"status": "connected", "uri": self.uri, "collection": self.collection, "collectionReady": self.collection in collections}
