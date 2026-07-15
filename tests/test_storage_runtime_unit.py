from __future__ import annotations

from app.services import storage_runtime as module


class Result:
    def __init__(self, rows=None, scalar=None):
        self.rows = rows or []
        self.scalar = scalar

    def scalar_one(self):
        return self.scalar

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)

    def single(self):
        return self.rows[0]


class SQLConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, statement, params=None):
        sql = str(statement)
        if "SELECT 1" in sql:
            return Result(scalar=1)
        if "GROUP BY role_id" in sql:
            return Result([{"role_id": "r1", "role_name": "工程师", "normalized_category": "技术", "source_count": 2, "skill_groups": "SQL|Python|SQL"}])
        if "COUNT(*) FROM job_postings" in sql:
            return Result(scalar=2)
        if "ORDER BY collected_at" in sql:
            return Result([{
                "record_id": "1", "origin_record_id": "o1", "source_name": "Source",
                "source_url": "https://example.test/1", "collected_at": "2026-01-02",
                "published_at": "2026-01-01", "company": "C", "department": "D",
                "product": "P", "category": "技术", "city": "深圳", "job_title": "工程师",
                "work_years": "3年", "responsibility": "开发", "requirement": "本科",
                "normalized_skills": "Python|SQL",
            }])
        if "SELECT city, category" in sql:
            return Result([{"city": "深圳", "category": "技术", "department": "D", "work_years": "3年", "normalized_skills": "Python|SQL"}])
        if "GROUP BY source_name" in sql:
            return Result([{"source_name": "Source", "source_url": "https://example.test", "records": 2, "collected_at": "2026-01-02"}])
        raise AssertionError(sql)


class SQLEngine:
    def connect(self):
        return SQLConnection()


def test_mysql_repository_queries_and_shapes_results():
    repo = module.MySQLJobRepository(SQLEngine())
    assert repo.ping()
    roles = repo.jobs(role_limit=5)
    assert roles[0]["skills"] == ["Python", "SQL"]
    assert roles[0]["sourceCount"] == 2
    result = repo.real_jobs(0)
    assert result["recordCount"] == 2
    assert result["jobs"][0]["skills"] == ["Python", "SQL"]
    assert result["skillStats"][0] == {"name": "Python", "count": 1}
    assert result["sources"][0]["records"] == 2


class NeoResult(Result):
    pass


class NeoSession:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def run(self, query, **params):
        compact = " ".join(query.split())
        if "RETURN n.id AS id, n.label AS label" in compact and "LIMIT $limit" in compact:
            return NeoResult([{"id": "n1", "label": "Python", "type": "skill", "count": 2}])
        if "WHERE a.id IN $ids" in compact:
            assert params["ids"] == ["n1"]
            return NeoResult([{"source": "n1", "target": "n1", "type": "related", "weight": 1}])
        if "count(n) AS count" in compact and "RoleAlias" not in compact and "SkillTrend" not in compact and "GraphVersion" not in compact and "n.type" not in compact:
            return NeoResult([{"count": 1}])
        if "count(r) AS count" in compact and "r.type" not in compact:
            return NeoResult([{"count": 2}])
        if "RoleAlias" in compact and "count(n)" in compact:
            return NeoResult([{"count": 3}])
        if "SkillTrend" in compact and "count(n)" in compact:
            return NeoResult([{"count": 4}])
        if "GraphVersion" in compact and "count(n)" in compact:
            return NeoResult([{"count": 5}])
        if "RETURN n.type AS type" in compact:
            return NeoResult([{"type": "skill", "count": 1}])
        if "RETURN r.type AS type" in compact:
            return NeoResult([{"type": "related", "count": 2}])
        if "ORDER BY count DESC LIMIT 30" in compact:
            return NeoResult([{"id": "n1", "label": "Python", "type": "skill", "count": 1}])
        if "ORDER BY weight DESC LIMIT 30" in compact:
            return NeoResult([{"source": "n1", "target": "n2", "type": "related", "weight": 2}])
        if "RETURN n.alias AS alias" in compact:
            return NeoResult([{"alias": "开发", "canonicalRoleId": "r1"}])
        if "RETURN n.period AS period" in compact:
            return NeoResult([{"period": "2026-01", "skill": "Python"}])
        if "RETURN n.id AS versionId" in compact:
            return NeoResult([{"versionId": "v1"}])
        raise AssertionError(compact)


class Driver:
    def __init__(self):
        self.closed = False
        self.verified = False

    def verify_connectivity(self):
        self.verified = True

    def session(self, database):
        assert database == "neo4j"
        return NeoSession()

    def close(self):
        self.closed = True


def test_neo4j_repository_graph_summary_and_lifecycle(monkeypatch):
    driver = Driver()
    monkeypatch.setattr(module.GraphDatabase, "driver", lambda *_args, **_kwargs: driver)
    repo = module.Neo4jGraphRepository("bolt://test", "neo4j", "pw", "neo4j")
    assert repo.ping()
    graph = repo.graph(0)
    assert graph["nodes"][0]["id"] == "n1"
    assert graph["edges"][0]["relation"] == "related"
    summary = repo.summary()
    assert summary["nodes"] == 1
    assert summary["edges"] == 2
    assert summary["roleAliases"] == 3
    assert summary["skillTrends"] == 4
    assert summary["versions"] == 5
    repo.close()
    assert driver.closed
