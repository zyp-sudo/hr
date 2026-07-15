"""Load the ETL dataset into MySQL and the knowledge graph into Neo4j."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

import pymysql
from neo4j import GraphDatabase
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SYNC_STATE_PATH = DATA / "sync" / "storage_state.json"
MYSQL_SCHEMA = DATA / "warehouse" / "mysql_schema.sql"

MYSQL_TABLES = (
    ("job_postings", DATA / "etl" / "unified_jobs.csv"),
    ("job_skill_evidence", DATA / "etl" / "unified_job_skills.csv"),
    ("kg_nodes", DATA / "kg" / "nodes.csv"),
    ("kg_edges", DATA / "kg" / "edges.csv"),
    ("skill_trends", DATA / "kg" / "skill_trends.csv"),
    ("role_aliases", DATA / "kg" / "role_aliases.csv"),
    ("graph_versions", DATA / "kg" / "graph_versions.csv"),
    ("data_quality_report", DATA / "etl" / "data_quality_report.csv"),
)


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_sync_state() -> dict[str, str]:
    if not SYNC_STATE_PATH.exists():
        return {}
    return json.loads(SYNC_STATE_PATH.read_text(encoding="utf-8"))


def current_sync_state() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): file_digest(path)
        for _, path in MYSQL_TABLES
    }


def batches(items: Iterable[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def csv_rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            yield {key: (value if value != "" else None) for key, value in row.items()}


def schema_statements() -> list[str]:
    text = MYSQL_SCHEMA.read_text(encoding="utf-8")
    statements: list[str] = []
    for part in text.split(";"):
        lines = [line for line in part.splitlines() if not line.strip().startswith("--")]
        statement = "\n".join(lines).strip()
        if statement:
            statements.append(statement)
    return statements


def load_mysql(
    mysql_url: str,
    reset: bool,
    if_empty: bool,
    batch_size: int,
    changed_tables: set[str] | None = None,
) -> dict[str, int]:
    url = make_url(mysql_url)
    database = url.database or "job_kg"
    server = pymysql.connect(
        host=url.host or "localhost",
        port=url.port or 3306,
        user=url.username or "root",
        password=url.password or "",
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with server.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        server.close()

    connection = pymysql.connect(
        host=url.host or "localhost",
        port=url.port or 3306,
        user=url.username or "root",
        password=url.password or "",
        database=database,
        charset="utf8mb4",
        autocommit=False,
    )
    counts: dict[str, int] = {}
    try:
        with connection.cursor() as cursor:
            if reset:
                for table, _ in reversed(MYSQL_TABLES):
                    cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
            for statement in schema_statements():
                if statement.upper().startswith(("CREATE DATABASE", "USE ")):
                    continue
                cursor.execute(statement)
            if if_empty:
                cursor.execute("SELECT COUNT(*) FROM job_postings")
                if int(cursor.fetchone()[0]) > 0:
                    print("MySQL already contains job data; skipping import.")
                    return {"job_postings": 0}
            connection.commit()

            for table, path in MYSQL_TABLES:
                if changed_tables is not None and table not in changed_tables:
                    counts[table] = 0
                    print(f"MySQL {table}: unchanged, skipped")
                    continue
                if changed_tables is not None:
                    cursor.execute(f"DELETE FROM `{table}`")
                    connection.commit()
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    columns = next(csv.reader(handle))
                database_columns = [
                    {"from": "from_id", "to": "to_id"}.get(column, column)
                    if table == "kg_edges"
                    else column
                    for column in columns
                ]
                quoted = ", ".join(f"`{column}`" for column in database_columns)
                placeholders = ", ".join(["%s"] * len(columns))
                updates = ", ".join(
                    f"`{column}`=VALUES(`{column}`)" for column in database_columns
                )
                sql = (
                    f"INSERT INTO `{table}` ({quoted}) VALUES ({placeholders}) "
                    f"ON DUPLICATE KEY UPDATE {updates}"
                )
                loaded = 0
                for batch in batches(csv_rows(path), batch_size):
                    values = [tuple(row[column] for column in columns) for row in batch]
                    cursor.executemany(sql, values)
                    connection.commit()
                    loaded += len(values)
                counts[table] = loaded
                print(f"MySQL {table}: {loaded}")
    finally:
        connection.close()
    return counts


def load_neo4j(
    uri: str,
    username: str,
    password: str,
    database: str,
    reset: bool,
    if_empty: bool,
    batch_size: int,
    changed: bool = True,
) -> dict[str, int]:
    driver = GraphDatabase.driver(uri, auth=(username, password))
    counts: dict[str, int] = {}
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            if not changed:
                print("Neo4j graph inputs unchanged; skipped import.")
                return {"nodes": 0, "edges": 0}
            session.run("CREATE CONSTRAINT kg_node_id IF NOT EXISTS FOR (n:KgNode) REQUIRE n.id IS UNIQUE").consume()
            session.run("CREATE CONSTRAINT role_alias_id IF NOT EXISTS FOR (n:RoleAlias) REQUIRE n.id IS UNIQUE").consume()
            session.run("CREATE CONSTRAINT skill_trend_id IF NOT EXISTS FOR (n:SkillTrend) REQUIRE n.id IS UNIQUE").consume()
            session.run("CREATE CONSTRAINT graph_version_id IF NOT EXISTS FOR (n:GraphVersion) REQUIRE n.id IS UNIQUE").consume()
            if if_empty:
                existing = session.run("MATCH (n:KgNode) RETURN count(n) AS count").single()["count"]
                if int(existing) > 0:
                    print("Neo4j already contains graph data; skipping import.")
                    return {"nodes": 0, "edges": 0}
            if reset:
                session.run("MATCH (n) WHERE n:KgNode OR n:RoleAlias OR n:SkillTrend OR n:GraphVersion DETACH DELETE n").consume()

            node_count = 0
            for batch in batches(csv_rows(DATA / "kg" / "nodes.csv"), batch_size):
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (n:KgNode {id: row.id})
                    SET n.label = row.label, n.type = row.type, n.canonical = row.canonical,
                        n.count = toInteger(row.count), n.firstSeen = row.first_seen,
                        n.lastSeen = row.last_seen, n.propertiesJson = row.properties
                    """,
                    rows=batch,
                ).consume()
                node_count += len(batch)
            counts["nodes"] = node_count
            print(f"Neo4j nodes: {node_count}")

            edge_count = 0
            for batch in batches(csv_rows(DATA / "kg" / "edges.csv"), batch_size):
                session.run(
                    """
                    UNWIND $rows AS row
                    MATCH (a:KgNode {id: row['from']}), (b:KgNode {id: row['to']})
                    MERGE (a)-[r:KG_RELATION {id: row.id}]->(b)
                    SET r.type = row.type, r.weight = toInteger(row.weight),
                        r.confidence = toFloat(row.confidence), r.firstSeen = row.first_seen,
                        r.lastSeen = row.last_seen, r.evidence = row.evidence
                    """,
                    rows=batch,
                ).consume()
                edge_count += len(batch)
            counts["edges"] = edge_count
            print(f"Neo4j edges: {edge_count}")

            alias_count = 0
            for batch in batches(csv_rows(DATA / "kg" / "role_aliases.csv"), batch_size):
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (n:RoleAlias {id: row.alias + '|' + row.canonical_role_id})
                    SET n.alias = row.alias, n.canonicalRoleId = row.canonical_role_id,
                        n.canonicalRole = row.canonical_role,
                        n.evidenceCount = toInteger(row.evidence_count)
                    """,
                    rows=batch,
                ).consume()
                alias_count += len(batch)
            counts["role_aliases"] = alias_count

            trend_count = 0
            for batch in batches(csv_rows(DATA / "kg" / "skill_trends.csv"), batch_size):
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (n:SkillTrend {id: row.period + '|' + row.role_id + '|' + row.skill})
                    SET n.period = row.period, n.roleId = row.role_id, n.role = row.role,
                        n.skill = row.skill, n.dimension = row.dimension,
                        n.demand = toInteger(row.demand), n.sourceCount = toInteger(row.source_count)
                    """,
                    rows=batch,
                ).consume()
                trend_count += len(batch)
            counts["skill_trends"] = trend_count

            version_count = 0
            for batch in batches(csv_rows(DATA / "kg" / "graph_versions.csv"), batch_size):
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (n:GraphVersion {id: row.version_id})
                    SET n.period = row.period, n.nodeCount = toInteger(row.node_count),
                        n.edgeCount = toInteger(row.edge_count), n.jobCount = toInteger(row.job_count),
                        n.skillMentions = toInteger(row.skill_mentions)
                    """,
                    rows=batch,
                ).consume()
                version_count += len(batch)
            counts["versions"] = version_count
            print(f"Neo4j metadata: aliases={alias_count}, trends={trend_count}, versions={version_count}")
    finally:
        driver.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Clear managed tables/nodes before loading.")
    parser.add_argument("--if-empty", action="store_true", help="Skip a database that already has data.")
    parser.add_argument("--sync", action="store_true", help="Replace only data files whose SHA-256 digest changed.")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    mysql_url = os.getenv(
        "MYSQL_URL", "mysql+pymysql://root:password@localhost:3307/job_kg?charset=utf8mb4"
    )
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password123")
    neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")
    if args.if_empty and args.sync:
        parser.error("--if-empty and --sync cannot be used together")

    previous_state = read_sync_state() if args.sync else {}
    current_state = current_sync_state()
    changed_tables = None
    if args.sync:
        changed_tables = {
            table
            for table, path in MYSQL_TABLES
            if previous_state.get(str(path.relative_to(ROOT)).replace("\\", "/"))
            != current_state[str(path.relative_to(ROOT)).replace("\\", "/")]
        }
    load_mysql(mysql_url, args.reset, args.if_empty, args.batch_size, changed_tables=changed_tables)
    graph_changed = not args.sync or any(
        previous_state.get(path) != current_state[path]
        for path in (
            "data/kg/nodes.csv",
            "data/kg/edges.csv",
            "data/kg/role_aliases.csv",
            "data/kg/skill_trends.csv",
            "data/kg/graph_versions.csv",
        )
    )
    load_neo4j(
        neo4j_uri,
        neo4j_username,
        neo4j_password,
        neo4j_database,
        args.reset or (args.sync and graph_changed),
        args.if_empty,
        args.batch_size,
        changed=graph_changed,
    )
    if args.sync or args.reset:
        SYNC_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SYNC_STATE_PATH.write_text(json.dumps(current_state, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
