"""Build competition annotation sets from real ETL job data.

This script produces three human-annotation templates under
data/benchmarks/competition/:

1. jd_parsing_annotation_template.csv
   - Sampled real jobs with empty annotation columns for skills, responsibilities,
     education, and experience years.
   - Annotators fill in ground-truth values by reading the raw job text.

2. resume_extraction_annotation_template.csv
   - Placeholder entries for de-identified resumes, each with empty annotation
     columns for skills, education, years, projects, and certifications.
   - Annotators must source or create de-identified resumes independently and
     fill in the ground truth.

3. person_job_matching_annotation_template.csv
   - Job–resume pairs with empty label and rationale columns.
   - Annotators assign match / partial_match / no_match with a brief rationale.

All sampling uses a fixed random seed (42) for reproducibility.  Annotation
columns are deliberately left blank — this script does NOT generate synthetic
"ground truth" and does NOT claim annotation completeness.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIFIED_JOBS_PATH = ROOT / "data" / "etl" / "unified_jobs.csv"
COMPETITION_DIR = ROOT / "data" / "benchmarks" / "competition"
SEED = 42

# ── JD parsing annotation fields ──────────────────────────────────────────
JD_ANNOTATION_FIELDS = [
    "job_record_id",
    "job_title",
    "company",
    "category",
    "responsibility",
    "requirement",
    # Machine-extracted reference (for annotator convenience, not ground truth)
    "machine_skills",
    "machine_education",
    "machine_work_years",
    # ── Human annotation columns (to be filled by annotators) ──
    "annotator_id",
    "annotation_date",
    "annotated_skills",            # pipe-separated canonical skill names
    "annotated_responsibilities",  # pipe-separated key responsibility phrases
    "annotated_education",         # e.g. 本科 / 硕士 / 博士 / 不限
    "annotated_experience_years",  # integer, minimum required years
    "annotation_notes",
]

# ── Resume extraction annotation fields ───────────────────────────────────
RESUME_ANNOTATION_FIELDS = [
    "resume_id",
    "resume_text_placeholder",     # de-identified resume text (annotator-provided)
    # ── Human annotation columns ──
    "annotator_id",
    "annotation_date",
    "annotated_skills",            # pipe-separated canonical skill names
    "annotated_education",         # highest degree
    "annotated_experience_years",  # total years of experience
    "annotated_projects",          # pipe-separated project names / descriptions
    "annotated_certifications",    # pipe-separated certification names
    "annotation_notes",
]

# ── Person-job matching annotation fields ─────────────────────────────────
MATCHING_ANNOTATION_FIELDS = [
    "pair_id",
    "job_record_id",
    "job_title",
    "company",
    "job_skills",
    "job_education",
    "job_experience_years",
    "resume_id",
    "resume_summary_placeholder",   # brief de-identified summary (annotator-provided)
    # ── Human annotation columns ──
    "annotator_id",
    "annotation_date",
    "match_label",                  # match / partial_match / no_match
    "match_rationale",              # brief justification
    "annotation_notes",
]

MANIFEST_FIELDS = [
    "dataset",
    "file_name",
    "record_count",
    "annotation_status",
    "annotator_count",
    "notes",
]

# ── Overwrite protection ────────────────────────────────────────────────────
# Fields whose non-empty values indicate human annotation work has been done.
# The builder will refuse to overwrite any CSV that contains data in these
# fields, even with --force.

_HUMAN_ANNOTATION_EXACT_FIELDS = frozenset({
    "annotator_id",
    "annotation_date",
    "annotation_notes",
    "match_label",
    "match_rationale",
})

_HUMAN_ANNOTATION_PREFIXES = ("annotated_",)

# Keywords matched case-insensitively against field names.  "裁决" and "仲裁"
# cover Chinese arbitration / judgment fields; "reviewer" and "arbitration"
# cover English variants.
_HUMAN_ANNOTATION_KEYWORDS = ("reviewer", "裁决", "arbitration", "仲裁")


def _has_human_annotations(path: Path):
    """Check whether a CSV annotation template contains human-filled data.

    Returns ``(has_annotations: bool, found_fields: set[str])``.
    ``found_fields`` is the set of field *names* (not values) that have
    at least one non-empty cell — safe to include in error messages.
    """
    if not path.exists():
        return False, set()

    records = _read_csv(path)
    found: set[str] = set()

    for row in records:
        for field, value in row.items():
            if not str(value).strip():
                continue
            field_lower = field.lower()
            # Exact field-name match
            if field in _HUMAN_ANNOTATION_EXACT_FIELDS:
                found.add(field)
            # Prefix match  (annotated_skills, annotated_education, …)
            elif any(field.startswith(p) for p in _HUMAN_ANNOTATION_PREFIXES):
                found.add(field)
            # Keyword match in field name (reviewer, arbitration, 裁决, 仲裁)
            elif any(kw in field_lower for kw in _HUMAN_ANNOTATION_KEYWORDS):
                found.add(field)

    return len(found) > 0, found


def _check_targets(targets: dict[str, Path], force: bool) -> list[str]:
    """Pre-check every annotation target before writing *any* of them.

    Returns a list of human-readable rejection reasons (one per failing
    target).  An empty list means all targets are safe to write.
    """
    reasons: list[str] = []

    for name, path in targets.items():
        if not path.exists():
            continue

        if not force:
            reasons.append(
                f"{name} already exists: {path}\n"
                f"  Reason: target file already exists. "
                f"Use --force to overwrite empty (un-annotated) templates only."
            )
        else:
            has_ann, fields = _has_human_annotations(path)
            if has_ann:
                field_list = ", ".join(sorted(fields))
                reasons.append(
                    f"{name} contains human annotations: {path}\n"
                    f"  Reason: the following annotation fields have non-empty "
                    f"values: {field_list}. Overwrite refused to prevent data loss."
                )

    return reasons


def _read_csv(path: Path) -> list[dict]:
    """Read a CSV file, returning a list of dicts."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    """Write a CSV file with the given fields and rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _is_etl_related(job: dict) -> bool:
    """Determine if a job is ETL/data-engineering related."""
    category = str(job.get("normalized_category", "")).strip()
    if category == "data_engineering":
        return True
    # Also include jobs whose title or description mentions ETL/data keywords
    text = " ".join([
        str(job.get("job_title", "")),
        str(job.get("responsibility", "")),
        str(job.get("requirement", "")),
    ]).lower()
    etl_keywords = ["etl", "数据开发", "数据工程", "数据仓库", "数仓",
                    "数据治理", "数据质量", "元数据", "数据管道", "data pipeline",
                    "数据集成", "数据同步", "数据清洗"]
    return any(kw in text for kw in etl_keywords)


def _sample_etl_jobs(min_count: int = 100) -> list[dict]:
    """Sample at least `min_count` ETL-related jobs with a fixed seed."""
    all_jobs = _read_csv(UNIFIED_JOBS_PATH)
    etl_jobs = [job for job in all_jobs if _is_etl_related(job)]
    rng = random.Random(SEED)
    rng.shuffle(etl_jobs)
    sample_size = max(min_count, min(len(etl_jobs), 200))
    return etl_jobs[:sample_size]


def build_jd_parsing_template(sampled_jobs: list[dict]) -> Path:
    """Build the JD parsing annotation template CSV."""
    rows = []
    for job in sampled_jobs:
        rows.append({
            "job_record_id": job.get("record_id", ""),
            "job_title": job.get("job_title", ""),
            "company": job.get("company", ""),
            "category": job.get("normalized_category", ""),
            "responsibility": job.get("responsibility", ""),
            "requirement": job.get("requirement", ""),
            "machine_skills": job.get("normalized_skills", ""),
            "machine_education": job.get("education", ""),
            "machine_work_years": job.get("work_years", ""),
            "annotator_id": "",
            "annotation_date": "",
            "annotated_skills": "",
            "annotated_responsibilities": "",
            "annotated_education": "",
            "annotated_experience_years": "",
            "annotation_notes": "",
        })
    path = COMPETITION_DIR / "jd_parsing_annotation_template.csv"
    _write_csv(path, JD_ANNOTATION_FIELDS, rows)
    return path


def build_resume_extraction_template(count: int = 30) -> Path:
    """Build the resume extraction annotation template CSV.

    This produces placeholder rows.  Annotators are expected to source or
    create de-identified resumes and fill in the ground-truth columns.
    """
    rows = []
    for i in range(1, count + 1):
        rows.append({
            "resume_id": f"competition-resume-{i:04d}",
            "resume_text_placeholder": "",
            "annotator_id": "",
            "annotation_date": "",
            "annotated_skills": "",
            "annotated_education": "",
            "annotated_experience_years": "",
            "annotated_projects": "",
            "annotated_certifications": "",
            "annotation_notes": "",
        })
    path = COMPETITION_DIR / "resume_extraction_annotation_template.csv"
    _write_csv(path, RESUME_ANNOTATION_FIELDS, rows)
    return path


def build_matching_template(sampled_jobs: list[dict], pairs_per_job: int = 3) -> Path:
    """Build the person-job matching annotation template CSV.

    Creates pairs of jobs (from the sample) with resume placeholder slots.
    Annotators fill in the match label and rationale.
    """
    rng = random.Random(SEED)
    rows = []
    for idx, job in enumerate(sampled_jobs[:max(50, len(sampled_jobs))], start=1):
        for p in range(1, pairs_per_job + 1):
            resume_id = f"competition-resume-{rng.randint(1, 9999):04d}"
            rows.append({
                "pair_id": f"pair-{idx:04d}-{p}",
                "job_record_id": job.get("record_id", ""),
                "job_title": job.get("job_title", ""),
                "company": job.get("company", ""),
                "job_skills": job.get("normalized_skills", ""),
                "job_education": job.get("education", ""),
                "job_experience_years": job.get("work_years", ""),
                "resume_id": resume_id,
                "resume_summary_placeholder": "",
                "annotator_id": "",
                "annotation_date": "",
                "match_label": "",
                "match_rationale": "",
                "annotation_notes": "",
            })
    path = COMPETITION_DIR / "person_job_matching_annotation_template.csv"
    _write_csv(path, MATCHING_ANNOTATION_FIELDS, rows)
    return path


def build_manifest(paths: dict[str, Path]) -> Path:
    """Write a manifest summarising the generated annotation sets."""
    rows = []
    for dataset, path in paths.items():
        records = _read_csv(path)
        rows.append({
            "dataset": dataset,
            "file_name": path.name,
            "record_count": len(records),
            "annotation_status": "pending_annotation",
            "annotator_count": 0,
            "notes": (
                "Annotation columns are empty. "
                "Requires independent human annotation by at least two reviewers."
            ),
        })
    manifest_path = COMPETITION_DIR / "annotation_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({
            "generated_from": str(UNIFIED_JOBS_PATH.relative_to(ROOT)),
            "random_seed": SEED,
            "datasets": rows,
            "annotation_protocol": {
                "reviewers": 2,
                "arbitration": (
                    "Disagreements between annotators are resolved by a third "
                    "senior reviewer.  Inter-annotator agreement is measured "
                    "with Cohen's kappa; pairs below 0.6 are re-annotated."
                ),
                "skill_labels": (
                    "Annotators map free-text skill mentions to canonical skill "
                    "names defined in scripts/job_taxonomy.py SKILL_ALIASES. "
                    "Skills not covered by the taxonomy should be noted in "
                    "annotation_notes for taxonomy expansion."
                ),
            },
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def build_readme() -> Path:
    """Write a README explaining the competition benchmark directory."""
    content = """# Competition Benchmark Data

This directory contains **human annotation templates** for the three
competition evaluation tasks.  All annotation columns are currently **empty**
— status is `pending_annotation`.

## Files

| File | Purpose | Records |
|------|---------|---------|
| `jd_parsing_annotation_template.csv` | JD field extraction ground truth | 100+ sampled real ETL jobs |
| `resume_extraction_annotation_template.csv` | Resume field extraction ground truth | 30 placeholder entries |
| `person_job_matching_annotation_template.csv` | Person-job match labels | 150+ job–resume pairs |
| `annotation_manifest.json` | Manifest with status and protocol | — |

## Annotation Protocol

1. **Two independent annotators** review each record and fill in the
   `annotator_id`, `annotation_date`, and annotation value columns.
2. **Disagreements** are resolved by a third senior reviewer.  Inter-annotator
   agreement is measured with Cohen's kappa; pairs below 0.6 are re-annotated.
3. **Do NOT** use the `machine_*` columns as ground truth — they are rule-based
   references provided only for annotator convenience.

## Task Definitions

### 1. JD Parsing
Annotators read `responsibility` and `requirement` text and extract:
- **Skills**: canonical skill names (pipe-separated), following the taxonomy in
  `scripts/job_taxonomy.py`.
- **Responsibilities**: key responsibility phrases (pipe-separated).
- **Education**: minimum required degree (博士 / 硕士 / 本科 / 大专 / 不限).
- **Experience years**: minimum required years of experience (integer).

### 2. Resume Extraction
Annotators source or create de-identified resumes, then extract:
- **Skills**, **Education**, **Experience years**, **Projects**, **Certifications**.

### 3. Person-Job Matching
Annotators review job–resume pairs and assign:
- **match**: the resume meets all core requirements.
- **partial_match**: the resume meets some but not all core requirements.
- **no_match**: the resume does not meet the core requirements.
- **rationale**: a brief justification for the label.

## Status

**Current status: `pending_annotation`** — no human annotations have been
completed.  The evaluation script (`scripts/evaluate_competition_metrics.py`)
will report `pending_annotation` until all templates have been independently
annotated by at least two reviewers.
"""
    path = COMPETITION_DIR / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def main(force: bool = False) -> int:
    """Build competition annotation sets.

    Returns 0 on success, 1 when targets are rejected by the overwrite
    protection checks (no files are written in that case).
    """
    # ── Pre-check all annotation targets *before* writing anything ────────
    targets = {
        "JD parsing template": COMPETITION_DIR / "jd_parsing_annotation_template.csv",
        "Resume extraction template": COMPETITION_DIR / "resume_extraction_annotation_template.csv",
        "Person-job matching template": COMPETITION_DIR / "person_job_matching_annotation_template.csv",
    }

    reasons = _check_targets(targets, force)
    if reasons:
        for reason in reasons:
            print(f"ERROR: {reason}", file=sys.stderr)
        print(
            "\nNo files were written. Annotation templates unchanged.",
            file=sys.stderr,
        )
        return 1

    COMPETITION_DIR.mkdir(parents=True, exist_ok=True)

    print("Sampling ETL jobs from unified_jobs.csv ...")
    sampled = _sample_etl_jobs(min_count=100)
    print(f"  Sampled {len(sampled)} ETL-related jobs (seed={SEED})")

    print("Building JD parsing annotation template ...")
    jd_path = build_jd_parsing_template(sampled)
    jd_count = len(_read_csv(jd_path))
    print(f"  {jd_path.name}: {jd_count} records")

    print("Building resume extraction annotation template ...")
    resume_path = build_resume_extraction_template(count=30)
    resume_count = len(_read_csv(resume_path))
    print(f"  {resume_path.name}: {resume_count} records")

    print("Building person-job matching annotation template ...")
    matching_path = build_matching_template(sampled, pairs_per_job=3)
    matching_count = len(_read_csv(matching_path))
    print(f"  {matching_path.name}: {matching_count} records")

    print("Building manifest ...")
    manifest_path = build_manifest({
        "jd_parsing": jd_path,
        "resume_extraction": resume_path,
        "person_job_matching": matching_path,
    })
    print(f"  {manifest_path.name} written")

    print("Building README ...")
    readme_path = build_readme()
    print(f"  {readme_path.name} written")

    print("\nDone. All annotation templates are in:", str(COMPETITION_DIR))
    print("Status: pending_annotation — waiting for human annotators.")
    return 0


if __name__ == "__main__":
    force = "--force" in sys.argv
    unknown = [a for a in sys.argv[1:] if a != "--force"]
    if unknown:
        print(f"Unknown arguments: {unknown}", file=sys.stderr)
        print(
            "Usage: python scripts/build_competition_annotation_set.py [--force]",
            file=sys.stderr,
        )
        sys.exit(2)
    sys.exit(main(force=force))
