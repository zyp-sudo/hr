from scripts.evaluate_accuracy import run_benchmark


def test_mvp_accuracy_benchmark_passes_thresholds():
    report = run_benchmark()
    assert report["case_count"] >= 100
    assert report["passed"] is True
    assert min(
        report["metrics"]["jd_skill_extraction_f1"],
        report["metrics"]["resume_field_accuracy"],
        report["metrics"]["match_decision_accuracy"],
    ) >= 0.9
