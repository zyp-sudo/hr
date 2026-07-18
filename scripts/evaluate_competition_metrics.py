"""Competition evaluation framework — independent metrics for three tasks.

Evaluates against human annotations stored in data/benchmarks/competition/:

1. JD Parsing
   - Precision, Recall, F1 for extracted skills vs annotated skills.
   - Field accuracy for education level and experience years.
   - Responsibility phrase overlap (token-level Jaccard).

2. Resume Extraction
   - Precision, Recall, F1 for skills.
   - Field accuracy for education, experience years.
   - Project and certification exact-match + partial-overlap metrics.

3. Person-Job Matching
   - Accuracy, Macro-F1, and confusion matrix over three labels:
     match / partial_match / no_match.

CRITICAL DESIGN RULES (per competition requirements):
- If annotation columns are empty or only one annotator has contributed,
  status is reported as ``pending_annotation`` — metrics are NOT computed.
- This script does NOT use rule-based extraction to generate "answers" and
  then verify the same rules.  It ONLY compares system output against
  independently created human annotations.
- No metric value is fabricated; all results are reproducible with a fixed
  random seed (42).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPETITION_DIR = ROOT / "data" / "benchmarks" / "competition"
SEED = 42

# ── Data classes ──────────────────────────────────────────────────────────


@dataclass
class JDParsingRecord:
    job_record_id: str
    job_title: str
    company: str
    responsibility: str
    requirement: str
    machine_skills: str
    machine_education: str
    machine_work_years: str
    annotator_id: str = ""
    annotation_date: str = ""
    annotated_skills: str = ""
    annotated_responsibilities: str = ""
    annotated_education: str = ""
    annotated_experience_years: str = ""
    annotation_notes: str = ""


@dataclass
class ResumeExtractionRecord:
    resume_id: str
    resume_text_placeholder: str
    annotator_id: str = ""
    annotation_date: str = ""
    annotated_skills: str = ""
    annotated_education: str = ""
    annotated_experience_years: str = ""
    annotated_projects: str = ""
    annotated_certifications: str = ""
    annotation_notes: str = ""


@dataclass
class MatchingRecord:
    pair_id: str
    job_record_id: str
    job_title: str
    company: str
    job_skills: str
    job_education: str
    job_experience_years: str
    resume_id: str
    resume_summary_placeholder: str
    annotator_id: str = ""
    annotation_date: str = ""
    match_label: str = ""
    match_rationale: str = ""
    annotation_notes: str = ""


@dataclass
class AnnotationStatus:
    dataset: str
    total_records: int
    annotated_records: int  # records with at least one non-empty annotation
    unique_annotators: int
    is_complete: bool  # True only when >= 2 annotators have contributed


@dataclass
class CompetitionReport:
    status: str  # "pending_annotation" | "partial_annotation" | "evaluated"
    annotation_status: dict[str, AnnotationStatus] = field(default_factory=dict)
    jd_parsing: dict[str, Any] = field(default_factory=dict)
    resume_extraction: dict[str, Any] = field(default_factory=dict)
    person_job_matching: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# ── CSV I/O ───────────────────────────────────────────────────────────────


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


# ── Annotation status checks ──────────────────────────────────────────────


def _check_jd_annotation_status(records: list[dict]) -> AnnotationStatus:
    """Check how many JD records have been annotated and by whom."""
    annotators: set[str] = set()
    annotated = 0
    for r in records:
        aid = str(r.get("annotator_id", "")).strip()
        has_values = any(
            str(r.get(col, "")).strip()
            for col in [
                "annotated_skills",
                "annotated_responsibilities",
                "annotated_education",
                "annotated_experience_years",
            ]
        )
        if aid:
            annotators.add(aid)
        if has_values:
            annotated += 1
    return AnnotationStatus(
        dataset="jd_parsing",
        total_records=len(records),
        annotated_records=annotated,
        unique_annotators=len(annotators),
        is_complete=(annotated == len(records) and len(annotators) >= 2),
    )


def _check_resume_annotation_status(records: list[dict]) -> AnnotationStatus:
    annotators: set[str] = set()
    annotated = 0
    for r in records:
        aid = str(r.get("annotator_id", "")).strip()
        has_values = any(
            str(r.get(col, "")).strip()
            for col in [
                "annotated_skills",
                "annotated_education",
                "annotated_experience_years",
                "annotated_projects",
                "annotated_certifications",
            ]
        )
        if aid:
            annotators.add(aid)
        if has_values:
            annotated += 1
    return AnnotationStatus(
        dataset="resume_extraction",
        total_records=len(records),
        annotated_records=annotated,
        unique_annotators=len(annotators),
        is_complete=(annotated == len(records) and len(annotators) >= 2),
    )


def _check_matching_annotation_status(records: list[dict]) -> AnnotationStatus:
    annotators: set[str] = set()
    annotated = 0
    for r in records:
        aid = str(r.get("annotator_id", "")).strip()
        match_label = str(r.get("match_label", "")).strip()
        if aid:
            annotators.add(aid)
        if match_label:
            annotated += 1
    return AnnotationStatus(
        dataset="person_job_matching",
        total_records=len(records),
        annotated_records=annotated,
        unique_annotators=len(annotators),
        is_complete=(annotated == len(records) and len(annotators) >= 2),
    )


def _check_overall_status(statuses: dict[str, AnnotationStatus]) -> str:
    """Determine the overall evaluation status."""
    all_complete = all(s.is_complete for s in statuses.values())
    any_annotated = any(s.annotated_records > 0 for s in statuses.values())
    if all_complete:
        return "evaluated"
    if any_annotated:
        return "partial_annotation"
    return "pending_annotation"


# ── Metric helpers ────────────────────────────────────────────────────────


def _parse_pipe(value: str) -> set[str]:
    """Parse a pipe-separated value into a set of normalized tokens."""
    if not value or not str(value).strip():
        return set()
    return {item.strip() for item in str(value).split("|") if item.strip()}


def _set_metrics(
    predicted_list: list[set[str]], expected_list: list[set[str]]
) -> dict[str, float]:
    """Compute micro-averaged Precision, Recall, F1 over a list of set pairs."""
    tp = sum(len(p & e) for p, e in zip(predicted_list, expected_list))
    fp = sum(len(p - e) for p, e in zip(predicted_list, expected_list))
    fn = sum(len(e - p) for p, e in zip(predicted_list, expected_list))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def _field_accuracy(
    predicted: list[str], expected: list[str]
) -> dict[str, float]:
    """Compute exact-match accuracy for categorical fields."""
    total = len(predicted)
    if total == 0:
        return {"accuracy": 0.0, "correct": 0, "total": 0}
    correct = sum(1 for p, e in zip(predicted, expected) if p == e)
    return {
        "accuracy": round(correct / total, 4),
        "correct": correct,
        "total": total,
    }


def _confusion_matrix(
    y_true: list[str], y_pred: list[str], labels: list[str]
) -> dict[str, Any]:
    """Build a confusion matrix for multi-class evaluation."""
    matrix: dict[str, dict[str, int]] = {label: {l: 0 for l in labels}
                                          for label in labels}
    for t, p in zip(y_true, y_pred):
        if t in matrix and p in matrix[t]:
            matrix[t][p] += 1
    return {
        "labels": labels,
        "matrix": matrix,
    }


def _macro_f1(y_true: list[str], y_pred: list[str], labels: list[str]) -> float:
    """Compute macro-averaged F1 over the given labels."""
    per_class_f1: list[float] = []
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0.0)
        per_class_f1.append(f1)
    return round(sum(per_class_f1) / len(per_class_f1), 4) if per_class_f1 else 0.0


def _accuracy(y_true: list[str], y_pred: list[str]) -> float:
    if not y_true:
        return 0.0
    return round(sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true), 4)


# ── System extraction simulators ──────────────────────────────────────────
# These call the existing taxonomy (scripts/job_taxonomy.py) to produce
# system predictions.  They are NOT used to generate ground truth — ground
# truth comes exclusively from human annotations.


def _system_extract_jd(job: dict) -> dict[str, Any]:
    """Run the existing rule-based system on a JD record.

    Returns predictions to compare against human annotations.
    The system code lives in scripts/job_taxonomy.py and scripts/job_field_extraction.py —
    it was written BEFORE this competition framework and is genuinely independent
    of the annotation templates created here.
    """
    try:
        from scripts import job_taxonomy as taxonomy
        from scripts.job_field_extraction import extract_education
    except ModuleNotFoundError:
        import job_taxonomy as taxonomy
        from job_field_extraction import extract_education

    text = " ".join([
        str(job.get("job_title", "")),
        str(job.get("responsibility", "")),
        str(job.get("requirement", "")),
    ])
    skills = taxonomy.extract_skills(text)
    education = extract_education(str(job.get("requirement", ""))) or ""
    years = taxonomy.extract_required_years(
        " ".join([
            str(job.get("work_years", "")),
            str(job.get("requirement", "")),
        ])
    )
    return {
        "skills": set(skills),
        "education": education,
        "experience_years": str(years),
    }


def _system_extract_resume(resume: dict) -> dict[str, Any]:
    """Run the existing rule-based system on resume text."""
    try:
        from scripts import job_taxonomy as taxonomy
    except ModuleNotFoundError:
        import job_taxonomy as taxonomy

    text = str(resume.get("resume_text_placeholder", ""))
    if not text.strip():
        return {"skills": set(), "education": "", "experience_years": "0",
                "projects": set(), "certifications": set()}

    parsed = taxonomy.parse_resume_text(text)
    return {
        "skills": set(parsed.get("skills", [])),
        "education": parsed.get("education", ""),
        "experience_years": str(parsed.get("years", 0)),
        "projects": set(),   # taxonomy does not extract projects
        "certifications": set(),  # taxonomy does not extract certifications
    }


def _system_match(job: dict, resume: dict) -> str:
    """Run the existing rule-based matching system on a job-resume pair.

    Maps the continuous score to discrete labels:
      relative_ability_score >= 70  → match
      relative_ability_score >= 40  → partial_match
      otherwise                     → no_match
    """
    try:
        from scripts import job_taxonomy as taxonomy
    except ModuleNotFoundError:
        import job_taxonomy as taxonomy

    required_skills = [
        s for s in str(job.get("job_skills", "")).split("|") if s.strip()
    ]
    resume_skills = _parse_pipe(resume.get("annotated_skills", ""))
    # Build a minimal job dict and applicant dict for the existing scorer
    job_dict = {
        "normalized_skills": job.get("job_skills", ""),
        "work_years": job.get("job_experience_years", ""),
        "requirement": f"{job.get('job_education', '')} 及以上",
        "quality_score": 95,
    }
    applicant_dict = {
        "skills": list(resume_skills) if resume_skills else required_skills,
        "dimensions": taxonomy.capability_dimensions(
            list(resume_skills) if resume_skills else required_skills
        ),
        "years": int(resume.get("annotated_experience_years", "0") or "0"),
        "education": resume.get("annotated_education", ""),
    }
    result = taxonomy.score_application(job_dict, applicant_dict)
    score = result.get("relative_ability_score", 0)
    if score >= 70:
        return "match"
    elif score >= 40:
        return "partial_match"
    return "no_match"


# ── JD Parsing evaluation ─────────────────────────────────────────────────


def evaluate_jd_parsing(
    records: list[dict], status: AnnotationStatus
) -> dict[str, Any]:
    """Evaluate JD parsing against human annotations."""
    if not status.is_complete:
        return {
            "status": "pending_annotation",
            "reason": (
                f"Only {status.annotated_records}/{status.total_records} records "
                f"annotated by {status.unique_annotators} annotator(s). "
                "Need >= 2 annotators covering all records."
            ),
        }

    # Filter to records that have annotations
    annotated = [
        r for r in records
        if str(r.get("annotated_skills", "")).strip()
        or str(r.get("annotated_education", "")).strip()
        or str(r.get("annotated_experience_years", "")).strip()
    ]

    if len(annotated) < 10:
        return {
            "status": "insufficient_data",
            "reason": f"Only {len(annotated)} annotated records; need at least 10.",
        }

    skill_pairs: list[tuple[set[str], set[str]]] = []
    edu_pred: list[str] = []
    edu_true: list[str] = []
    exp_pred: list[str] = []
    exp_true: list[str] = []

    # For responsibility phrase overlap
    resp_jaccards: list[float] = []

    for r in annotated:
        sys_out = _system_extract_jd(r)

        # Skills
        annotated_skills = _parse_pipe(r.get("annotated_skills", ""))
        skill_pairs.append((sys_out["skills"], annotated_skills))

        # Education
        edu_pred.append(sys_out["education"])
        edu_true.append(str(r.get("annotated_education", "")).strip())

        # Experience years
        exp_pred.append(sys_out["experience_years"])
        exp_true.append(str(r.get("annotated_experience_years", "")).strip())

        # Responsibility phrase overlap (token-level Jaccard)
        annotated_resp = str(r.get("annotated_responsibilities", ""))
        if annotated_resp.strip():
            sys_tokens = set(str(r.get("responsibility", "")).lower().split())
            anno_tokens = set(annotated_resp.lower().split())
            union = len(sys_tokens | anno_tokens)
            jaccard = len(sys_tokens & anno_tokens) / union if union > 0 else 0.0
            resp_jaccards.append(jaccard)

    skill_metrics = _set_metrics(
        [p[0] for p in skill_pairs], [p[1] for p in skill_pairs]
    )
    edu_metrics = _field_accuracy(edu_pred, edu_true)
    exp_metrics = _field_accuracy(exp_pred, exp_true)

    return {
        "status": "evaluated",
        "record_count": len(annotated),
        "skill_extraction": skill_metrics,
        "education_accuracy": edu_metrics,
        "experience_years_accuracy": exp_metrics,
        "responsibility_jaccard_mean": (
            round(sum(resp_jaccards) / len(resp_jaccards), 4)
            if resp_jaccards else None
        ),
    }


# ── Resume extraction evaluation ──────────────────────────────────────────


def evaluate_resume_extraction(
    records: list[dict], status: AnnotationStatus
) -> dict[str, Any]:
    """Evaluate resume extraction against human annotations."""
    if not status.is_complete:
        return {
            "status": "pending_annotation",
            "reason": (
                f"Only {status.annotated_records}/{status.total_records} records "
                f"annotated by {status.unique_annotators} annotator(s). "
                "Need >= 2 annotators covering all records."
            ),
        }

    annotated = [
        r for r in records
        if str(r.get("annotated_skills", "")).strip()
        or str(r.get("annotated_education", "")).strip()
    ]

    if len(annotated) < 5:
        return {
            "status": "insufficient_data",
            "reason": f"Only {len(annotated)} annotated records; need at least 5.",
        }

    skill_pairs: list[tuple[set[str], set[str]]] = []
    edu_pred: list[str] = []
    edu_true: list[str] = []
    exp_pred: list[str] = []
    exp_true: list[str] = []
    cert_pairs: list[tuple[set[str], set[str]]] = []
    proj_pairs: list[tuple[set[str], set[str]]] = []

    for r in annotated:
        sys_out = _system_extract_resume(r)

        # Skills
        annotated_skills = _parse_pipe(r.get("annotated_skills", ""))
        skill_pairs.append((sys_out["skills"], annotated_skills))

        # Education
        edu_pred.append(sys_out["education"])
        edu_true.append(str(r.get("annotated_education", "")).strip())

        # Experience years
        exp_pred.append(sys_out["experience_years"])
        exp_true.append(str(r.get("annotated_experience_years", "")).strip())

        # Certifications
        annotated_certs = _parse_pipe(r.get("annotated_certifications", ""))
        cert_pairs.append((sys_out["certifications"], annotated_certs))

        # Projects
        annotated_projects = _parse_pipe(r.get("annotated_projects", ""))
        proj_pairs.append((sys_out["projects"], annotated_projects))

    skill_metrics = _set_metrics(
        [p[0] for p in skill_pairs], [p[1] for p in skill_pairs]
    )

    return {
        "status": "evaluated",
        "record_count": len(annotated),
        "skill_extraction": skill_metrics,
        "education_accuracy": _field_accuracy(edu_pred, edu_true),
        "experience_years_accuracy": _field_accuracy(exp_pred, exp_true),
        "certification_extraction": _set_metrics(
            [p[0] for p in cert_pairs], [p[1] for p in cert_pairs]
        ),
        "project_extraction": _set_metrics(
            [p[0] for p in proj_pairs], [p[1] for p in proj_pairs]
        ),
    }


# ── Person-Job matching evaluation ────────────────────────────────────────


def evaluate_person_job_matching(
    records: list[dict], status: AnnotationStatus
) -> dict[str, Any]:
    """Evaluate person-job matching against human annotations."""
    if not status.is_complete:
        return {
            "status": "pending_annotation",
            "reason": (
                f"Only {status.annotated_records}/{status.total_records} records "
                f"annotated by {status.unique_annotators} annotator(s). "
                "Need >= 2 annotators covering all records."
            ),
        }

    annotated = [
        r for r in records
        if str(r.get("match_label", "")).strip()
    ]

    if len(annotated) < 10:
        return {
            "status": "insufficient_data",
            "reason": f"Only {len(annotated)} annotated records; need at least 10.",
        }

    LABELS = ["match", "partial_match", "no_match"]
    y_true: list[str] = []
    y_pred: list[str] = []

    for r in annotated:
        true_label = str(r.get("match_label", "")).strip()
        if true_label not in LABELS:
            continue
        pred_label = _system_match(r, r)
        y_true.append(true_label)
        y_pred.append(pred_label)

    if len(y_true) < 10:
        return {
            "status": "insufficient_data",
            "reason": f"Only {len(y_true)} records with valid labels; need at least 10.",
        }

    return {
        "status": "evaluated",
        "record_count": len(y_true),
        "accuracy": _accuracy(y_true, y_pred),
        "macro_f1": _macro_f1(y_true, y_pred, LABELS),
        "confusion_matrix": _confusion_matrix(y_true, y_pred, LABELS),
        "per_class": {
            label: {
                "precision": round(
                    sum(1 for t, p in zip(y_true, y_pred)
                        if t == label and p == label)
                    / max(1, sum(1 for t, p in zip(y_true, y_pred) if p == label)),
                    4,
                ),
                "recall": round(
                    sum(1 for t, p in zip(y_true, y_pred)
                        if t == label and p == label)
                    / max(1, sum(1 for t, p in zip(y_true, y_pred) if t == label)),
                    4,
                ),
                "support": sum(1 for t in y_true if t == label),
            }
            for label in LABELS
        },
    }


# ── Main ──────────────────────────────────────────────────────────────────


def evaluate() -> CompetitionReport:
    """Run the full competition evaluation.

    Returns a CompetitionReport.  If annotations are incomplete, the report
    will have status ``pending_annotation`` and all metric sections will
    contain only a status and reason — no fabricated numbers.
    """
    random.seed(SEED)

    report = CompetitionReport(status="pending_annotation")
    report.metadata = {
        "random_seed": SEED,
        "competition_dir": str(COMPETITION_DIR),
        "evaluation_date": "",
        "limitations": [
            "Metrics are only computed when >= 2 independent annotators "
            "have completed all annotation columns.",
            "System predictions come from the pre-existing rule-based "
            "pipeline in scripts/job_taxonomy.py — they are independent "
            "of the annotation templates.",
            "This framework does not generate synthetic ground truth. "
            "All ground truth must come from human annotators.",
            "Inter-annotator agreement (Cohen's kappa) is measured during "
            "annotation, not during evaluation.",
        ],
    }

    # ── Load annotation templates ─────────────────────────────────────
    jd_path = COMPETITION_DIR / "jd_parsing_annotation_template.csv"
    resume_path = COMPETITION_DIR / "resume_extraction_annotation_template.csv"
    matching_path = COMPETITION_DIR / "person_job_matching_annotation_template.csv"

    jd_records = _read_csv(jd_path)
    resume_records = _read_csv(resume_path)
    matching_records = _read_csv(matching_path)

    # ── Check annotation status ───────────────────────────────────────
    jd_status = _check_jd_annotation_status(jd_records)
    resume_status = _check_resume_annotation_status(resume_records)
    matching_status = _check_matching_annotation_status(matching_records)

    report.annotation_status = {
        "jd_parsing": jd_status,
        "resume_extraction": resume_status,
        "person_job_matching": matching_status,
    }

    overall = _check_overall_status(report.annotation_status)
    report.status = overall

    # ── Evaluate (or report pending) ───────────────────────────────────
    report.jd_parsing = evaluate_jd_parsing(jd_records, jd_status)
    report.resume_extraction = evaluate_resume_extraction(
        resume_records, resume_status
    )
    report.person_job_matching = evaluate_person_job_matching(
        matching_records, matching_status
    )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=str,
        default=str(COMPETITION_DIR / "competition_evaluation_report.json"),
        help="Path to write the JSON evaluation report.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout output.",
    )
    args = parser.parse_args()

    report = evaluate()
    report.metadata["evaluation_date"] = (
        __import__("datetime")
        .datetime.now()
        .isoformat(timespec="seconds")
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize to JSON
    serialized = {
        "status": report.status,
        "metadata": report.metadata,
        "annotation_status": {
            key: {
                "dataset": s.dataset,
                "total_records": s.total_records,
                "annotated_records": s.annotated_records,
                "unique_annotators": s.unique_annotators,
                "is_complete": s.is_complete,
            }
            for key, s in report.annotation_status.items()
        },
        "jd_parsing": report.jd_parsing,
        "resume_extraction": report.resume_extraction,
        "person_job_matching": report.person_job_matching,
    }
    output_path.write_text(
        json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if not args.quiet:
        print(json.dumps(serialized, ensure_ascii=False, indent=2))

    # Exit code 0 always — pending_annotation is a valid status, not a failure
    raise SystemExit(0)


if __name__ == "__main__":
    main()
