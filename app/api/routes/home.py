"""Public homepage endpoints — available without authentication.

The ``/api/home/demo-jobs`` endpoint returns exactly 10 curated job records
from MySQL. These are used by the unauthenticated homepage.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/home", tags=["home-public"])


@router.get("/demo-jobs")
def demo_jobs() -> dict:
    """Return the 10 static demo job records — no auth required.

    This is the ONLY data endpoint available to unauthenticated users.
    It reads from the ``demo_homepage_jobs`` table and returns all fields.
    """
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, title, company, city, salary, skills, summary, "
                    "industry, sort_order "
                    "FROM demo_homepage_jobs "
                    "ORDER BY sort_order ASC, id ASC"
                )
            ).fetchall()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"MySQL 数据源不可用: {type(exc).__name__}",
        ) from exc

    items = [
        {
            "id": row.id,
            "title": row.title,
            "company": row.company,
            "city": row.city,
            "salary": row.salary,
            "skills": [s.strip() for s in (row.skills or "").split(",") if s.strip()],
            "summary": row.summary,
            "industry": row.industry,
            "sort_order": row.sort_order,
        }
        for row in rows
    ]

    return {
        "total": len(items),
        "items": items,
        "is_demo": True,
    }
