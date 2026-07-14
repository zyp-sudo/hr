from app.services.es_client import ElasticsearchClient


def get_es() -> ElasticsearchClient:
    return ElasticsearchClient()
