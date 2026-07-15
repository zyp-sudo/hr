from scripts.evaluate_holdout import evaluate, load_cases


def test_fixed_holdout_is_separate_and_reports_real_errors():
    cases = load_cases()
    report = evaluate(cases)
    assert report["case_count"] == len(cases) >= 20
    assert report["annotation"]["reviewers"] == 1
    assert report["annotation"]["double_blind"] is False
    assert report["all_metrics_perfect"] is False
    assert report["metrics"]["skill_f1"] >= 0.6
    assert report["metrics"]["category_accuracy"] >= 0.6
    assert len(report["category_by_stratum"]) >= 5
