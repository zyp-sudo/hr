from __future__ import annotations

from app.services import es_client as module


class _Indices:
    def __init__(self):
        self.present = set()
        self.created = []
        self.deleted = []
        self.refreshed = []

    def exists(self, index):
        return index in self.present

    def create(self, index, **body):
        self.present.add(index)
        self.created.append((index, body))

    def delete(self, index):
        self.present.discard(index)
        self.deleted.append(index)

    def refresh(self, index):
        self.refreshed.append(index)


class FakeNativeES:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.indices = _Indices()
        self.searches = []
        self.indexed = []

    def ping(self):
        return True

    def count(self, index):
        return {"count": 7}

    def index(self, **kwargs):
        self.indexed.append(kwargs)

    def search(self, index, body):
        self.searches.append((index, body))
        return {"body": body}


def _client(monkeypatch):
    monkeypatch.setattr(module, "Elasticsearch", FakeNativeES)
    return module.ElasticsearchClient()


def test_index_lifecycle_and_document_operations(monkeypatch):
    client = _client(monkeypatch)
    assert client.ping()
    assert client.count("missing") == 0
    client.create_index("job_index")
    assert client.count("job_index") == 7
    client.refresh("job_index")
    client.index_document("job_index", 9, {"id": 9})
    client.create_index("job_index", recreate=True)
    assert client.client.indices.deleted == ["job_index"]
    client.delete_index("job_index")
    try:
        client.delete_index("job_index")
    except ValueError as exc:
        assert "Index not found" in str(exc)


def test_search_builds_real_filters_and_aggregations(monkeypatch):
    client = _client(monkeypatch)
    result = client.search_jobs(
        keyword="Python", city="深圳", industry="技术", education="本科",
        experience="3年", salary_min=10000, salary_max=30000,
        skills=["Python"], page=2, page_size=10,
    )
    body = result["body"]
    assert body["from"] == 10
    assert len(body["query"]["bool"]["filter"]) == 7
    assert body["query"]["bool"]["must"][0]["multi_match"]["query"] == "Python"
    assert "salary_ranges" in body["aggs"]
    assert client.search_jobs()["body"]["query"]["bool"]["must"] == [{"match_all": {}}]


def test_analysis_queries_and_bulk(monkeypatch):
    client = _client(monkeypatch)
    assert "hot_skills" in client.aggregate_skills(3)["body"]["aggs"]
    assert "by_date" in client.job_trend_analysis()["body"]["aggs"]
    assert client.get_skill_index_stats(4)["body"]["size"] == 4

    def fake_bulk(_native, actions, **_kwargs):
        values = list(actions)
        assert values[0]["_id"] == "1"
        return 1, []

    monkeypatch.setattr(module.helpers, "bulk", fake_bulk)
    assert client.bulk_index("job_index", [{"id": 1}]) == (1, [])
