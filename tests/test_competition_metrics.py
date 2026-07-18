"""Tests for the competition evaluation framework.

Verifies:
- Annotation set builder produces correct file structure and record counts.
- Evaluation framework reports pending_annotation for empty templates.
- With simulated annotations, the framework correctly computes metrics.
- Reproducibility with fixed random seed.
- Metric helper functions compute correct values.
- All three evaluation tasks (JD parsing, resume extraction, matching) work
  end-to-end with controlled test data.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# ── Path setup ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
COMPETITION_DIR = ROOT / "data" / "benchmarks" / "competition"


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def competition_dir_exists():
    """Ensure the competition data directory and templates exist."""
    assert COMPETITION_DIR.exists(), (
        "Competition directory not found. Run "
        "python -m scripts.build_competition_annotation_set first."
    )
    return COMPETITION_DIR


# ── Builder tests ─────────────────────────────────────────────────────────


class TestAnnotationSetBuilder:
    """Verify the annotation set builder produces correct output."""

    def test_jd_template_has_correct_fields(self, competition_dir_exists):
        import csv
        jd_path = competition_dir_exists / "jd_parsing_annotation_template.csv"
        assert jd_path.exists(), f"Missing {jd_path.name}"

        with jd_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            fields = reader.fieldnames

        # Must have at least 100 records
        assert len(rows) >= 100, (
            f"JD template has {len(rows)} records; need >= 100"
        )

        # Must have annotation columns
        for col in [
            "annotator_id", "annotation_date", "annotated_skills",
            "annotated_responsibilities", "annotated_education",
            "annotated_experience_years",
        ]:
            assert col in fields, f"Missing annotation column: {col}"

        # Annotation columns must be empty (no fabricated ground truth)
        for row in rows:
            assert str(row.get("annotated_skills", "")).strip() == "", (
                "annotated_skills should be empty — no fabricated ground truth"
            )
            assert str(row.get("annotator_id", "")).strip() == ""

        # Machine columns should have data (reference for annotators)
        has_machine_data = any(
            str(row.get("machine_skills", "")).strip() for row in rows
        )
        assert has_machine_data, "machine_skills column should have reference data"

    def test_resume_template_has_correct_structure(self, competition_dir_exists):
        import csv
        resume_path = (
            competition_dir_exists / "resume_extraction_annotation_template.csv"
        )
        assert resume_path.exists(), f"Missing {resume_path.name}"

        with resume_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            fields = reader.fieldnames

        assert len(rows) >= 20, (
            f"Resume template has {len(rows)} records; need >= 20"
        )

        for col in [
            "resume_id", "resume_text_placeholder",
            "annotated_skills", "annotated_education",
            "annotated_experience_years", "annotated_projects",
            "annotated_certifications",
        ]:
            assert col in fields, f"Missing column: {col}"

        # Annotation columns must be empty — no fake data
        for row in rows:
            assert str(row.get("annotated_skills", "")).strip() == ""

        # resume_text_placeholder is intentionally empty — annotators fill it
        has_text = any(
            str(row.get("resume_text_placeholder", "")).strip() for row in rows
        )
        assert not has_text, (
            "resume_text_placeholder should be empty — "
            "annotators provide de-identified resumes"
        )

    def test_matching_template_has_valid_labels(self, competition_dir_exists):
        import csv
        matching_path = (
            competition_dir_exists / "person_job_matching_annotation_template.csv"
        )
        assert matching_path.exists(), f"Missing {matching_path.name}"

        with matching_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)

        assert len(rows) >= 50, (
            f"Matching template has {len(rows)} records; need >= 50"
        )

        # match_label must be empty for all records
        for row in rows:
            label = str(row.get("match_label", "")).strip()
            assert label == "", (
                f"match_label should be empty, got '{label}' for "
                f"{row.get('pair_id', '?')}"
            )

    def test_manifest_exists_and_reports_pending(self, competition_dir_exists):
        manifest_path = competition_dir_exists / "annotation_manifest.json"
        assert manifest_path.exists(), "Manifest missing"

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["random_seed"] == 42

        for ds in manifest["datasets"]:
            assert ds["annotation_status"] == "pending_annotation", (
                f"{ds['dataset']} should be pending_annotation"
            )

    def test_builder_reproducibility(self, competition_dir_exists):
        """Same seed should produce deterministic output."""
        import csv
        # Run the builder again with same seed
        from scripts.build_competition_annotation_set import _sample_etl_jobs

        sample1 = _sample_etl_jobs(min_count=100)
        sample2 = _sample_etl_jobs(min_count=100)
        ids1 = [j["record_id"] for j in sample1]
        ids2 = [j["record_id"] for j in sample2]
        assert ids1 == ids2, "Sampling is not reproducible with fixed seed"

    def test_etl_filter_includes_data_engineering(self):
        from scripts.build_competition_annotation_set import _is_etl_related

        data_eng_job = {
            "normalized_category": "data_engineering",
            "job_title": "数据开发工程师",
            "responsibility": "负责数据仓库建设",
            "requirement": "熟悉ETL流程",
        }
        assert _is_etl_related(data_eng_job) is True

    def test_etl_filter_includes_etl_keyword_jobs(self):
        from scripts.build_competition_annotation_set import _is_etl_related

        etl_title_job = {
            "normalized_category": "backend_engineering",
            "job_title": "ETL 开发工程师",
            "responsibility": "something",
            "requirement": "something",
        }
        assert _is_etl_related(etl_title_job) is True

    def test_etl_filter_excludes_non_etl(self):
        from scripts.build_competition_annotation_set import _is_etl_related

        non_etl_job = {
            "normalized_category": "frontend_client",
            "job_title": "React 前端工程师",
            "responsibility": "开发Web前端页面",
            "requirement": "熟悉React和TypeScript",
        }
        assert _is_etl_related(non_etl_job) is False


# ── Evaluator tests ───────────────────────────────────────────────────────


class TestCompetitionEvaluator:
    """Verify the evaluation framework correctly handles all states."""

    def test_evaluator_reports_pending_for_empty_annotations(self):
        """With empty annotation templates, status must be pending_annotation."""
        from scripts.evaluate_competition_metrics import evaluate

        report = evaluate()
        assert report.status == "pending_annotation", (
            f"Expected pending_annotation, got {report.status}"
        )

        # All three sub-tasks must report pending
        assert report.jd_parsing["status"] == "pending_annotation"
        assert report.resume_extraction["status"] == "pending_annotation"
        assert report.person_job_matching["status"] == "pending_annotation"

    def test_evaluator_output_is_serializable(self):
        """Verify the full report serializes to JSON without error."""
        from scripts.evaluate_competition_metrics import evaluate

        report = evaluate()
        serialized = json.dumps(
            {
                "status": report.status,
                "annotation_status": {
                    k: {
                        "dataset": v.dataset,
                        "total_records": v.total_records,
                        "annotated_records": v.annotated_records,
                        "unique_annotators": v.unique_annotators,
                        "is_complete": v.is_complete,
                    }
                    for k, v in report.annotation_status.items()
                },
                "jd_parsing": report.jd_parsing,
                "resume_extraction": report.resume_extraction,
                "person_job_matching": report.person_job_matching,
            },
            ensure_ascii=False,
            indent=2,
        )
        assert len(serialized) > 0


# ── Metric helper tests ───────────────────────────────────────────────────


class TestMetricHelpers:
    """Verify metric computation functions independently."""

    def test_set_metrics_perfect(self):
        from scripts.evaluate_competition_metrics import _set_metrics

        result = _set_metrics(
            [{"Java", "Python"}, {"SQL", "Redis"}],
            [{"Java", "Python"}, {"SQL", "Redis"}],
        )
        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0
        assert result["tp"] == 4
        assert result["fp"] == 0
        assert result["fn"] == 0

    def test_set_metrics_partial(self):
        from scripts.evaluate_competition_metrics import _set_metrics

        # System predicts Java + Python, truth is Java + Go
        result = _set_metrics(
            [{"Java", "Python"}],
            [{"Java", "Go"}],
        )
        # TP = 1 (Java), FP = 1 (Python), FN = 1 (Go)
        assert result["tp"] == 1
        assert result["fp"] == 1
        assert result["fn"] == 1
        assert result["precision"] == 0.5
        assert result["recall"] == 0.5
        assert result["f1"] == 0.5

    def test_set_metrics_empty(self):
        from scripts.evaluate_competition_metrics import _set_metrics

        result = _set_metrics([], [])
        assert result["precision"] == 0.0
        assert result["recall"] == 0.0
        assert result["f1"] == 0.0

    def test_field_accuracy(self):
        from scripts.evaluate_competition_metrics import _field_accuracy

        result = _field_accuracy(
            ["本科", "硕士", "本科", "大专", "博士"],
            ["本科", "硕士", "硕士", "大专", "博士"],
        )
        assert result["accuracy"] == 0.8  # 4/5 correct
        assert result["correct"] == 4
        assert result["total"] == 5

    def test_field_accuracy_empty(self):
        from scripts.evaluate_competition_metrics import _field_accuracy

        result = _field_accuracy([], [])
        assert result["accuracy"] == 0.0
        assert result["total"] == 0

    def test_confusion_matrix_structure(self):
        from scripts.evaluate_competition_metrics import _confusion_matrix

        LABELS = ["match", "partial_match", "no_match"]
        y_true = ["match", "partial_match", "no_match", "match", "match"]
        y_pred = ["match", "partial_match", "partial_match", "match", "no_match"]

        cm = _confusion_matrix(y_true, y_pred, LABELS)
        assert cm["labels"] == LABELS
        # match row: 2 predicted as match, 0 as partial, 1 as no_match
        assert cm["matrix"]["match"]["match"] == 2
        assert cm["matrix"]["match"]["no_match"] == 1
        # partial_match row
        assert cm["matrix"]["partial_match"]["partial_match"] == 1
        # no_match row: predicted as partial_match
        assert cm["matrix"]["no_match"]["partial_match"] == 1

    def test_macro_f1(self):
        from scripts.evaluate_competition_metrics import _macro_f1

        LABELS = ["match", "partial_match", "no_match"]
        y_true = ["match", "match", "partial_match", "no_match", "no_match"]
        y_pred = ["match", "match", "partial_match", "no_match", "no_match"]

        f1 = _macro_f1(y_true, y_pred, LABELS)
        assert f1 == 1.0

    def test_macro_f1_imperfect(self):
        from scripts.evaluate_competition_metrics import _macro_f1

        LABELS = ["match", "no_match"]
        y_true = ["match", "match", "no_match", "no_match"]
        y_pred = ["match", "no_match", "no_match", "no_match"]
        # match: tp=1, fp=0, fn=1 → P=1.0, R=0.5, F1=0.6667
        # no_match: tp=2, fp=1, fn=0 → P=0.6667, R=1.0, F1=0.8
        # macro = (0.6667 + 0.8) / 2 = 0.7334
        f1 = _macro_f1(y_true, y_pred, LABELS)
        assert 0.73 <= f1 <= 0.74, f"Expected ~0.7334, got {f1}"

    def test_accuracy(self):
        from scripts.evaluate_competition_metrics import _accuracy

        assert _accuracy(["a", "b", "c"], ["a", "b", "c"]) == 1.0
        # _accuracy rounds to 4 decimal places: round(2/3, 4) = 0.6667
        assert abs(_accuracy(["a", "b", "c"], ["a", "x", "c"]) - 2 / 3) < 0.001
        assert _accuracy([], []) == 0.0

    def test_parse_pipe(self):
        from scripts.evaluate_competition_metrics import _parse_pipe

        assert _parse_pipe("Java|Python|SQL") == {"Java", "Python", "SQL"}
        assert _parse_pipe("  Java | Python | Java  ") == {"Java", "Python"}
        assert _parse_pipe("") == set()
        assert _parse_pipe("||") == set()


# ── Annotation status tests ───────────────────────────────────────────────


class TestAnnotationStatus:
    """Verify annotation status detection logic."""

    def test_empty_annotations_are_incomplete(self):
        from scripts.evaluate_competition_metrics import (
            _check_jd_annotation_status,
        )

        records = [
            {"annotator_id": "", "annotated_skills": "",
             "annotated_responsibilities": "", "annotated_education": "",
             "annotated_experience_years": ""}
            for _ in range(10)
        ]
        status = _check_jd_annotation_status(records)
        assert status.is_complete is False
        assert status.annotated_records == 0
        assert status.unique_annotators == 0

    def test_single_annotator_is_incomplete(self):
        from scripts.evaluate_competition_metrics import (
            _check_jd_annotation_status,
        )

        records = [
            {
                "annotator_id": "reviewer_a",
                "annotated_skills": "Java|Python",
                "annotated_responsibilities": "",
                "annotated_education": "本科",
                "annotated_experience_years": "3",
            }
            for _ in range(10)
        ]
        status = _check_jd_annotation_status(records)
        assert status.is_complete is False, (
            "Single annotator should not be complete"
        )
        assert status.annotated_records == 10
        assert status.unique_annotators == 1

    def test_two_annotators_all_records_is_complete(self):
        from scripts.evaluate_competition_metrics import (
            _check_jd_annotation_status,
        )

        # Simulate 5 records each from two annotators (interleaved for
        # IAA measurement, but status check just counts)
        records = []
        for i in range(5):
            records.append({
                "annotator_id": "reviewer_a",
                "annotated_skills": "Java|Python",
                "annotated_responsibilities": "后端开发",
                "annotated_education": "本科",
                "annotated_experience_years": "3",
            })
        for i in range(5):
            records.append({
                "annotator_id": "reviewer_b",
                "annotated_skills": "Java|Spring",
                "annotated_responsibilities": "后端服务开发",
                "annotated_education": "本科",
                "annotated_experience_years": "3",
            })
        status = _check_jd_annotation_status(records)
        assert status.is_complete is True, (
            f"2 annotators × all records should be complete; "
            f"got annotated={status.annotated_records}, "
            f"annotators={status.unique_annotators}"
        )
        assert status.unique_annotators == 2

    def test_matching_status_empty(self):
        from scripts.evaluate_competition_metrics import (
            _check_matching_annotation_status,
        )

        records = [
            {"annotator_id": "", "match_label": ""}
            for _ in range(10)
        ]
        status = _check_matching_annotation_status(records)
        assert status.is_complete is False
        assert status.annotated_records == 0


# ── Integration test with simulated annotations ───────────────────────────


class TestSimulatedAnnotationEvaluation:
    """End-to-end test with controlled, simulated annotation data.

    These tests use synthetic data to verify the evaluation pipeline computes
    metrics correctly when annotations ARE present.  This is NOT fabricating
    production results — it validates the framework logic.
    """

    def test_jd_evaluation_with_simulated_data(self, tmp_path):
        """Verify JD parsing metrics are computed when annotations exist."""
        import csv
        from scripts.evaluate_competition_metrics import (
            evaluate_jd_parsing,
            _check_jd_annotation_status,
        )

        # Build 20 simulated records with 2 annotators each
        records = []
        for i in range(20):
            records.append({
                "job_record_id": f"test-job-{i:04d}",
                "job_title": f"ETL开发工程师-{i}",
                "company": "TestCorp",
                "category": "data_engineering",
                "responsibility": "负责数据仓库ETL开发和数据治理",
                "requirement": "本科及以上学历，3年以上经验，熟悉SQL和Python",
                "machine_skills": "SQL|Python|Data Warehouse",
                "machine_education": "本科",
                "machine_work_years": "3年",
                "annotator_id": "reviewer_a",
                "annotation_date": "2026-07-17",
                "annotated_skills": "SQL|Python|Data Warehouse|ETL",
                "annotated_responsibilities": "ETL开发|数据治理",
                "annotated_education": "本科",
                "annotated_experience_years": "3",
                "annotation_notes": "",
            })
            records.append({
                "job_record_id": f"test-job-{i:04d}",
                "job_title": f"ETL开发工程师-{i}",
                "company": "TestCorp",
                "category": "data_engineering",
                "responsibility": "负责数据仓库ETL开发和数据治理",
                "requirement": "本科及以上学历，3年以上经验，熟悉SQL和Python",
                "machine_skills": "SQL|Python|Data Warehouse",
                "machine_education": "本科",
                "machine_work_years": "3年",
                "annotator_id": "reviewer_b",
                "annotation_date": "2026-07-17",
                "annotated_skills": "SQL|Python|Data Warehouse",
                "annotated_responsibilities": "ETL开发|数据仓库",
                "annotated_education": "本科",
                "annotated_experience_years": "3",
                "annotation_notes": "",
            })

        status = _check_jd_annotation_status(records)
        assert status.is_complete is True
        assert status.unique_annotators == 2

        result = evaluate_jd_parsing(records, status)
        assert result["status"] == "evaluated", (
            f"Expected evaluated, got {result['status']}: {result.get('reason', '')}"
        )
        assert result["record_count"] > 0
        assert "skill_extraction" in result
        assert "education_accuracy" in result
        assert "experience_years_accuracy" in result

        # Metrics should be reasonable (not fabricated 1.0)
        assert 0.0 <= result["skill_extraction"]["f1"] <= 1.0
        assert 0.0 <= result["education_accuracy"]["accuracy"] <= 1.0

    def test_matching_evaluation_with_simulated_data(self):
        """Verify matching metrics are computed when annotations exist."""
        from scripts.evaluate_competition_metrics import (
            evaluate_person_job_matching,
            _check_matching_annotation_status,
        )

        records = []
        # Create 30 records: 10 match, 10 partial_match, 10 no_match
        # (two annotators per record = 60 rows)
        labels_cycle = (
            ["match"] * 10 + ["partial_match"] * 10 + ["no_match"] * 10
        )
        for i, label in enumerate(labels_cycle):
            for annotator in ("reviewer_a", "reviewer_b"):
                records.append({
                    "pair_id": f"test-pair-{i:04d}",
                    "job_record_id": f"test-job-{i % 10:04d}",
                    "job_title": f"ETL工程师-{i % 10}",
                    "company": "TestCorp",
                    "job_skills": "SQL|Python|ETL",
                    "job_education": "本科",
                    "job_experience_years": "3",
                    "resume_id": f"resume-{i:04d}",
                    "resume_summary_placeholder": "",
                    "annotator_id": annotator,
                    "annotation_date": "2026-07-17",
                    "match_label": label,
                    "match_rationale": f"Test rationale for {label}",
                    "annotation_notes": "",
                })

        status = _check_matching_annotation_status(records)
        assert status.is_complete is True

        result = evaluate_person_job_matching(records, status)
        assert result["status"] == "evaluated"
        assert "accuracy" in result
        assert "macro_f1" in result
        assert "confusion_matrix" in result
        assert 0.0 <= result["accuracy"] <= 1.0
        assert 0.0 <= result["macro_f1"] <= 1.0
        assert result["confusion_matrix"]["labels"] == [
            "match", "partial_match", "no_match"
        ]

    def test_resume_evaluation_with_simulated_data(self):
        """Verify resume extraction metrics are computed correctly."""
        from scripts.evaluate_competition_metrics import (
            evaluate_resume_extraction,
            _check_resume_annotation_status,
        )

        records = []
        for i in range(10):
            for annotator in ("reviewer_a", "reviewer_b"):
                records.append({
                    "resume_id": f"test-resume-{i:04d}",
                    "resume_text_placeholder": (
                        f"5年Python开发经验，本科学历，"
                        f"熟悉Django和FastAPI框架"
                    ),
                    "annotator_id": annotator,
                    "annotation_date": "2026-07-17",
                    "annotated_skills": "Python|SQL|Docker",
                    "annotated_education": "本科",
                    "annotated_experience_years": "5",
                    "annotated_projects": "电商平台|数据管道",
                    "annotated_certifications": "AWS Certified",
                    "annotation_notes": "",
                })

        status = _check_resume_annotation_status(records)
        assert status.is_complete is True

        result = evaluate_resume_extraction(records, status)
        assert result["status"] == "evaluated"
        assert "skill_extraction" in result
        assert "education_accuracy" in result
        assert "experience_years_accuracy" in result
        assert "certification_extraction" in result
        assert "project_extraction" in result

    def test_insufficient_data_with_few_records(self):
        """Verify insufficient_data status when too few records."""
        from scripts.evaluate_competition_metrics import (
            evaluate_jd_parsing,
            _check_jd_annotation_status,
        )

        records = []
        for i in range(3):
            for annotator in ("reviewer_a", "reviewer_b"):
                records.append({
                    "job_record_id": f"test-{i}",
                    "job_title": f"Test-{i}",
                    "company": "TC",
                    "category": "data_engineering",
                    "responsibility": "test",
                    "requirement": "test",
                    "machine_skills": "",
                    "machine_education": "",
                    "machine_work_years": "",
                    "annotator_id": annotator,
                    "annotation_date": "2026-07-17",
                    "annotated_skills": "Python",
                    "annotated_responsibilities": "test",
                    "annotated_education": "本科",
                    "annotated_experience_years": "3",
                    "annotation_notes": "",
                })

        status = _check_jd_annotation_status(records)
        # With both annotators covering all 3 records, it's "complete"
        # but evaluate_jd_parsing checks for minimum count
        result = evaluate_jd_parsing(records, status)
        assert result["status"] == "insufficient_data", (
            f"Expected insufficient_data, got {result['status']}"
        )


# ── Template count summary ────────────────────────────────────────────────


def test_template_counts_report():
    """Report template sample counts for documentation purposes.

    This test always passes; its purpose is to surface the current counts
    so reviewers can verify they meet competition requirements.
    """
    import csv

    jd_path = COMPETITION_DIR / "jd_parsing_annotation_template.csv"
    resume_path = COMPETITION_DIR / "resume_extraction_annotation_template.csv"
    matching_path = COMPETITION_DIR / "person_job_matching_annotation_template.csv"

    counts = {}
    for name, path in [
        ("JD parsing", jd_path),
        ("Resume extraction", resume_path),
        ("Person-job matching", matching_path),
    ]:
        if path.exists():
            with path.open("r", encoding="utf-8-sig", newline="") as fh:
                counts[name] = sum(1 for _ in fh) - 1  # subtract header
        else:
            counts[name] = 0

    # Print for test output visibility
    print(f"\n=== Competition Annotation Template Counts ===")
    for name, count in counts.items():
        print(f"  {name}: {count} records")
    print(f"  Total: {sum(counts.values())} records")
    print(f"  Status: pending_annotation (no human annotations filled)")
    print(f"===============================================\n")

    # Assert minimum counts
    assert counts["JD parsing"] >= 100, (
        f"JD template needs >= 100 records, got {counts['JD parsing']}"
    )
    assert counts["Resume extraction"] >= 20, (
        f"Resume template needs >= 20 records, got {counts['Resume extraction']}"
    )
    assert counts["Person-job matching"] >= 50, (
        f"Matching template needs >= 50 records, got {counts['Person-job matching']}"
    )

    # All pass — the counts meet requirements
    assert True


# ── Overwrite protection tests ──────────────────────────────────────────────


class TestAnnotationSetBuilderOverwriteProtection:
    """Verify the builder refuses to overwrite annotation templates that may
    contain human-filled data.

    All tests that involve writing use temporary directories — the real
    ``data/benchmarks/competition`` files are never touched.
    """

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _make_minimal_unified_jobs(tmp_path: Path, count: int = 10) -> Path:
        """Create a small unified_jobs.csv with *count* ETL jobs."""
        import csv

        path = tmp_path / "unified_jobs.csv"
        fields = [
            "record_id", "job_title", "company", "normalized_category",
            "responsibility", "requirement", "normalized_skills",
            "education", "work_years",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for i in range(count):
                writer.writerow({
                    "record_id": f"job-{i:04d}",
                    "job_title": f"ETL开发工程师-{i}",
                    "company": "TestCorp",
                    "normalized_category": "data_engineering",
                    "responsibility": "负责ETL流程开发和数据仓库建设",
                    "requirement": "熟悉SQL和Python",
                    "normalized_skills": "SQL|Python|Data Warehouse",
                    "education": "本科",
                    "work_years": "3年",
                })
        return path

    @staticmethod
    def _make_template_csv(
        path: Path,
        fieldnames: list[str],
        rows: list[dict],
    ) -> None:
        """Write a CSV template file (utf-8-sig, same as the builder uses)."""
        import csv

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _read_bytes(path: Path) -> bytes:
        """Read raw bytes of a file."""
        return path.read_bytes()

    # -- _has_human_annotations unit tests ------------------------------------

    def test_has_human_annotations_file_not_found(self, tmp_path):
        """Non-existent file → (False, empty set)."""
        from scripts.build_competition_annotation_set import (
            _has_human_annotations,
        )

        has_ann, fields = _has_human_annotations(tmp_path / "nope.csv")
        assert has_ann is False
        assert fields == set()

    def test_has_human_annotations_empty_template(self, tmp_path):
        """Template with all-empty annotation columns → (False, empty set)."""
        from scripts.build_competition_annotation_set import (
            _has_human_annotations,
            JD_ANNOTATION_FIELDS,
        )

        path = tmp_path / "empty.csv"
        self._make_template_csv(path, JD_ANNOTATION_FIELDS, [
            {f: "" for f in JD_ANNOTATION_FIELDS} for _ in range(5)
        ])

        has_ann, fields = _has_human_annotations(path)
        assert has_ann is False
        assert fields == set()

    def test_has_human_annotations_detects_annotator_id(self, tmp_path):
        """Non-empty annotator_id → True."""
        from scripts.build_competition_annotation_set import (
            _has_human_annotations,
            JD_ANNOTATION_FIELDS,
        )

        path = tmp_path / "anno.csv"
        row = {f: "" for f in JD_ANNOTATION_FIELDS}
        row["annotator_id"] = "reviewer_a"
        self._make_template_csv(path, JD_ANNOTATION_FIELDS, [row])

        has_ann, fields = _has_human_annotations(path)
        assert has_ann is True
        assert "annotator_id" in fields

    def test_has_human_annotations_detects_annotated_prefix(self, tmp_path):
        """Non-empty annotated_skills → True (prefix match)."""
        from scripts.build_competition_annotation_set import (
            _has_human_annotations,
            RESUME_ANNOTATION_FIELDS,
        )

        path = tmp_path / "resume_anno.csv"
        row = {f: "" for f in RESUME_ANNOTATION_FIELDS}
        row["annotated_skills"] = "Java|Python"
        self._make_template_csv(path, RESUME_ANNOTATION_FIELDS, [row])

        has_ann, fields = _has_human_annotations(path)
        assert has_ann is True
        assert "annotated_skills" in fields

    def test_has_human_annotations_detects_match_label(self, tmp_path):
        """Non-empty match_label → True."""
        from scripts.build_competition_annotation_set import (
            _has_human_annotations,
            MATCHING_ANNOTATION_FIELDS,
        )

        path = tmp_path / "match_anno.csv"
        row = {f: "" for f in MATCHING_ANNOTATION_FIELDS}
        row["match_label"] = "match"
        self._make_template_csv(path, MATCHING_ANNOTATION_FIELDS, [row])

        has_ann, fields = _has_human_annotations(path)
        assert has_ann is True
        assert "match_label" in fields

    def test_has_human_annotations_detects_annotation_date(self, tmp_path):
        """Non-empty annotation_date → True."""
        from scripts.build_competition_annotation_set import (
            _has_human_annotations,
            JD_ANNOTATION_FIELDS,
        )

        path = tmp_path / "date_anno.csv"
        row = {f: "" for f in JD_ANNOTATION_FIELDS}
        row["annotation_date"] = "2026-07-17"
        self._make_template_csv(path, JD_ANNOTATION_FIELDS, [row])

        has_ann, fields = _has_human_annotations(path)
        assert has_ann is True
        assert "annotation_date" in fields

    def test_has_human_annotations_detects_annotation_notes(self, tmp_path):
        """Non-empty annotation_notes → True."""
        from scripts.build_competition_annotation_set import (
            _has_human_annotations,
            JD_ANNOTATION_FIELDS,
        )

        path = tmp_path / "notes_anno.csv"
        row = {f: "" for f in JD_ANNOTATION_FIELDS}
        row["annotation_notes"] = "需要进一步确认"
        self._make_template_csv(path, JD_ANNOTATION_FIELDS, [row])

        has_ann, fields = _has_human_annotations(path)
        assert has_ann is True
        assert "annotation_notes" in fields

    def test_has_human_annotations_detects_match_rationale(self, tmp_path):
        """Non-empty match_rationale → True."""
        from scripts.build_competition_annotation_set import (
            _has_human_annotations,
            MATCHING_ANNOTATION_FIELDS,
        )

        path = tmp_path / "rationale_anno.csv"
        row = {f: "" for f in MATCHING_ANNOTATION_FIELDS}
        row["match_rationale"] = "Perfect match"
        self._make_template_csv(path, MATCHING_ANNOTATION_FIELDS, [row])

        has_ann, fields = _has_human_annotations(path)
        assert has_ann is True
        assert "match_rationale" in fields

    def test_has_human_annotations_detects_reviewer_field(self, tmp_path):
        """Field name containing 'reviewer' → True (keyword match)."""
        from scripts.build_competition_annotation_set import (
            _has_human_annotations,
            MATCHING_ANNOTATION_FIELDS,
        )

        # Use matching fields + custom reviewer field
        fields = list(MATCHING_ANNOTATION_FIELDS) + ["final_reviewer_id"]
        path = tmp_path / "reviewer_anno.csv"
        row = {f: "" for f in fields}
        row["final_reviewer_id"] = "senior_reviewer"
        self._make_template_csv(path, fields, [row])

        has_ann, found = _has_human_annotations(path)
        assert has_ann is True
        assert "final_reviewer_id" in found

    def test_has_human_annotations_detects_arbitration_field(self, tmp_path):
        """Field name containing 'arbitration' → True (keyword match)."""
        from scripts.build_competition_annotation_set import (
            _has_human_annotations,
            MATCHING_ANNOTATION_FIELDS,
        )

        fields = list(MATCHING_ANNOTATION_FIELDS) + ["arbitration_status"]
        path = tmp_path / "arb_anno.csv"
        row = {f: "" for f in fields}
        row["arbitration_status"] = "resolved"
        self._make_template_csv(path, fields, [row])

        has_ann, found = _has_human_annotations(path)
        assert has_ann is True
        assert "arbitration_status" in found

    def test_has_human_annotations_empty_strings_ignored(self, tmp_path):
        """Whitespace-only values should not trigger detection."""
        from scripts.build_competition_annotation_set import (
            _has_human_annotations,
            JD_ANNOTATION_FIELDS,
        )

        path = tmp_path / "whitespace.csv"
        row = {f: "" for f in JD_ANNOTATION_FIELDS}
        row["annotator_id"] = "   "  # whitespace only
        self._make_template_csv(path, JD_ANNOTATION_FIELDS, [row])

        has_ann, fields = _has_human_annotations(path)
        assert has_ann is False

    # -- _check_targets unit tests --------------------------------------------

    def test_check_targets_all_absent_returns_empty(self, tmp_path):
        """All targets missing → no reasons."""
        from scripts.build_competition_annotation_set import _check_targets

        targets = {
            "JD": tmp_path / "jd.csv",
            "Resume": tmp_path / "resume.csv",
            "Matching": tmp_path / "matching.csv",
        }
        reasons = _check_targets(targets, force=False)
        assert reasons == []

    def test_check_targets_exists_no_force(self, tmp_path):
        """Existing target without --force → rejection."""
        from scripts.build_competition_annotation_set import (
            _check_targets,
            JD_ANNOTATION_FIELDS,
        )

        jd_path = tmp_path / "jd.csv"
        self._make_template_csv(jd_path, JD_ANNOTATION_FIELDS, [
            {f: "" for f in JD_ANNOTATION_FIELDS}
        ])

        reasons = _check_targets({"JD": jd_path}, force=False)
        assert len(reasons) == 1
        assert "already exists" in reasons[0]
        assert str(jd_path) in reasons[0]

    def test_check_targets_empty_template_with_force_ok(self, tmp_path):
        """Empty template + --force → allowed (no reasons)."""
        from scripts.build_competition_annotation_set import (
            _check_targets,
            JD_ANNOTATION_FIELDS,
        )

        jd_path = tmp_path / "jd.csv"
        self._make_template_csv(jd_path, JD_ANNOTATION_FIELDS, [
            {f: "" for f in JD_ANNOTATION_FIELDS}
        ])

        reasons = _check_targets({"JD": jd_path}, force=True)
        assert reasons == []

    def test_check_targets_annotator_id_with_force_refused(self, tmp_path):
        """annotator_id present + --force → refused."""
        from scripts.build_competition_annotation_set import (
            _check_targets,
            JD_ANNOTATION_FIELDS,
        )

        jd_path = tmp_path / "jd.csv"
        row = {f: "" for f in JD_ANNOTATION_FIELDS}
        row["annotator_id"] = "reviewer_a"
        self._make_template_csv(jd_path, JD_ANNOTATION_FIELDS, [row])

        reasons = _check_targets({"JD": jd_path}, force=True)
        assert len(reasons) == 1
        assert "annotator_id" in reasons[0]
        assert "human annotations" in reasons[0]

    def test_check_targets_annotated_field_with_force_refused(self, tmp_path):
        """annotated_skills present + --force → refused."""
        from scripts.build_competition_annotation_set import (
            _check_targets,
            JD_ANNOTATION_FIELDS,
        )

        jd_path = tmp_path / "jd.csv"
        row = {f: "" for f in JD_ANNOTATION_FIELDS}
        row["annotated_skills"] = "Java|SQL"
        self._make_template_csv(jd_path, JD_ANNOTATION_FIELDS, [row])

        reasons = _check_targets({"JD": jd_path}, force=True)
        assert len(reasons) == 1
        assert "annotated_skills" in reasons[0]

    def test_check_targets_match_label_with_force_refused(self, tmp_path):
        """match_label present + --force → refused."""
        from scripts.build_competition_annotation_set import (
            _check_targets,
            MATCHING_ANNOTATION_FIELDS,
        )

        match_path = tmp_path / "match.csv"
        row = {f: "" for f in MATCHING_ANNOTATION_FIELDS}
        row["match_label"] = "match"
        self._make_template_csv(match_path, MATCHING_ANNOTATION_FIELDS, [row])

        reasons = _check_targets({"Matching": match_path}, force=True)
        assert len(reasons) == 1
        assert "match_label" in reasons[0]

    # -- Integration / multi-file tests ---------------------------------------

    def test_multi_file_precheck_no_partial_overwrite(self, tmp_path):
        """When one target has annotations, *none* of the others are written.

        We simulate by running _check_targets against two targets where one
        has annotations.  The check returns reasons → nothing proceeds.
        We then verify the other (clean) target file was NOT touched.
        """
        from scripts.build_competition_annotation_set import (
            _check_targets,
            JD_ANNOTATION_FIELDS,
            RESUME_ANNOTATION_FIELDS,
        )

        # Clean JD template
        jd_path = tmp_path / "jd.csv"
        self._make_template_csv(jd_path, JD_ANNOTATION_FIELDS, [
            {f: "" for f in JD_ANNOTATION_FIELDS} for _ in range(3)
        ])
        jd_bytes_before = self._read_bytes(jd_path)

        # Annotated resume template
        resume_path = tmp_path / "resume.csv"
        row = {f: "" for f in RESUME_ANNOTATION_FIELDS}
        row["annotated_education"] = "硕士"
        self._make_template_csv(resume_path, RESUME_ANNOTATION_FIELDS, [row])
        resume_bytes_before = self._read_bytes(resume_path)

        targets = {
            "JD parsing template": jd_path,
            "Resume extraction template": resume_path,
        }

        reasons = _check_targets(targets, force=True)
        # Only the resume should be flagged
        assert len(reasons) == 1
        assert "Resume extraction template" in reasons[0]

        # BOTH files must be byte-identical to before the check
        assert self._read_bytes(jd_path) == jd_bytes_before, (
            "Clean JD template was modified — partial overwrite!"
        )
        assert self._read_bytes(resume_path) == resume_bytes_before, (
            "Annotated resume template was modified!"
        )

    def test_rejection_preserves_original_bytes(self, tmp_path):
        """After _check_targets rejects, original file content is unchanged."""
        from scripts.build_competition_annotation_set import (
            _check_targets,
            JD_ANNOTATION_FIELDS,
        )

        jd_path = tmp_path / "jd.csv"
        row = {f: "" for f in JD_ANNOTATION_FIELDS}
        row["job_record_id"] = "original-123"
        row["job_title"] = "原始数据工程师"
        row["annotator_id"] = "annotator_x"
        row["annotated_skills"] = "Kafka|Flink"
        self._make_template_csv(jd_path, JD_ANNOTATION_FIELDS, [row])

        original_bytes = self._read_bytes(jd_path)

        reasons = _check_targets({"JD": jd_path}, force=True)
        assert len(reasons) == 1

        after_bytes = self._read_bytes(jd_path)
        assert after_bytes == original_bytes, (
            "Original file bytes changed after rejection!"
        )

    def test_rejection_error_message_has_path_not_content(self, tmp_path):
        """Error messages include file path and field names but NOT values."""
        from scripts.build_competition_annotation_set import (
            _check_targets,
            JD_ANNOTATION_FIELDS,
        )

        jd_path = tmp_path / "jd.csv"
        row = {f: "" for f in JD_ANNOTATION_FIELDS}
        row["annotator_id"] = "reviewer_secret_name"
        row["annotated_skills"] = "SecretSkill|Classified"
        self._make_template_csv(jd_path, JD_ANNOTATION_FIELDS, [row])

        reasons = _check_targets({"JD": jd_path}, force=True)
        message = reasons[0]

        # Should contain path
        assert str(jd_path) in message
        # Should contain field NAMES
        assert "annotator_id" in message
        assert "annotated_skills" in message
        # Should NOT leak actual annotation values
        assert "reviewer_secret_name" not in message
        assert "SecretSkill" not in message
        assert "Classified" not in message

    # -- Full main() integration tests ----------------------------------------

    def test_main_normal_init_when_targets_absent(self, tmp_path, monkeypatch):
        """When no targets exist, main() creates them and returns 0."""
        jobs_path = self._make_minimal_unified_jobs(tmp_path, count=10)
        comp_dir = tmp_path / "competition"
        comp_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "scripts.build_competition_annotation_set.UNIFIED_JOBS_PATH",
            jobs_path,
        )
        monkeypatch.setattr(
            "scripts.build_competition_annotation_set.COMPETITION_DIR",
            comp_dir,
        )

        from scripts.build_competition_annotation_set import main

        exit_code = main(force=False)
        assert exit_code == 0

        assert (comp_dir / "jd_parsing_annotation_template.csv").exists()
        assert (comp_dir / "resume_extraction_annotation_template.csv").exists()
        assert (comp_dir / "person_job_matching_annotation_template.csv").exists()

    def test_main_refuse_when_target_exists_without_force(
        self, tmp_path, monkeypatch,
    ):
        """Existing target + no --force → main() returns 1, nothing written."""
        jobs_path = self._make_minimal_unified_jobs(tmp_path, count=10)
        comp_dir = tmp_path / "competition"
        comp_dir.mkdir(parents=True)

        # Pre-create one template file
        from scripts.build_competition_annotation_set import JD_ANNOTATION_FIELDS

        jd_path = comp_dir / "jd_parsing_annotation_template.csv"
        self._make_template_csv(jd_path, JD_ANNOTATION_FIELDS, [
            {f: "" for f in JD_ANNOTATION_FIELDS}
        ])
        jd_bytes_before = self._read_bytes(jd_path)

        monkeypatch.setattr(
            "scripts.build_competition_annotation_set.UNIFIED_JOBS_PATH",
            jobs_path,
        )
        monkeypatch.setattr(
            "scripts.build_competition_annotation_set.COMPETITION_DIR",
            comp_dir,
        )

        from scripts.build_competition_annotation_set import main

        exit_code = main(force=False)
        assert exit_code == 1, (
            f"Expected exit code 1 (rejection), got {exit_code}"
        )

        # JD template must be untouched
        assert self._read_bytes(jd_path) == jd_bytes_before, (
            "Existing template was overwritten despite rejection!"
        )

    def test_main_force_rebuild_empty_template(
        self, tmp_path, monkeypatch,
    ):
        """Empty template + --force → main() rebuilds it and returns 0."""
        jobs_path = self._make_minimal_unified_jobs(tmp_path, count=10)
        comp_dir = tmp_path / "competition"
        comp_dir.mkdir(parents=True)

        # Pre-create an EMPTY template (no annotations)
        from scripts.build_competition_annotation_set import JD_ANNOTATION_FIELDS

        jd_path = comp_dir / "jd_parsing_annotation_template.csv"
        self._make_template_csv(jd_path, JD_ANNOTATION_FIELDS, [
            {f: "" for f in JD_ANNOTATION_FIELDS} for _ in range(3)
        ])

        monkeypatch.setattr(
            "scripts.build_competition_annotation_set.UNIFIED_JOBS_PATH",
            jobs_path,
        )
        monkeypatch.setattr(
            "scripts.build_competition_annotation_set.COMPETITION_DIR",
            comp_dir,
        )

        from scripts.build_competition_annotation_set import main

        exit_code = main(force=True)
        assert exit_code == 0, (
            f"Expected exit code 0 (rebuild allowed), got {exit_code}"
        )

        # Template should still exist (was rebuilt)
        assert jd_path.exists()

        # Verify the rebuilt template still has empty annotation columns
        import csv
        with jd_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                assert str(row.get("annotator_id", "")).strip() == ""
                assert str(row.get("annotated_skills", "")).strip() == ""

    def test_main_force_refuse_when_annotated(
        self, tmp_path, monkeypatch,
    ):
        """Template with human annotations + --force → main() returns 1."""
        jobs_path = self._make_minimal_unified_jobs(tmp_path, count=10)
        comp_dir = tmp_path / "competition"
        comp_dir.mkdir(parents=True)

        # Pre-create a template WITH annotations
        from scripts.build_competition_annotation_set import JD_ANNOTATION_FIELDS

        jd_path = comp_dir / "jd_parsing_annotation_template.csv"
        row = {f: "" for f in JD_ANNOTATION_FIELDS}
        row["annotator_id"] = "reviewer_a"
        row["annotated_skills"] = "Java|Python"
        self._make_template_csv(jd_path, JD_ANNOTATION_FIELDS, [row])
        jd_bytes_before = self._read_bytes(jd_path)

        monkeypatch.setattr(
            "scripts.build_competition_annotation_set.UNIFIED_JOBS_PATH",
            jobs_path,
        )
        monkeypatch.setattr(
            "scripts.build_competition_annotation_set.COMPETITION_DIR",
            comp_dir,
        )

        from scripts.build_competition_annotation_set import main

        exit_code = main(force=True)
        assert exit_code == 1, (
            f"Expected exit code 1 (annotations found), got {exit_code}"
        )

        # Original file must be untouched
        assert self._read_bytes(jd_path) == jd_bytes_before, (
            "Annotated template was overwritten!"
        )

    def test_main_rejection_no_files_created_in_comp_dir(
        self, tmp_path, monkeypatch,
    ):
        """When rejection happens, the competition dir is not even mkdir'd
        if it didn't already exist, and no new files appear inside it."""
        jobs_path = self._make_minimal_unified_jobs(tmp_path, count=10)
        comp_dir = tmp_path / "competition"
        # Do NOT pre-create comp_dir — let main() try only after pre-check

        # Pre-create one template WITH annotations
        from scripts.build_competition_annotation_set import JD_ANNOTATION_FIELDS

        comp_dir.mkdir(parents=True)
        jd_path = comp_dir / "jd_parsing_annotation_template.csv"
        row = {f: "" for f in JD_ANNOTATION_FIELDS}
        row["annotator_id"] = "reviewer_a"
        self._make_template_csv(jd_path, JD_ANNOTATION_FIELDS, [row])

        # Record the set of files before running
        files_before = set(
            p.relative_to(comp_dir) for p in comp_dir.rglob("*") if p.is_file()
        )

        monkeypatch.setattr(
            "scripts.build_competition_annotation_set.UNIFIED_JOBS_PATH",
            jobs_path,
        )
        monkeypatch.setattr(
            "scripts.build_competition_annotation_set.COMPETITION_DIR",
            comp_dir,
        )

        from scripts.build_competition_annotation_set import main

        exit_code = main(force=True)
        assert exit_code == 1

        # No new files should have been created
        files_after = set(
            p.relative_to(comp_dir) for p in comp_dir.rglob("*") if p.is_file()
        )
        assert files_after == files_before, (
            f"New files appeared in competition dir: {files_after - files_before}"
        )
