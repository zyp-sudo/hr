"""Verify cross-store row-count invariants for the current generated snapshot."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[1]


def csv_record_count(relative_path: str) -> int:
    with (ROOT / relative_path).open("r", encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


CURRENT_JOB_COUNT = csv_record_count("data/etl/unified_jobs.csv")
CURRENT_SKILL_EVIDENCE_COUNT = csv_record_count("data/etl/unified_job_skills.csv")


EXPECTED_MYSQL = {
    "job_postings": CURRENT_JOB_COUNT,
    "job_skill_evidence": CURRENT_SKILL_EVIDENCE_COUNT,
    "kg_nodes": 907,
    "kg_edges": 1_806,
    "skill_trends": 2_932,
    "role_aliases": 33_998,
    "graph_versions": 22,
}
EXPECTED_NEO4J = {
    "kg_nodes": 907,
    "kg_edges": 1_806,
    # Neo4j ids are case-sensitive; MySQL's utf8mb4_unicode_ci composite key
    # intentionally collapses 96 case-only alias variants.
    "role_aliases": 34_094,
    "skill_trends": 2_932,
    "graph_versions": 22,
}
EXPECTED_ES = {"job_index": CURRENT_JOB_COUNT}


def assert_counts(store: str, actual: dict[str, int], expected: dict[str, int]) -> None:
    mismatches = {
        name: {"expected": expected[name], "actual": actual.get(name)}
        for name in expected
        if actual.get(name) != expected[name]
    }
    if mismatches:
        raise AssertionError(f"{store} count mismatch: {json.dumps(mismatches, ensure_ascii=False)}")


def mysql_counts() -> dict[str, int]:
    url = os.getenv(
        "MYSQL_URL", "mysql+pymysql://root:password@localhost:3307/job_kg?charset=utf8mb4"
    )
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return {
                table: int(connection.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar_one())
                for table in EXPECTED_MYSQL
            }
    finally:
        engine.dispose()


def neo4j_counts() -> dict[str, int]:
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "password123")),
    )
    queries = {
        "kg_nodes": "MATCH (n:KgNode) RETURN count(n) AS count",
        "kg_edges": "MATCH (:KgNode)-[r:KG_RELATION]->(:KgNode) RETURN count(r) AS count",
        "role_aliases": "MATCH (n:RoleAlias) RETURN count(n) AS count",
        "skill_trends": "MATCH (n:SkillTrend) RETURN count(n) AS count",
        "graph_versions": "MATCH (n:GraphVersion) RETURN count(n) AS count",
    }
    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            return {
                name: int(session.run(query).single()["count"])
                for name, query in queries.items()
            }
    finally:
        driver.close()


def elasticsearch_counts() -> dict[str, int]:
    kwargs: dict[str, Any] = {"hosts": [os.getenv("ES_HOST", "http://localhost:9200")]}
    username = os.getenv("ES_USERNAME")
    password = os.getenv("ES_PASSWORD")
    if username and password:
        kwargs["basic_auth"] = (username, password)
    client = Elasticsearch(**kwargs)
    try:
        return {"job_index": int(client.count(index="job_index")["count"])}
    finally:
        client.close()


def main() -> None:
    report = {
        "mysql": mysql_counts(),
        "neo4j": neo4j_counts(),
        "elasticsearch": elasticsearch_counts(),
    }
    assert_counts("mysql", report["mysql"], EXPECTED_MYSQL)
    assert_counts("neo4j", report["neo4j"], EXPECTED_NEO4J)
    assert_counts("elasticsearch", report["elasticsearch"], EXPECTED_ES)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
