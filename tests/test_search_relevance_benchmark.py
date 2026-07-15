from app.services.es_client import ElasticsearchClient
from scripts.evaluate_retrieval import ranked_metrics


class _FakeSearchClient:
    def __init__(self):
        self.body = None

    def search(self, *, index, body):
        self.body = body
        return {"hits": {"hits": []}}


def _client_with_fake_transport():
    service = object.__new__(ElasticsearchClient)
    service.client = _FakeSearchClient()
    return service


def test_keyword_search_is_relevance_first():
    service = _client_with_fake_transport()
    service.search_jobs(keyword="Java 后台")
    assert list(service.client.body["sort"][0]) == ["_score"]
    assert service.client.body["sort"][1]["published_at"]["order"] == "desc"


def test_browse_without_keyword_is_recency_first():
    service = _client_with_fake_transport()
    service.search_jobs()
    assert list(service.client.body["sort"][0]) == ["published_at"]


def test_ranked_metrics_use_graded_relevance():
    metrics = ranked_metrics(["irrelevant", "exact", "partial"], {"exact": 3, "partial": 1}, 3)
    assert metrics["mrr@3"] == 0.5
    assert 0 < metrics["ndcg@3"] < 1
    assert metrics["judged_coverage@3"] == 0.6667
