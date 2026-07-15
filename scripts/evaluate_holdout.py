"""Evaluate a fixed, manually labelled holdout separate from rule templates."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import job_taxonomy as taxonomy

DEFAULT_INPUT = ROOT / "data" / "benchmarks" / "accuracy_holdout_v1.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "benchmarks" / "accuracy_holdout_report.json"


def load_cases(path: Path = DEFAULT_INPUT) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _skill_counts(cases: list[dict[str, Any]]) -> tuple[int, int, int]:
    tp = fp = fn = 0
    for case in cases:
        expected = set(case["expected"])
        predicted = set(taxonomy.extract_skills(case["text"]))
        tp += len(expected & predicted)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
    return tp, fp, fn


def _f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    value = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(value, 4)}


def evaluate(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    cases = cases or load_cases()
    skill_cases = [case for case in cases if case["task"] == "skills"]
    category_cases = [case for case in cases if case["task"] == "category"]
    skill_metrics = _f1(*_skill_counts(skill_cases))
    category_predictions = {
        case["id"]: taxonomy.classify_job(
            case["text"], "", "", "", taxonomy.extract_skills(case["text"])
        )
        for case in category_cases
    }
    category_accuracy = sum(
        category_predictions[case["id"]] == case["expected"] for case in category_cases
    ) / len(category_cases)

    strata: dict[str, list[bool]] = defaultdict(list)
    for case in category_cases:
        strata[case["stratum"]].append(category_predictions[case["id"]] == case["expected"])
    category_by_stratum = {
        name: {"count": len(values), "accuracy": round(sum(values) / len(values), 4)}
        for name, values in sorted(strata.items())
    }
    return {
        "benchmark": "manual_fixed_holdout_v1",
        "case_count": len(cases),
        "annotation": {
            "labels": "fixed manual review, stored independently from evaluator",
            "reviewers": 1,
            "double_blind": False,
            "limitations": "Small diagnostic holdout; expand with two independent domain annotators before production claims.",
        },
        "metrics": {**{f"skill_{key}": value for key, value in skill_metrics.items()}, "category_accuracy": round(category_accuracy, 4)},
        "category_by_stratum": category_by_stratum,
        "all_metrics_perfect": all(value == 1.0 for value in [skill_metrics["f1"], category_accuracy]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--min-skill-f1", type=float)
    parser.add_argument("--min-category-accuracy", type=float)
    args = parser.parse_args()
    report = evaluate(load_cases(Path(args.input)))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    failed = (
        args.min_skill_f1 is not None and report["metrics"]["skill_f1"] < args.min_skill_f1
    ) or (
        args.min_category_accuracy is not None
        and report["metrics"]["category_accuracy"] < args.min_category_accuracy
    )
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
