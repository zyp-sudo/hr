"""Restore the tracked 55k job snapshot and merge the latest collected rows.

The crawler normally appends to ``data/collected_jobs.csv``. If that file was
accidentally reset, the ETL and runtime stores shrink to the latest crawl only.
This recovery keeps the current rows, merges them over the tracked snapshot,
and rebuilds the ETL outputs without discarding newer postings.
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
JOBS_PATH = DATA / "collected_jobs.csv"
SKILLS_PATH = DATA / "collected_job_skills.csv"


def tracked_rows(path: Path) -> list[dict[str, str]]:
    relative = path.relative_to(ROOT).as_posix()
    completed = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    text = completed.stdout.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def current_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def job_key(row: dict[str, str]) -> tuple[str, ...]:
    source = (row.get("source") or "").strip().lower()
    post_id = (row.get("postId") or "").strip()
    if post_id:
        return ("id", source, post_id)
    return (
        "content",
        source,
        (row.get("title") or "").strip().lower(),
        (row.get("company") or "").strip().lower(),
        (row.get("city") or "").strip().lower(),
        (row.get("sourceUrl") or "").strip().lower(),
    )


def skill_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        (row.get("source") or "").strip().lower(),
        (row.get("postId") or "").strip(),
        (row.get("skill") or "").strip().lower(),
    )


def merge_rows(
    historical: list[dict[str, str]],
    latest: list[dict[str, str]],
    key: Callable[[dict[str, str]], tuple[str, ...]],
) -> list[dict[str, str]]:
    merged: dict[tuple[str, ...], dict[str, str]] = {}
    for row in historical:
        merged[key(row)] = row
    for row in latest:
        merged[key(row)] = row
    return list(merged.values())


def atomic_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise RuntimeError(f"Refusing to replace {path} with an empty dataset")
    fields = list(rows[0])
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8-sig",
        newline="",
        suffix=f"-{path.name}",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    try:
        shutil.copyfile(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ROOT) / f"job-history-recovery-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(JOBS_PATH, backup_dir / JOBS_PATH.name)
    shutil.copy2(SKILLS_PATH, backup_dir / SKILLS_PATH.name)

    latest_jobs = current_rows(JOBS_PATH)
    latest_skills = current_rows(SKILLS_PATH)
    merged_jobs = merge_rows(tracked_rows(JOBS_PATH), latest_jobs, job_key)
    merged_skills = merge_rows(tracked_rows(SKILLS_PATH), latest_skills, skill_key)

    atomic_csv(JOBS_PATH, merged_jobs)
    atomic_csv(SKILLS_PATH, merged_skills)

    from etl_unify_jobs import transform

    manifest = transform()
    print(
        {
            "historical_jobs": len(merged_jobs) - len(latest_jobs),
            "latest_rows_considered": len(latest_jobs),
            "merged_jobs": len(merged_jobs),
            "merged_skill_evidence": len(merged_skills),
            "etl_jobs": manifest["unified_job_records"],
            "backup": str(backup_dir),
        }
    )


if __name__ == "__main__":
    main()
