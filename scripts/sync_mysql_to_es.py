import argparse
from datetime import datetime

from dateutil.parser import isoparse

from app.db.session import SessionLocal
from app.services.sync_service import MySQLToElasticsearchSyncService


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync MySQL data to Elasticsearch.")
    parser.add_argument("--recreate-indices", action="store_true", help="Delete and recreate ES indices before full sync.")
    parser.add_argument("--updated-since", help="Incremental sync lower bound, for example 2026-07-01T00:00:00+08:00.")
    args = parser.parse_args()

    updated_since: datetime | None = isoparse(args.updated_since) if args.updated_since else None
    with SessionLocal() as db:
        service = MySQLToElasticsearchSyncService(db)
        if updated_since:
            result = service.sync_incremental(updated_since)
        else:
            result = service.sync_all(recreate_indices=args.recreate_indices)
    print(result)


if __name__ == "__main__":
    main()
