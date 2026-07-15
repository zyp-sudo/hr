from datetime import datetime, timezone

from app.services.es_mappings import INDEX_MAPPINGS, JOB_INDEX
from app.services.sync_service import JobPostingElasticsearchSyncService


def test_job_posting_document_mapping():
    doc = JobPostingElasticsearchSyncService.row_to_doc(
        {
            "record_id": "source:1",
            "job_title": "Java 后端工程师",
            "company": "示例公司",
            "city": "深圳",
            "published_at": "2026年6月8日",
            "collected_at": "2026-07-07T12:00:00+08:00",
            "normalized_category": "backend_engineering",
            "normalized_skills": "Java|SQL|Docker",
            "quality_score": "95",
            "quality_level": "A",
        }
    )
    assert doc["id"] == "source:1"
    assert doc["published_at"] == "2026-06-08"
    assert doc["skills"] == ["Java", "SQL", "Docker"]
    assert doc["industry"] == "backend_engineering"


def test_date_normalization():
    assert JobPostingElasticsearchSyncService._date(None) is None
    assert JobPostingElasticsearchSyncService._date("2026-07-01 12:30:00") == "2026-07-01T12:30:00"
    assert JobPostingElasticsearchSyncService._date(datetime.now(timezone.utc).isoformat())


def test_reconciliation_hash_has_an_explicit_keyword_mapping():
    assert INDEX_MAPPINGS[JOB_INDEX]["mappings"]["properties"]["sync_hash"] == {"type": "keyword"}
