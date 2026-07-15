"""Reconcile MySQL jobs with Elasticsearch by primary key and row hash."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from dateutil.parser import isoparse
from elasticsearch import helpers
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import engine
from app.services.es_mappings import JOB_INDEX
from app.services.sync_service import JobPostingElasticsearchSyncService
from scripts.bootstrap_storage import atomic_write_json, exclusive_lock, file_digest


DEFAULT_STATE_PATH = ROOT / "data" / "sync" / "elasticsearch_state.json"
SOURCE_PATH = ROOT / "data" / "etl" / "unified_jobs.csv"


def canonical_row_hash(row: dict[str, Any]) -> str:
    payload = json.dumps(
        row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def elasticsearch_hashes(service: JobPostingElasticsearchSyncService) -> dict[str, str]:
    if not service.es.client.indices.exists(index=JOB_INDEX):
        return {}
    result: dict[str, str] = {}
    for hit in helpers.scan(
        service.es.client,
        index=JOB_INDEX,
        query={"query": {"match_all": {}}, "_source": ["sync_hash"]},
        size=1000,
        preserve_order=False,
    ):
        result[str(hit["_id"])] = str(hit.get("_source", {}).get("sync_hash") or "")
    return result


def mysql_rows(batch_size: int) -> Iterable[list[dict[str, Any]]]:
    last_id = ""
    while True:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT * FROM job_postings WHERE record_id > :last_id "
                    "ORDER BY record_id LIMIT :batch_size"
                ),
                {"last_id": last_id, "batch_size": batch_size},
            ).mappings().all()
        if not rows:
            break
        batch = [dict(row) for row in rows]
        yield batch
        last_id = str(batch[-1]["record_id"])


def reconcile(service: JobPostingElasticsearchSyncService, batch_size: int) -> dict[str, int]:
    """Apply only changed documents and propagate source deletions."""
    service.es.create_index(JOB_INDEX, recreate=False)
    es_hash_by_id = elasticsearch_hashes(service)
    source_ids: set[str] = set()
    indexed = 0
    unchanged = 0
    for rows in mysql_rows(batch_size):
        changed_documents: list[dict[str, Any]] = []
        for row in rows:
            record_id = str(row.get("record_id") or "")
            source_ids.add(record_id)
            sync_hash = canonical_row_hash(row)
            if es_hash_by_id.get(record_id) == sync_hash:
                unchanged += 1
                continue
            document = service.row_to_doc(row)
            document["sync_hash"] = sync_hash
            changed_documents.append(document)
        if changed_documents:
            success, errors = service.es.bulk_index(
                JOB_INDEX, changed_documents, chunk_size=batch_size
            )
            if errors:
                raise RuntimeError(f"Elasticsearch indexing returned {len(errors)} errors")
            indexed += success

    deleted_ids = sorted(set(es_hash_by_id) - source_ids)
    deleted = 0
    if deleted_ids:
        deleted, errors = helpers.bulk(
            service.es.client.options(request_timeout=60),
            (
                {"_op_type": "delete", "_index": JOB_INDEX, "_id": record_id}
                for record_id in deleted_ids
            ),
            chunk_size=batch_size,
            raise_on_error=False,
        )
        if errors:
            raise RuntimeError(f"Elasticsearch deletion returned {len(errors)} errors")
    service.es.refresh(JOB_INDEX)
    return {
        "source_count": len(source_ids),
        "scanned_index_count": len(es_hash_by_id),
        "indexed": indexed,
        "unchanged": unchanged,
        "deleted": deleted,
        "index_count": service.es.count(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recreate-indices", action="store_true")
    parser.add_argument(
        "--updated-since",
        help="Deprecated hint; validated, but all ids/hashes are reconciled for correctness.",
    )
    parser.add_argument("--auto", action="store_true", help="Compatibility flag.")
    parser.add_argument("--batch-size", type=int, default=800)
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_PATH))
    args = parser.parse_args()
    if args.updated_since:
        isoparse(args.updated_since)

    state_path = Path(args.state_file)
    with exclusive_lock(state_path.with_suffix(state_path.suffix + ".lock")):
        service = JobPostingElasticsearchSyncService(engine, batch_size=args.batch_size)
        if args.recreate_indices:
            service.es.create_index(JOB_INDEX, recreate=True)
        result = reconcile(service, args.batch_size)
        payload: dict[str, Any] = {
            "mode": "primary_key_hash_reconciliation",
            **result,
            "source_digest": file_digest(SOURCE_PATH),
            "updated_since_hint": args.updated_since,
        }
        atomic_write_json(state_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
