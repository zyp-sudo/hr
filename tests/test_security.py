"""Unit tests for app.core.security — JWT, password hashing, and auth dependencies."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import security as mod


# ======================================================================
# password hashing
# ======================================================================

def test_hash_password_returns_bcrypt_string():
    pw = "test_password"
    result = mod.hash_password(pw)
    assert result != pw
    assert result.startswith("$2b$") or result.startswith("$2a$")


def test_verify_password_matches_correctly():
    pw = "correct_horse_battery_staple"
    hashed = mod.hash_password(pw)
    assert mod.verify_password(pw, hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = mod.hash_password("real_password")
    assert mod.verify_password("wrong_password", hashed) is False


# ======================================================================
# session id
# ======================================================================

def test_generate_session_id_is_64_hex_chars():
    sid = mod.generate_session_id()
    assert len(sid) == 64
    assert all(c in "0123456789abcdef" for c in sid)


def test_generate_session_ids_are_unique():
    ids = {mod.generate_session_id() for _ in range(10)}
    assert len(ids) == 10


# ======================================================================
# JWT token creation / decoding
# ======================================================================

def test_create_access_token_encodes_payload():
    token = mod.create_access_token(user_id=42, role="admin", session_id="abc123")
    # decode it back
    from jose import jwt
    payload = jwt.decode(token, mod.SECRET_KEY, algorithms=[mod.ALGORITHM])
    assert payload["sub"] == "42"
    assert payload["role"] == "admin"
    assert payload["sid"] == "abc123"
    assert "iat" in payload
    assert "exp" in payload


def test_create_access_token_expires_in_24h():
    from datetime import datetime, timezone
    from jose import jwt
    token = mod.create_access_token(user_id=1, role="user", session_id="x")
    payload = jwt.decode(token, mod.SECRET_KEY, algorithms=[mod.ALGORITHM])
    delta = payload["exp"] - payload["iat"]
    assert delta == 60 * 24 * 60  # ACCESS_TOKEN_EXPIRE_MINUTES in seconds


# ======================================================================
# _verify_db_session
# ======================================================================

def test_verify_db_session_returns_false_when_row_is_None():
    with patch.object(mod, "engine") as mock_engine:
        conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None
        assert mod._verify_db_session(1, "sid") is False


def test_verify_db_session_returns_false_when_user_inactive():
    with patch.object(mod, "engine") as mock_engine:
        conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = conn
        row = MagicMock()
        row.is_active = False
        row.session_id = "sid"
        conn.execute.return_value.fetchone.return_value = row
        assert mod._verify_db_session(1, "sid") is False


def test_verify_db_session_returns_false_when_session_id_mismatches():
    with patch.object(mod, "engine") as mock_engine:
        conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = conn
        row = MagicMock()
        row.is_active = True
        row.session_id = "different_sid"
        conn.execute.return_value.fetchone.return_value = row
        assert mod._verify_db_session(1, "sid") is False


def test_verify_db_session_returns_true_when_session_matches():
    with patch.object(mod, "engine") as mock_engine:
        conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = conn
        row = MagicMock()
        row.is_active = True
        row.session_id = "sid"
        conn.execute.return_value.fetchone.return_value = row
        assert mod._verify_db_session(1, "sid") is True


def test_verify_db_session_returns_false_on_db_exception():
    with patch.object(mod, "engine") as mock_engine:
        mock_engine.connect.side_effect = RuntimeError("db down")
        assert mod._verify_db_session(1, "sid") is False


# ======================================================================
# get_current_user
# ======================================================================

def _credentials(token: str = "valid") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_get_current_user_raises_401_for_bad_token():
    with pytest.raises(HTTPException) as exc:
        mod.get_current_user(_credentials("not.a.jwt"))
    assert exc.value.status_code == 401


def test_get_current_user_raises_401_when_sub_missing():
    token = mod.create_access_token(user_id=1, role="user", session_id="s")
    # create a token without sub by crafting it manually
    from jose import jwt as jose_jwt
    bad = jose_jwt.encode({"role": "user", "sid": "s"}, mod.SECRET_KEY, algorithm=mod.ALGORITHM)
    with pytest.raises(HTTPException) as exc:
        mod.get_current_user(_credentials(bad))
    assert exc.value.status_code == 401


def test_get_current_user_raises_401_when_sid_missing():
    from jose import jwt as jose_jwt
    bad = jose_jwt.encode({"sub": "1", "role": "user"}, mod.SECRET_KEY, algorithm=mod.ALGORITHM)
    with pytest.raises(HTTPException) as exc:
        mod.get_current_user(_credentials(bad))
    assert exc.value.status_code == 401


def test_get_current_user_raises_401_when_sub_not_int():
    from jose import jwt as jose_jwt
    bad = jose_jwt.encode(
        {"sub": "not_an_int", "role": "user", "sid": "s"},
        mod.SECRET_KEY, algorithm=mod.ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        mod.get_current_user(_credentials(bad))
    assert exc.value.status_code == 401


def test_get_current_user_raises_401_when_db_session_rejected():
    token = mod.create_access_token(user_id=1, role="user", session_id="sid")
    with patch.object(mod, "_verify_db_session", return_value=False):
        with pytest.raises(HTTPException) as exc:
            mod.get_current_user(_credentials(token))
        assert exc.value.status_code == 401
        assert "会话已失效" in exc.value.detail


def test_get_current_user_returns_payload_on_success():
    token = mod.create_access_token(user_id=7, role="admin", session_id="s1")
    with patch.object(mod, "_verify_db_session", return_value=True):
        result = mod.get_current_user(_credentials(token))
        assert result == {"user_id": 7, "role": "admin"}


# ======================================================================
# get_current_admin
# ======================================================================

def test_get_current_admin_raises_403_for_non_admin():
    with pytest.raises(HTTPException) as exc:
        mod.get_current_admin({"user_id": 1, "role": "user"})
    assert exc.value.status_code == 403


def test_get_current_admin_passes_for_admin():
    result = mod.get_current_admin({"user_id": 1, "role": "admin"})
    assert result == {"user_id": 1, "role": "admin"}


# ======================================================================
# get_optional_user
# ======================================================================

def test_get_optional_user_returns_None_when_no_credentials():
    assert mod.get_optional_user(None) is None


def test_get_optional_user_returns_user_when_token_valid():
    token = mod.create_access_token(user_id=3, role="user", session_id="s")
    with patch.object(mod, "_verify_db_session", return_value=True):
        result = mod.get_optional_user(_credentials(token))
        assert result == {"user_id": 3, "role": "user"}


def test_get_optional_user_returns_None_when_token_invalid():
    with pytest.raises(HTTPException):
        mod.get_current_user(_credentials("bad.token"))
    # optional user catches the exception
    result = mod.get_optional_user(_credentials("bad.token"))
    assert result is None
