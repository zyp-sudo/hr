import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "人岗智能匹配与能力图谱系统"
    mysql_url: str = os.getenv(
        "MYSQL_URL",
        "mysql+pymysql://root:password@localhost:3306/talent_graph?charset=utf8mb4",
    )
    es_hosts: list[str] = [os.getenv("ES_HOST", "http://localhost:9200")]
    es_username: str | None = os.getenv("ES_USERNAME")
    es_password: str | None = os.getenv("ES_PASSWORD")
    es_verify_certs: bool = os.getenv("ES_VERIFY_CERTS", "false").lower() == "true"
    sync_batch_size: int = int(os.getenv("SYNC_BATCH_SIZE", "800"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
