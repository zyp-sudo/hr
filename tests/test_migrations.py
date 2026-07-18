"""Unit tests for app.db.migrations — schema migration helpers with mocked DB."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.db import migrations as mod


# ======================================================================
# Mock connection
# ======================================================================

class FakeConnection:
    def __init__(self, scalar_result=None, fetchall_result=None):
        self.scalar_result = scalar_result
        self.fetchall_result = fetchall_result
        self.statements: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, statement, params=None):
        self.statements.append(str(statement))
        return self

    def scalar(self):
        return self.scalar_result

    def fetchall(self):
        return self.fetchall_result or []

    def commit(self):
        pass


# ======================================================================
# ensure_auth_schema
# ======================================================================

def test_ensure_auth_schema_creates_table_when_missing():
    conn = FakeConnection(scalar_result=0)
    with patch.object(mod, "engine") as mock_engine:
        mock_engine.connect.return_value = conn
        mod.ensure_auth_schema()
    # Should have executed CREATE TABLE
    assert any("CREATE TABLE IF NOT EXISTS users" in s for s in conn.statements)


def test_ensure_auth_schema_skips_when_all_columns_exist():
    conn = FakeConnection(
        scalar_result=1,
        fetchall_result=[
            ("password_hash",), ("is_active",), ("role",), ("session_id",),
        ],
    )
    with patch.object(mod, "engine") as mock_engine:
        mock_engine.connect.return_value = conn
        mod.ensure_auth_schema()
    # No ALTER TABLE statements should have been issued
    alter_stmts = [s for s in conn.statements if "ALTER TABLE" in s]
    assert len(alter_stmts) == 0


def test_ensure_auth_schema_adds_missing_columns():
    conn = FakeConnection(
        scalar_result=1,
        fetchall_result=[
            # Only password_hash exists; is_active, role, session_id are missing
            ("password_hash",),
        ],
    )
    with patch.object(mod, "engine") as mock_engine:
        mock_engine.connect.return_value = conn
        mod.ensure_auth_schema()
    alter_stmts = [s for s in conn.statements if "ALTER TABLE" in s]
    assert len(alter_stmts) == 3  # is_active, role, session_id


def test_ensure_auth_schema_handles_alter_exception():
    conn = FakeConnection(
        scalar_result=1,
        fetchall_result=[
            # Only password_hash exists
            ("password_hash",),
        ],
    )
    # Make the first ALTER fail, the rest succeed
    original_execute = conn.execute

    call_count = [0]

    def failing_execute(statement, params=None):
        s = str(statement)
        if "ALTER TABLE" in s:
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("alter failed")
        return original_execute(statement, params)

    conn.execute = failing_execute

    with patch.object(mod, "engine") as mock_engine:
        mock_engine.connect.return_value = conn
        # Should not raise — exceptions are caught and logged
        mod.ensure_auth_schema()
    # The first ALTER failed but the other two should have been attempted
    alter_stmts = [s for s in conn.statements if "ALTER TABLE" in s]
    assert len(alter_stmts) >= 2


# ======================================================================
# ensure_ai_hub_schema
# ======================================================================

def test_ensure_ai_hub_schema_creates_tables():
    conn = FakeConnection()
    with patch.object(mod, "engine") as mock_engine:
        mock_engine.connect.return_value = conn
        mod.ensure_ai_hub_schema()
    assert any("CREATE TABLE IF NOT EXISTS ai_providers" in s for s in conn.statements)
    assert any("CREATE TABLE IF NOT EXISTS ai_models" in s for s in conn.statements)


# ======================================================================
# ensure_demo_jobs_schema
# ======================================================================

def test_ensure_demo_jobs_schema_creates_table_and_seeds_when_empty():
    conn = FakeConnection(scalar_result=0)
    with patch.object(mod, "engine") as mock_engine:
        mock_engine.connect.return_value = conn
        mod.ensure_demo_jobs_schema()
    assert any("CREATE TABLE IF NOT EXISTS demo_homepage_jobs" in s for s in conn.statements)
    # Should have 10 INSERTs
    insert_stmts = [s for s in conn.statements if "INSERT INTO demo_homepage_jobs" in s]
    assert len(insert_stmts) == 10


def test_ensure_demo_jobs_schema_skips_seed_when_rows_exist():
    conn = FakeConnection(scalar_result=5)
    with patch.object(mod, "engine") as mock_engine:
        mock_engine.connect.return_value = conn
        mod.ensure_demo_jobs_schema()
    insert_stmts = [s for s in conn.statements if "INSERT INTO demo_homepage_jobs" in s]
    assert len(insert_stmts) == 0
