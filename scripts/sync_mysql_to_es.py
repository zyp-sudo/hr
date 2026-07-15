import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from dateutil.parser import isoparse
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import engine
from app.services.sync_service import JobPostingElasticsearchSyncService


DEFAULT_STATE_PATH = ROOT / "data" / "sync" / "elasticsearch_state.json"
SOURCE_PATH = ROOT / "data" / "etl" / "unified_jobs.csv"


def read_state(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def source_digest() -> str:
    digest = hashlib.sha256()
    with SOURCE_PATH.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def latest_watermark() -> tuple[str | None, str]:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT collected_at, MAX(record_id) AS record_id FROM job_postings "
                "WHERE collected_at = (SELECT MAX(collected_at) FROM job_postings) "
                "GROUP BY collected_at"
            )
        ).mappings().first()
    if not row:
        return None, ""
    return str(row["collected_at"]), str(row["record_id"] or "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync MySQL data to Elasticsearch.")
    parser.add_argument("--recreate-indices", action="store_true", help="Delete and recreate ES indices before full sync.")
    parser.add_argument("--updated-since", help="Incremental sync lower bound, for example 2026-07-01T00:00:00+08:00.")
    parser.add_argument("--auto", action="store_true", help="Full sync for an empty index, otherwise continue from the saved watermark.")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_PATH), help="Incremental watermark JSON path.")
    args = parser.parse_args()

    state_path = Path(args.state_file)
    state = read_state(state_path)
    digest = source_digest()
    updated_since: datetime | None = isoparse(args.updated_since) if args.updated_since else None
    service = JobPostingElasticsearchSyncService(engine)
    after_record_id = ""
    index_count = service.es.count()
    if (
        args.auto
        and not updated_since
        and index_count > 0
        and state.get("source_digest") == digest
        and state.get("max_collected_at")
    ):
        updated_since = isoparse(state["max_collected_at"])
        after_record_id = str(state.get("last_record_id") or "")

    if updated_since:
        result = service.sync_incremental(updated_since, after_record_id=after_record_id)
        mode = "incremental"
    else:
        recreate = args.recreate_indices or (args.auto and index_count > 0 and state.get("source_digest") != digest)
        result = service.sync_all(recreate_index=recreate)
        mode = "full"

    max_collected_at, last_record_id = latest_watermark()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": mode,
        "indexed": result,
        "max_collected_at": max_collected_at,
        "last_record_id": last_record_id,
        "source_digest": digest,
        "index_count": service.es.count(),
    }
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
