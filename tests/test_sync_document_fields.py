from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.sync_service import JobPostingElasticsearchSyncService, MySQLToElasticsearchSyncService
from scripts.job_field_extraction import extract_education, extract_salary


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("计算机相关专业，本科及以上学历", "本科"),
        ("Master's degree in computer science", "硕士"),
        ("博士学历", "博士"),
        ("硕士及以上学历，博士优先", "硕士"),
        ("学历不限，博士优先", None),
        ("不限学历", None),
    ],
)
def test_extract_education_is_explicit(text, expected):
    assert extract_education(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("薪资 10-20K/月", (10000, 20000)),
        ("月薪 1.5-2.5万/月", (15000, 25000)),
        ("年薪30-60万/年", (25000, 50000)),
        ("$100-200 per day", None),
        ("项目规模 10-20", None),
    ],
)
def test_extract_salary_only_normalizes_supported_rmb_periods(text, expected):
    salary = extract_salary(text)
    assert ((salary.minimum, salary.maximum) if salary else None) == expected


def test_job_posting_document_uses_warehouse_fields():
    row = {
        "record_id": "source:1",
        "job_title": "Python 工程师",
        "company": "Example",
        "normalized_skills": "Python|SQL",
        "collected_at": "2026-07-01 12:00:00",
        "published_at": "2026-07-01",
        "education": "本科",
        "salary_min": 10000,
        "salary_max": 20000,
        "salary_text": "10-20K/月",
        "quality_score": "88",
    }
    doc = JobPostingElasticsearchSyncService.row_to_doc(row)
    assert doc["id"] == "source:1"
    assert doc["education"] == "本科"
    assert doc["salary_min"] == 10000
    assert doc["salary_max"] == 20000
    assert doc["skills"] == ["Python", "SQL"]
    assert doc["collected_at"] == "2026-07-01T12:00:00"


def test_job_posting_document_keeps_unknown_fields_null():
    doc = JobPostingElasticsearchSyncService.row_to_doc({"record_id": "1"})
    assert doc["education"] is None
    assert doc["salary_min"] is None
    assert doc["salary_max"] is None


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _Connection:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, _statement, _params):
        return _Rows(self.pages.pop(0))


class _Engine:
    def __init__(self, pages):
        self.pages = pages

    def connect(self):
        return _Connection(self.pages)


class _ES:
    def __init__(self):
        self.docs = []
        self.created = []
        self.refreshed = []

    def create_index(self, index, recreate=False):
        self.created.append((index, recreate))

    def bulk_index(self, _index, documents, chunk_size=0):
        self.docs.extend(documents)
        return len(documents), []

    def refresh(self, index):
        self.refreshed.append(index)


def test_job_posting_full_sync_pages_and_refreshes():
    pages = [[{"record_id": "1", "education": "本科", "salary_min": 1, "salary_max": 2}], []]
    es = _ES()
    service = JobPostingElasticsearchSyncService(_Engine(pages), es=es, batch_size=1)
    assert service.sync_all(recreate_index=True) == {"jobs": 1}
    assert es.created == [("job_index", True)]
    assert es.docs[0]["education"] == "本科"
    assert es.refreshed == ["job_index"]


def test_job_posting_sync_rejects_partial_bulk_errors():
    es = _ES()
    es.bulk_index = lambda *_args, **_kwargs: (0, [{"error": "bad"}])
    service = JobPostingElasticsearchSyncService(_Engine([[{"record_id": "1"}]]), es=es)
    with pytest.raises(RuntimeError, match="bulk indexing"):
        service._sync_rows(None, "")


def test_normalized_product_documents_and_sync_loops():
    skill = SimpleNamespace(id=3, name="Python", category="开发", level="高级", heat=1.5, related_job_count=2, updated_at=None)
    link = SimpleNamespace(skill=skill, required=True)
    job = SimpleNamespace(
        id=1, title="工程师", company_id=2, company_name="C", city="深圳", province="广东",
        country="中国", salary_min=10000, salary_max=20000, salary_text="10-20K/月",
        education="本科", experience="3年", description="开发", requirement="本科",
        industry="技术", job_type="全职", source="source", source_url="url",
        published_at=None, updated_at=None, skill_links=[link],
    )
    company = SimpleNamespace(id=2, name="C", industry="技术", size="100", region="深圳", description="d", recruiting_job_count=1, updated_at=None)
    resume = SimpleNamespace(id=4, user_id=5, title="R", raw_text="Python", education=["本科"], projects=["P"], skill_tags=["Python"], job_intention={"position": "工程师"}, parse_status="parsed", is_active=True, updated_at=None)
    assert MySQLToElasticsearchSyncService.job_to_doc(job)["required_skills"] == ["Python"]
    assert MySQLToElasticsearchSyncService.skill_to_doc(skill)["name"] == "Python"
    assert MySQLToElasticsearchSyncService.company_to_doc(company)["name"] == "C"
    assert MySQLToElasticsearchSyncService.resume_to_doc(resume)["job_intention"] == "工程师"

    service = object.__new__(MySQLToElasticsearchSyncService)
    service.es = _ES()
    service.batch_size = 2
    service._iter_jobs = lambda updated_since=None: [[job]]
    service._iter_by_id = lambda model, updated_since=None: [[skill]] if model.__name__ == "Skill" else ([[company]] if model.__name__ == "Company" else [[resume]])
    assert service.sync_jobs() == 1
    assert service.sync_skills() == 1
    assert service.sync_companies() == 1
    assert service.sync_resumes() == 1
    assert service._bulk_write("job_index", []) == 0


def test_normalized_bulk_failure_is_reported_as_zero():
    service = object.__new__(MySQLToElasticsearchSyncService)
    service.batch_size = 2
    service.es = SimpleNamespace(bulk_index=lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("down")))
    assert service._bulk_write("job_index", [{"id": 1}]) == 0
