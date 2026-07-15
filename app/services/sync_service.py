from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import Select, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models import Company, Job, JobSkill, Resume, Skill
from app.services.es_client import ElasticsearchClient
from app.services.es_mappings import COMPANY_INDEX, JOB_INDEX, RESUME_INDEX, SKILL_INDEX
from app.utils.time import to_iso

logger = logging.getLogger(__name__)


class MySQLToElasticsearchSyncService:
    def __init__(self, db: Session, es: ElasticsearchClient | None = None, batch_size: int | None = None) -> None:
        self.db = db
        self.es = es or ElasticsearchClient()
        self.batch_size = batch_size or get_settings().sync_batch_size

    def sync_all(self, recreate_indices: bool = False) -> dict[str, int]:
        self.es.create_all_indices(recreate=recreate_indices)
        return {
            "jobs": self.sync_jobs(),
            "skills": self.sync_skills(),
            "companies": self.sync_companies(),
            "resumes": self.sync_resumes(),
        }

    def sync_incremental(self, updated_since: datetime) -> dict[str, int]:
        self.es.create_all_indices(recreate=False)
        return {
            "jobs": self.sync_jobs(updated_since=updated_since),
            "skills": self.sync_skills(updated_since=updated_since),
            "companies": self.sync_companies(updated_since=updated_since),
            "resumes": self.sync_resumes(updated_since=updated_since),
        }

    def sync_jobs(self, updated_since: datetime | None = None) -> int:
        total = 0
        for batch in self._iter_jobs(updated_since=updated_since):
            docs = [self.job_to_doc(job) for job in batch]
            total += self._bulk_write(JOB_INDEX, docs)
        return total

    def sync_skills(self, updated_since: datetime | None = None) -> int:
        total = 0
        for batch in self._iter_by_id(Skill, updated_since=updated_since):
            docs = [self.skill_to_doc(skill) for skill in batch]
            total += self._bulk_write(SKILL_INDEX, docs)
        return total

    def sync_companies(self, updated_since: datetime | None = None) -> int:
        total = 0
        for batch in self._iter_by_id(Company, updated_since=updated_since):
            docs = [self.company_to_doc(company) for company in batch]
            total += self._bulk_write(COMPANY_INDEX, docs)
        return total

    def sync_resumes(self, updated_since: datetime | None = None) -> int:
        total = 0
        for batch in self._iter_by_id(Resume, updated_since=updated_since):
            docs = [self.resume_to_doc(resume) for resume in batch]
            total += self._bulk_write(RESUME_INDEX, docs)
        return total

    def _iter_jobs(self, updated_since: datetime | None = None) -> Iterable[list[Job]]:
        last_id = 0
        while True:
            stmt = (
                select(Job)
                .options(selectinload(Job.company), selectinload(Job.skill_links).selectinload(JobSkill.skill))
                .where(Job.id > last_id)
                .order_by(Job.id)
                .limit(self.batch_size)
            )
            if updated_since:
                stmt = stmt.where(Job.updated_at >= updated_since)
            rows = list(self.db.scalars(stmt))
            if not rows:
                break
            yield rows
            last_id = rows[-1].id

    def _iter_by_id(self, model: type[Any], updated_since: datetime | None = None) -> Iterable[list[Any]]:
        last_id = 0
        while True:
            stmt: Select[Any] = select(model).where(model.id > last_id).order_by(model.id).limit(self.batch_size)
            if updated_since:
                stmt = stmt.where(model.updated_at >= updated_since)
            rows = list(self.db.scalars(stmt))
            if not rows:
                break
            yield rows
            last_id = rows[-1].id

    def _bulk_write(self, index_name: str, docs: list[dict[str, Any]]) -> int:
        if not docs:
            return 0
        try:
            success, errors = self.es.bulk_index(index_name, docs, chunk_size=self.batch_size)
            if errors:
                logger.warning("ES bulk write partial errors index=%s errors=%s", index_name, errors[:3])
            return success
        except Exception:
            logger.exception("ES bulk write failed index=%s count=%s", index_name, len(docs))
            return 0

    @staticmethod
    def job_to_doc(job: Job) -> dict[str, Any]:
        skills = [link.skill.name for link in job.skill_links if link.skill]
        required_skills = [link.skill.name for link in job.skill_links if link.skill and link.required]
        return {
            "id": job.id,
            "title": job.title,
            "company_id": job.company_id,
            "company_name": job.company_name,
            "city": job.city,
            "province": job.province,
            "country": job.country,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_text": job.salary_text,
            "education": job.education,
            "experience": job.experience,
            "description": job.description,
            "requirement": job.requirement,
            "industry": job.industry,
            "job_type": job.job_type,
            "source": job.source,
            "source_url": job.source_url,
            "published_at": to_iso(job.published_at),
            "updated_at": to_iso(job.updated_at),
            "skills": skills,
            "skill_text": " ".join(skills),
            "required_skills": required_skills,
        }

    @staticmethod
    def skill_to_doc(skill: Skill) -> dict[str, Any]:
        return {
            "id": skill.id,
            "name": skill.name,
            "name_keyword": skill.name,
            "category": skill.category,
            "level": skill.level,
            "heat": skill.heat,
            "related_job_count": skill.related_job_count,
            "updated_at": to_iso(skill.updated_at),
        }

    @staticmethod
    def company_to_doc(company: Company) -> dict[str, Any]:
        return {
            "id": company.id,
            "name": company.name,
            "industry": company.industry,
            "size": company.size,
            "region": company.region,
            "description": company.description,
            "recruiting_job_count": company.recruiting_job_count,
            "updated_at": to_iso(company.updated_at),
        }

    @staticmethod
    def resume_to_doc(resume: Resume) -> dict[str, Any]:
        education_text = " ".join(str(item) for item in (resume.education or []))
        project_text = " ".join(str(item) for item in (resume.projects or []))
        intention = resume.job_intention or {}
        return {
            "id": resume.id,
            "user_id": resume.user_id,
            "title": resume.title,
            "raw_text": resume.raw_text,
            "education_text": education_text,
            "project_text": project_text,
            "skill_tags": resume.skill_tags or [],
            "job_intention": intention.get("position") if isinstance(intention, dict) else None,
            "parse_status": resume.parse_status,
            "is_active": resume.is_active,
            "updated_at": to_iso(resume.updated_at),
        }


class JobPostingElasticsearchSyncService:
    """Synchronize the ETL warehouse table used by the running application.

    The original ORM sync service targets the normalized product schema. The
    runnable MVP imports `data/etl/unified_jobs.csv` into `job_postings`, so the
    public search API must index that table instead.
    """

    def __init__(self, engine: Engine, es: ElasticsearchClient | None = None, batch_size: int | None = None) -> None:
        self.engine = engine
        self.es = es or ElasticsearchClient()
        self.batch_size = batch_size or get_settings().sync_batch_size

    def sync_all(self, recreate_index: bool = False) -> dict[str, int]:
        self.es.create_index(JOB_INDEX, recreate=recreate_index)
        indexed = self._sync_rows(updated_since=None, after_record_id="")
        self.es.refresh(JOB_INDEX)
        return {"jobs": indexed}

    def sync_incremental(self, updated_since: datetime, after_record_id: str = "") -> dict[str, int]:
        self.es.create_index(JOB_INDEX, recreate=False)
        indexed = self._sync_rows(updated_since=updated_since, after_record_id=after_record_id)
        self.es.refresh(JOB_INDEX)
        return {"jobs": indexed}

    def _sync_rows(self, updated_since: datetime | None, after_record_id: str) -> int:
        total = 0
        last_id = ""
        since = updated_since.isoformat() if updated_since else None
        while True:
            statement = text(
                """
                SELECT record_id, source_id, source_name, source_url, collected_at,
                       published_at, country, province, city, company,
                       normalized_category, job_title, job_type, work_years,
                       education, salary_min, salary_max, salary_text,
                       responsibility, requirement, normalized_skills,
                       quality_score, quality_level, content_hash
                FROM job_postings
                WHERE record_id > :last_id
                  AND (
                    :updated_since IS NULL
                    OR collected_at > :updated_since
                    OR (collected_at = :updated_since AND record_id > :after_record_id)
                  )
                ORDER BY record_id
                LIMIT :batch_size
                """
            )
            with self.engine.connect() as connection:
                rows = connection.execute(
                    statement,
                    {
                        "last_id": last_id,
                        "updated_since": since,
                        "after_record_id": after_record_id,
                        "batch_size": self.batch_size,
                    },
                ).mappings().all()
            if not rows:
                break
            documents = [self.row_to_doc(dict(row)) for row in rows]
            success, errors = self.es.bulk_index(JOB_INDEX, documents, chunk_size=self.batch_size)
            if errors:
                raise RuntimeError(f"Elasticsearch bulk indexing returned {len(errors)} errors")
            total += success
            last_id = str(rows[-1]["record_id"])
        return total

    @staticmethod
    def _date(value: object) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        chinese = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", raw)
        if chinese:
            return f"{chinese.group(1)}-{int(chinese.group(2)):02d}-{int(chinese.group(3)):02d}"
        return raw.replace(" ", "T", 1) if " " in raw and "T" not in raw else raw

    @classmethod
    def row_to_doc(cls, row: dict[str, Any]) -> dict[str, Any]:
        skills = [item for item in str(row.get("normalized_skills") or "").split("|") if item]
        collected_at = cls._date(row.get("collected_at"))
        return {
            "id": str(row.get("record_id") or ""),
            "title": row.get("job_title") or "",
            "company_id": row.get("company") or None,
            "company_name": row.get("company") or None,
            "city": row.get("city") or None,
            "province": row.get("province") or None,
            "country": row.get("country") or None,
            "salary_min": int(row["salary_min"]) if row.get("salary_min") is not None else None,
            "salary_max": int(row["salary_max"]) if row.get("salary_max") is not None else None,
            "salary_text": row.get("salary_text") or None,
            "education": row.get("education") or None,
            "experience": row.get("work_years") or None,
            "description": row.get("responsibility") or "",
            "requirement": row.get("requirement") or "",
            "industry": row.get("normalized_category") or None,
            "job_type": row.get("job_type") or None,
            "source": row.get("source_name") or row.get("source_id") or None,
            "source_url": row.get("source_url") or None,
            "published_at": cls._date(row.get("published_at")),
            "collected_at": collected_at,
            "updated_at": collected_at,
            "skills": skills,
            "skill_text": " ".join(skills),
            "required_skills": skills,
            "quality_score": int(row.get("quality_score") or 0),
            "quality_level": row.get("quality_level") or None,
            "content_hash": row.get("content_hash") or None,
        }
