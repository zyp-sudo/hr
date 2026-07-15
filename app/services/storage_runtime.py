from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from typing import Any, Iterator

from neo4j import GraphDatabase
from sqlalchemy import text
from sqlalchemy.engine import Engine


class MySQLJobRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def ping(self) -> bool:
        with self.engine.connect() as connection:
            return connection.execute(text("SELECT 1")).scalar_one() == 1

    def jobs(self, role_limit: int = 100) -> list[dict[str, Any]]:
        statement = text(
            """
            SELECT role_id, role_name, normalized_category, COUNT(*) AS source_count,
                   GROUP_CONCAT(DISTINCT normalized_skills SEPARATOR '|') AS skill_groups
            FROM job_postings
            WHERE role_id IS NOT NULL AND role_id <> ''
            GROUP BY role_id, role_name, normalized_category
            ORDER BY source_count DESC
            LIMIT :limit
            """
        )
        with self.engine.connect() as connection:
            rows = connection.execute(statement, {"limit": role_limit}).mappings().all()
        result: list[dict[str, Any]] = []
        for row in rows:
            skills = sorted({item for item in (row["skill_groups"] or "").split("|") if item})
            result.append(
                {
                    "id": row["role_id"],
                    "name": row["role_name"] or row["role_id"],
                    "type": row["normalized_category"] or "other",
                    "description": "MySQL 真实岗位数据聚合",
                    "sourceCount": int(row["source_count"] or 0),
                    "skills": skills,
                    "storage": "mysql",
                }
            )
        return result

    def real_jobs(self, limit: int) -> dict[str, Any]:
        count_statement = text("SELECT COUNT(*) FROM job_postings")
        query = text(
            """
            SELECT record_id, origin_record_id, source_name, source_url, collected_at,
                   published_at, company, department, product, category, city, job_title,
                   work_years, responsibility, requirement, normalized_skills
            FROM job_postings
            ORDER BY collected_at DESC, record_id
            LIMIT :limit
            """
        )
        stats_query = text(
            """
            SELECT city, category, department, work_years, normalized_skills
            FROM job_postings
            """
        )
        sources_query = text(
            """
            SELECT source_name, MIN(source_url) AS source_url, COUNT(*) AS records,
                   MAX(collected_at) AS collected_at
            FROM job_postings GROUP BY source_name ORDER BY records DESC
            """
        )
        effective_limit = max(1, min(limit if limit > 0 else 100, 1000))
        with self.engine.connect() as connection:
            record_count = int(connection.execute(count_statement).scalar_one())
            rows = connection.execute(query, {"limit": effective_limit}).mappings().all()
            stat_rows = connection.execute(stats_query).mappings().all()
            source_rows = connection.execute(sources_query).mappings().all()

        skill_counts: Counter[str] = Counter()
        city_counts: Counter[str] = Counter()
        category_counts: Counter[str] = Counter()
        department_counts: Counter[str] = Counter()
        work_year_counts: Counter[str] = Counter()
        for row in stat_rows:
            skill_counts.update(item for item in (row["normalized_skills"] or "").split("|") if item)
            for counter, value in (
                (city_counts, row["city"]),
                (category_counts, row["category"]),
                (department_counts, row["department"]),
                (work_year_counts, row["work_years"]),
            ):
                if value:
                    counter[str(value)] += 1

        def top(counter: Counter[str]) -> list[dict[str, Any]]:
            return [{"name": name, "count": count} for name, count in counter.most_common(20)]

        jobs = [
            {
                "source": row["source_name"],
                "postId": row["origin_record_id"] or row["record_id"],
                "title": row["job_title"],
                "company": row["company"],
                "bg": row["department"],
                "product": row["product"],
                "category": row["category"],
                "city": row["city"],
                "workYears": row["work_years"],
                "lastUpdateTime": row["published_at"],
                "responsibility": row["responsibility"],
                "requirement": row["requirement"],
                "skills": [item for item in (row["normalized_skills"] or "").split("|") if item],
                "sourceUrl": row["source_url"],
                "fetchedAt": row["collected_at"],
                "storage": "mysql",
            }
            for row in rows
        ]
        return {
            "jobs": jobs,
            "recordCount": record_count,
            "returnedCount": len(jobs),
            "skillStats": top(skill_counts),
            "cityStats": top(city_counts),
            "categoryStats": top(category_counts),
            "bgStats": top(department_counts),
            "workYearStats": top(work_year_counts),
            "sources": [
                {
                    "source": row["source_name"],
                    "baseUrl": row["source_url"],
                    "licenseNote": "详见数据源注册表",
                    "records": int(row["records"]),
                    "fetchedAt": row["collected_at"],
                }
                for row in source_rows
            ],
            "storage": "mysql",
        }


class Neo4jGraphRepository:
    def __init__(self, uri: str, username: str, password: str, database: str):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.database = database

    def close(self) -> None:
        self.driver.close()

    def ping(self) -> bool:
        self.driver.verify_connectivity()
        return True

    @contextmanager
    def session(self) -> Iterator[Any]:
        with self.driver.session(database=self.database) as session:
            yield session

    def graph(self, node_limit: int) -> dict[str, Any]:
        with self.session() as session:
            nodes = [
                dict(record)
                for record in session.run(
                    """
                    MATCH (n:KgNode)
                    RETURN n.id AS id, n.label AS label, n.type AS type,
                           coalesce(n.count, 0) AS count
                    ORDER BY count DESC, id
                    LIMIT $limit
                    """,
                    limit=max(1, min(node_limit, 1000)),
                )
            ]
            ids = [row["id"] for row in nodes]
            edge_records = [
                dict(record)
                for record in session.run(
                    """
                    MATCH (a:KgNode)-[r:KG_RELATION]->(b:KgNode)
                    WHERE a.id IN $ids AND b.id IN $ids
                    RETURN a.id AS source, b.id AS target, r.type AS type,
                           coalesce(r.weight, 0) AS weight
                    ORDER BY weight DESC
                    LIMIT 3000
                    """,
                    ids=ids,
                )
            ]
            edges = [
                {
                    "from": row["source"],
                    "to": row["target"],
                    "relation": row["type"],
                    **row,
                }
                for row in edge_records
            ]
        return {"nodes": nodes, "edges": edges, "storage": "neo4j"}

    def summary(self) -> dict[str, Any]:
        with self.session() as session:
            node_count = session.run("MATCH (n:KgNode) RETURN count(n) AS count").single()["count"]
            edge_count = session.run(
                "MATCH (:KgNode)-[r:KG_RELATION]->(:KgNode) RETURN count(r) AS count"
            ).single()["count"]
            role_alias_count = session.run("MATCH (n:RoleAlias) RETURN count(n) AS count").single()["count"]
            skill_trend_count = session.run("MATCH (n:SkillTrend) RETURN count(n) AS count").single()["count"]
            version_count = session.run("MATCH (n:GraphVersion) RETURN count(n) AS count").single()["count"]
            node_types = {
                record["type"] or "unknown": int(record["count"])
                for record in session.run(
                    "MATCH (n:KgNode) RETURN n.type AS type, count(n) AS count ORDER BY count DESC"
                )
            }
            edge_types = {
                record["type"] or "unknown": int(record["count"])
                for record in session.run(
                    """
                    MATCH (:KgNode)-[r:KG_RELATION]->(:KgNode)
                    RETURN r.type AS type, count(r) AS count ORDER BY count DESC
                    """
                )
            }
            top_nodes = [
                dict(record)
                for record in session.run(
                    """
                    MATCH (n:KgNode)
                    RETURN n.id AS id, n.label AS label, n.type AS type,
                           coalesce(n.count, 0) AS count, n.firstSeen AS firstSeen,
                           n.lastSeen AS lastSeen
                    ORDER BY count DESC LIMIT 30
                    """
                )
            ]
            top_edge_records = [
                dict(record)
                for record in session.run(
                    """
                    MATCH (a:KgNode)-[r:KG_RELATION]->(b:KgNode)
                    RETURN a.id AS source, b.id AS target, r.type AS type,
                           coalesce(r.weight, 0) AS weight,
                           coalesce(r.confidence, 0.0) AS confidence,
                           r.firstSeen AS firstSeen, r.lastSeen AS lastSeen
                    ORDER BY weight DESC LIMIT 30
                    """
                )
            ]
            top_edges = [
                {
                    "from": row["source"],
                    "to": row["target"],
                    "relation": row["type"],
                    **row,
                }
                for row in top_edge_records
            ]
            alias_samples = [
                dict(record)
                for record in session.run(
                    "MATCH (n:RoleAlias) RETURN n.alias AS alias, n.canonicalRoleId AS canonicalRoleId, "
                    "n.canonicalRole AS canonicalRole, n.evidenceCount AS evidenceCount "
                    "ORDER BY evidenceCount DESC LIMIT 20"
                )
            ]
            trend_samples = [
                dict(record)
                for record in session.run(
                    "MATCH (n:SkillTrend) RETURN n.period AS period, n.roleId AS roleId, n.role AS role, "
                    "n.skill AS skill, n.dimension AS dimension, n.demand AS demand, n.sourceCount AS sourceCount "
                    "ORDER BY period DESC, demand DESC LIMIT 30"
                )
            ]
            version_samples = [
                dict(record)
                for record in session.run(
                    "MATCH (n:GraphVersion) RETURN n.id AS versionId, n.period AS period, "
                    "n.nodeCount AS nodeCount, n.edgeCount AS edgeCount, n.jobCount AS jobCount, "
                    "n.skillMentions AS skillMentions ORDER BY period DESC LIMIT 30"
                )
            ]
        return {
            "nodes": int(node_count),
            "edges": int(edge_count),
            "roleAliases": int(role_alias_count),
            "skillTrends": int(skill_trend_count),
            "versions": int(version_count),
            "nodeTypeCounts": node_types,
            "edgeTypeCounts": edge_types,
            "topNodes": top_nodes,
            "topEdges": top_edges,
            "aliasSamples": alias_samples,
            "trendSamples": trend_samples,
            "versionSamples": version_samples,
            "outputs": ["Neo4j KgNode", "Neo4j KG_RELATION", "/api/graph"],
            "storage": "neo4j",
        }
