"""Load the ETL dataset into MySQL and the knowledge graph into Neo4j."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

import pymysql
from neo4j import GraphDatabase
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SYNC_STATE_PATH = DATA / "sync" / "storage_state.json"
SYNC_LOCK_PATH = DATA / "sync" / "storage_state.lock"
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

TABLE_KEYS = {
    "job_postings": ("record_id",),
    "job_skill_evidence": ("record_id",),
    "kg_nodes": ("id",),
    "kg_edges": ("id",),
    "skill_trends": ("period", "role_id", "skill"),
    "role_aliases": ("alias", "canonical_role_id"),
    "graph_versions": ("version_id",),
    "data_quality_report": ("source_id",),
}


@contextmanager
def exclusive_lock(path: Path, timeout_seconds: float = 30.0):
    """Prevent concurrent snapshot writers from interleaving database/state updates."""
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Another storage sync owns {path}")
            time.sleep(0.2)
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        os.close(descriptor)
        descriptor = None
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        path.unlink(missing_ok=True)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_sync_state(path: Path = SYNC_STATE_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def _quoted_columns(table: str, columns: list[str]) -> list[str]:
    return [
        {"from": "from_id", "to": "to_id"}.get(column, column)
        if table == "kg_edges"
        else column
        for column in columns
    ]


def reconcile_mysql_table(
    cursor: Any,
    table: str,
    path: Path,
    batch_size: int,
) -> dict[str, int]:
    """Reconcile a CSV snapshot without deleting or rewriting unchanged rows."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        source_columns = next(csv.reader(handle))
    columns = _quoted_columns(table, source_columns)
    keys = TABLE_KEYS[table]
    non_keys = [column for column in columns if column not in keys]
    stage = f"_sync_{table}_{os.getpid()}"
    cursor.execute(f"DROP TEMPORARY TABLE IF EXISTS `{stage}`")
    cursor.execute(f"CREATE TEMPORARY TABLE `{stage}` LIKE `{table}`")

    quoted = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    stage_non_keys = [column for column in columns if column not in TABLE_KEYS[table]]
    if stage_non_keys:
        duplicate_update = ", ".join(
            f"`{column}`=VALUES(`{column}`)" for column in stage_non_keys
        )
        stage_sql = (
            f"INSERT INTO `{stage}` ({quoted}) VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {duplicate_update}"
        )
    else:
        stage_sql = f"INSERT IGNORE INTO `{stage}` ({quoted}) VALUES ({placeholders})"
    staged = 0
    for batch in batches(csv_rows(path), batch_size):
        values = [tuple(row[column] for column in source_columns) for row in batch]
        cursor.executemany(stage_sql, values)
        staged += len(values)

    join = " AND ".join(f"t.`{key}` = s.`{key}`" for key in keys)
    missing = f"t.`{keys[0]}` IS NULL"
    changed = " OR ".join(f"NOT (t.`{column}` <=> s.`{column}`)" for column in non_keys)
    predicate = f"{missing} OR {changed}" if changed else missing
    cursor.execute(
        f"SELECT COUNT(*) FROM `{stage}` s LEFT JOIN `{table}` t ON {join} WHERE {predicate}"
    )
    changed_count = int(cursor.fetchone()[0])

    if changed_count:
        selected = ", ".join(f"s.`{column}`" for column in columns)
        updates = ", ".join(
            f"`{column}`=VALUES(`{column}`)" for column in non_keys
        )
        merge = (
            f"INSERT INTO `{table}` ({quoted}) SELECT {selected} FROM `{stage}` s "
            f"LEFT JOIN `{table}` t ON {join} WHERE {predicate}"
        )
        if updates:
            merge += f" ON DUPLICATE KEY UPDATE {updates}"
        cursor.execute(merge)

    reverse_join = " AND ".join(f"t.`{key}` = s.`{key}`" for key in keys)
    cursor.execute(
        f"SELECT COUNT(*) FROM `{table}` t LEFT JOIN `{stage}` s ON {reverse_join} "
        f"WHERE s.`{keys[0]}` IS NULL"
    )
    deleted_count = int(cursor.fetchone()[0])
    if deleted_count:
        cursor.execute(
            f"DELETE t FROM `{table}` t LEFT JOIN `{stage}` s ON {reverse_join} "
            f"WHERE s.`{keys[0]}` IS NULL"
        )
    cursor.execute(f"DROP TEMPORARY TABLE `{stage}`")
    return {"staged": staged, "changed": changed_count, "deleted": deleted_count}


def ensure_job_posting_search_fields(cursor: Any) -> None:
    """Migrate an existing warehouse created before salary/education fields."""
    cursor.execute("SHOW COLUMNS FROM `job_postings`")
    existing_columns = {str(row[0]) for row in cursor.fetchall()}
    definitions = {
        "education": "VARCHAR(32)",
        "salary_min": "INT",
        "salary_max": "INT",
        "salary_text": "VARCHAR(255)",
    }
    for column, definition in definitions.items():
        if column not in existing_columns:
            cursor.execute(f"ALTER TABLE `job_postings` ADD COLUMN `{column}` {definition}")

    cursor.execute("SHOW INDEX FROM `job_postings`")
    existing_indexes = {str(row[2]) for row in cursor.fetchall()}
    if "idx_job_education" not in existing_indexes:
        cursor.execute("ALTER TABLE `job_postings` ADD INDEX `idx_job_education` (`education`)")
    if "idx_job_salary" not in existing_indexes:
        cursor.execute(
            "ALTER TABLE `job_postings` ADD INDEX `idx_job_salary` (`salary_min`, `salary_max`)"
        )


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
            ensure_job_posting_search_fields(cursor)
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
                    result = reconcile_mysql_table(cursor, table, path, batch_size)
                    connection.commit()
                    counts[table] = result["changed"]
                    print(
                        f"MySQL {table}: staged={result['staged']}, "
                        f"changed={result['changed']}, deleted={result['deleted']}"
                    )
                    continue
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    columns = next(csv.reader(handle))
                database_columns = _quoted_columns(table, columns)
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
    parser.add_argument("--state-file", default=str(SYNC_STATE_PATH))
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

    state_path = Path(args.state_file)
    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    with exclusive_lock(lock_path):
        previous_state = read_sync_state(state_path) if args.sync else {}
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
            atomic_write_json(state_path, current_state)


if __name__ == "__main__":
    main()
