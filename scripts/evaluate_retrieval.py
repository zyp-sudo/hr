"""Run the fixed judged-query retrieval benchmark against Elasticsearch."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.es_client import ElasticsearchClient

DEFAULT_QRELS = ROOT / "data" / "benchmarks" / "retrieval_qrels_v1.json"
DEFAULT_OUTPUT = ROOT / "data" / "benchmarks" / "retrieval_report.json"


def dcg(grades: list[int]) -> float:
    return sum((2**grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(grades))


def ranked_metrics(ids: list[str], grades: dict[str, int], k: int = 10) -> dict[str, float]:
    observed = [int(grades.get(record_id, 0)) for record_id in ids[:k]]
    ideal = sorted((int(value) for value in grades.values()), reverse=True)[:k]
    ideal_dcg = dcg(ideal)
    first_relevant = next((rank for rank, grade in enumerate(observed, 1) if grade > 0), None)
    return {
        f"mrr@{k}": round(1 / first_relevant if first_relevant else 0.0, 4),
        f"ndcg@{k}": round(dcg(observed) / ideal_dcg if ideal_dcg else 0.0, 4),
        f"judged_coverage@{k}": round(sum(record_id in grades for record_id in ids[:k]) / k, 4),
    }


def evaluate(client: ElasticsearchClient, qrels_path: Path = DEFAULT_QRELS, k: int = 10) -> dict[str, Any]:
    qrels = json.loads(qrels_path.read_text(encoding="utf-8"))
    results = []
    for item in qrels["queries"]:
        response = client.search_jobs(keyword=item["query"], page_size=k)
        ids = [str(hit["_id"]) for hit in response["hits"]["hits"]]
        results.append({"query": item["query"], "returned_ids": ids, **ranked_metrics(ids, item["grades"], k)})
    return {
        "benchmark": "manual_pooled_qrels_v1",
        "query_count": len(results),
        "k": k,
        "mean_mrr": round(mean(item[f"mrr@{k}"] for item in results), 4),
        "mean_ndcg": round(mean(item[f"ndcg@{k}"] for item in results), 4),
        "mean_judged_coverage": round(mean(item[f"judged_coverage@{k}"] for item in results), 4),
        "queries": results,
        "annotation": qrels["metadata"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qrels", default=str(DEFAULT_QRELS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()
    report = evaluate(ElasticsearchClient(), Path(args.qrels), args.k)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
