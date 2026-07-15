from types import SimpleNamespace

from scripts import sync_mysql_to_es as sync


class _Indices:
    def exists(self, *, index):
        return True


class _RawClient:
    indices = _Indices()

    def options(self, **kwargs):
        return self


class _FakeEs:
    def __init__(self):
        self.client = _RawClient()
        self.indexed = []
        self.refreshed = False

    def create_index(self, index, recreate=False):
        return None

    def bulk_index(self, index, documents, chunk_size):
        self.indexed.extend(documents)
        return len(documents), []

    def refresh(self, index):
        self.refreshed = True

    def count(self):
        return 2


def test_es_reconciliation_updates_old_rows_and_propagates_deletes(monkeypatch):
    rows = [{"record_id": "same", "job_title": "same"}, {"record_id": "updated", "job_title": "new"}]
    same_hash = sync.canonical_row_hash(rows[0])
    monkeypatch.setattr(sync, "mysql_rows", lambda batch_size: [rows])
    monkeypatch.setattr(sync, "elasticsearch_hashes", lambda service: {"same": same_hash, "updated": "old", "deleted": "old"})
    deleted = []

    def fake_bulk(client, actions, **kwargs):
        materialized = list(actions)
        deleted.extend(action["_id"] for action in materialized)
        return len(materialized), []

    monkeypatch.setattr(sync.helpers, "bulk", fake_bulk)
    es = _FakeEs()
    service = SimpleNamespace(es=es, row_to_doc=lambda row: {"id": row["record_id"], "title": row["job_title"]})
    result = sync.reconcile(service, 100)
    assert [document["id"] for document in es.indexed] == ["updated"]
    assert deleted == ["deleted"]
    assert result["indexed"] == 1
    assert result["unchanged"] == 1
    assert result["deleted"] == 1
    assert es.refreshed is True
