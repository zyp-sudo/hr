from app.services.es_client import ElasticsearchClient
from app.core.config import get_settings
from app.db.session import engine
from app.services.storage_runtime import MySQLJobRepository, Neo4jGraphRepository


_settings = get_settings()
_job_repository = MySQLJobRepository(engine)
_graph_repository = Neo4jGraphRepository(
    _settings.neo4j_uri,
    _settings.neo4j_username,
    _settings.neo4j_password,
    _settings.neo4j_database,
)


def get_es() -> ElasticsearchClient:
    return ElasticsearchClient()


def get_job_repository() -> MySQLJobRepository:
    return _job_repository


def get_graph_repository() -> Neo4jGraphRepository:
    return _graph_repository
