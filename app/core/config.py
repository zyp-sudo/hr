import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    # ---- application ---------------------------------------------------
    app_name: str = "人岗智能匹配与能力图谱系统"
    app_name_en: str = "XH-202621 Talent-Match Intelligent Assessment System"

    # ---- MySQL ---------------------------------------------------------
    mysql_url: str = os.getenv(
        "MYSQL_URL",
        "mysql+pymysql://root:password@localhost:3307/job_kg?charset=utf8mb4",
    )

    # ---- Neo4j ---------------------------------------------------------
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_username: str = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password123")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")
    graph_node_limit: int = int(os.getenv("GRAPH_NODE_LIMIT", "160"))

    # ---- Java proxy ----------------------------------------------------
    java_backend_url: str = os.getenv("JAVA_BACKEND_URL", "http://localhost:8081")
    proxy_timeout: int = int(os.getenv("PROXY_TIMEOUT", "60"))

    # ---- Elasticsearch -------------------------------------------------
    es_hosts: list[str] = [os.getenv("ES_HOST", "http://localhost:9200")]
    es_username: str | None = os.getenv("ES_USERNAME")
    es_password: str | None = os.getenv("ES_PASSWORD")
    es_verify_certs: bool = os.getenv("ES_VERIFY_CERTS", "false").lower() == "true"

    # ---- Batch sync ----------------------------------------------------
    sync_batch_size: int = int(os.getenv("SYNC_BATCH_SIZE", "800"))

    # ---- Milvus --------------------------------------------------------
    milvus_uri: str = os.getenv("MILVUS_URI", "http://localhost:19530")
    milvus_token: str = os.getenv("MILVUS_TOKEN", "")
    milvus_collection: str = os.getenv("MILVUS_COLLECTION", "talent_profiles")
    talent_vector_dim: int = int(os.getenv("TALENT_VECTOR_DIM", "128"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
