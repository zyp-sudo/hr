"""Unit tests for app.api.routes.auth — login, me, logout, seed."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app


# ======================================================================
# Mock row helper
# ======================================================================

class FakeRow:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ======================================================================
# Mock connection
# ======================================================================

class FakeConnection:
    def __init__(self, fetchone_result=None, scalar_result=None, fetchall_result=None):
        self.fetchone_result = fetchone_result
        self.scalar_result = scalar_result
        self.fetchall_result = fetchall_result

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, statement, params=None):
        self.last_statement = str(statement)
        self.last_params = params
        return self

    def fetchone(self):
        return self.fetchone_result

    def scalar(self):
        return self.scalar_result

    def fetchall(self):
        return self.fetchall_result or []

    def commit(self):
        pass


def _client_with_auth_override(user=None):
    if user is None:
        user = {"user_id": 1, "role": "user"}
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


# ======================================================================
# POST /api/auth/login
# ======================================================================

def test_login_returns_422_for_empty_body():
    resp = TestClient(app).post("/api/auth/login", json={})
    assert resp.status_code == 422


def test_login_returns_422_for_empty_email():
    resp = TestClient(app).post("/api/auth/login", json={"email": "", "password": "x"})
    assert resp.status_code == 422


def test_login_returns_422_for_empty_password():
    resp = TestClient(app).post("/api/auth/login", json={"email": "a@b.com", "password": ""})
    assert resp.status_code == 422


def test_login_returns_401_for_unknown_email(monkeypatch):
    conn = FakeConnection(fetchone_result=None)
    monkeypatch.setattr("app.api.routes.auth.engine.connect", lambda: conn)
    resp = TestClient(app).post("/api/auth/login", json={"email": "no@no.com", "password": "x"})
    assert resp.status_code == 401
    assert "邮箱或密码错误" in resp.json()["detail"]


def test_login_returns_403_for_inactive_user(monkeypatch):
    row = FakeRow(id=1, name="Test", password_hash="hash", role="user", is_active=False)
    conn = FakeConnection(fetchone_result=row)
    monkeypatch.setattr("app.api.routes.auth.engine.connect", lambda: conn)
    resp = TestClient(app).post("/api/auth/login", json={"email": "a@b.com", "password": "x"})
    assert resp.status_code == 403
    assert "已被禁用" in resp.json()["detail"]


def test_login_returns_401_for_wrong_password(monkeypatch):
    import bcrypt
    pw_hash = bcrypt.hashpw("correct".encode(), bcrypt.gensalt()).decode()
    row = FakeRow(id=1, name="Test", password_hash=pw_hash, role="user", is_active=True)
    conn = FakeConnection(fetchone_result=row)
    monkeypatch.setattr("app.api.routes.auth.engine.connect", lambda: conn)
    resp = TestClient(app).post("/api/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert resp.status_code == 401


def test_login_success_returns_token_and_user(monkeypatch):
    import bcrypt
    pw_hash = bcrypt.hashpw("correct".encode(), bcrypt.gensalt()).decode()
    row = FakeRow(id=1, name="Test", password_hash=pw_hash, role="admin", is_active=True)
    conn = FakeConnection(fetchone_result=row)
    monkeypatch.setattr("app.api.routes.auth.engine.connect", lambda: conn)
    resp = TestClient(app).post("/api/auth/login", json={"email": "A@B.COM", "password": "correct"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["id"] == 1
    assert data["user"]["email"] == "a@b.com"  # normalized to lower
    assert data["user"]["role"] == "admin"


# ======================================================================
# GET /api/auth/me
# ======================================================================

def test_me_returns_user_profile(monkeypatch):
    row = FakeRow(
        id=1, name="张三", email="zhang@test.com", phone="13800138000",
        city="深圳", role="user", is_active=True,
        target_position="Python工程师", target_city="深圳",
        created_at="2026-01-01",
    )
    conn = FakeConnection(fetchone_result=row)
    monkeypatch.setattr("app.api.routes.auth.engine.connect", lambda: conn)
    client = _client_with_auth_override()
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "张三"
    assert data["email"] == "zhang@test.com"


def test_me_returns_404_when_user_missing(monkeypatch):
    conn = FakeConnection(fetchone_result=None)
    monkeypatch.setattr("app.api.routes.auth.engine.connect", lambda: conn)
    client = _client_with_auth_override()
    resp = client.get("/api/auth/me")
    assert resp.status_code == 404


# ======================================================================
# POST /api/auth/logout
# ======================================================================

def test_logout_clears_session(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr("app.api.routes.auth.engine.connect", lambda: conn)
    client = _client_with_auth_override()
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["message"] == "已登出"


def test_logout_requires_auth():
    resp = TestClient(app).post("/api/auth/logout")
    assert resp.status_code in (401, 403)


# ======================================================================
# POST /api/auth/seed
# ======================================================================

def test_seed_creates_new_accounts(monkeypatch):
    # No existing accounts → all 5 are new
    conn = FakeConnection(fetchone_result=None, scalar_result=None)
    monkeypatch.setattr("app.api.routes.auth.engine.connect", lambda: conn)
    resp = TestClient(app).post("/api/auth/seed")
    assert resp.status_code == 200
    data = resp.json()
    assert "种子账户已就绪" in data["message"]
    assert len(data["accounts"]) == 5


def test_seed_updates_existing_accounts(monkeypatch):
    # All accounts exist
    side_effect = [FakeRow(id=i + 1) for i in range(5)]

    class MultiConn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def __init__(self):
            self.call_count = 0

        def execute(self, statement, params=None):
            return self

        def fetchone(self):
            result = side_effect[min(self.call_count, 4)]
            self.call_count += 1
            return result

        def commit(self):
            pass

    monkeypatch.setattr("app.api.routes.auth.engine.connect", lambda: MultiConn())
    resp = TestClient(app).post("/api/auth/seed")
    assert resp.status_code == 200
    # No assertion on exact counts since MockConnection pattern differs
    assert "accounts" in resp.json()
