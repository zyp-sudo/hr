"""Authentication & authorization utilities.

JWT-based auth with single-session enforcement:
- A new session_id is generated on every login and stored in the DB.
- The JWT carries that session_id.
- Every authenticated request verifies the JWT session_id matches the DB.
- If someone else logs in with the same account, the old session_id is
  overwritten → the old JWT immediately becomes invalid → 互斥登入（单点登录强制）.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SECRET_KEY: str = os.getenv("JWT_SECRET", "xh202621-dev-secret-change-in-production")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

# ---------------------------------------------------------------------------
# HTTP Bearer scheme (used by Swagger UI "Authorize" button)
# ---------------------------------------------------------------------------
security_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="登录成功后把 Token 粘贴到这里即可访问需认证的接口",
)


# ====================================================================
# Public helpers
# ====================================================================

def hash_password(password: str) -> str:
    """Return bcrypt hash of *password*."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if *plain_password* matches *hashed_password*."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_access_token(user_id: int, role: str, session_id: str) -> str:
    """Create a signed JWT carrying user identity + current session id."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "sid": session_id,          # session_id — validates single-session
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def generate_session_id() -> str:
    """Return a cryptographically random session id (64 hex chars)."""
    return secrets.token_hex(32)


# ====================================================================
# FastAPI dependencies (the "gatekeepers")
# ====================================================================

def _verify_db_session(user_id: int, session_id: str) -> bool:
    """Return True if *session_id* is still the active session for *user_id*.

    This is the single-session enforcement point: if anyone logged in with
    the same account after this token was issued, the DB session_id has
    already been overwritten and this check will fail.
    """
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT session_id, is_active FROM users WHERE id = :uid"),
                {"uid": user_id},
            ).fetchone()
    except Exception:
        logger.exception("DB unreachable during session check for user %s", user_id)
        return False

    if row is None:
        return False
    if not row.is_active:
        return False
    return row.session_id == session_id


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> dict:
    """FastAPI dependency — validates JWT **and** DB session, returns user payload.

    Raises 401 if:
    - Token is missing / malformed / expired
    - Account was deactivated
    - Another login overwrote the session (互斥登入)

    Usage::

        @router.get("/api/data/full")
        def full_data(user: dict = Depends(get_current_user)):
            ...
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="请先登录",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1 — Decode JWT
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        session_id: str | None = payload.get("sid")
        role: str = payload.get("role", "user")
    except JWTError:
        logger.warning("JWT decode failed")
        raise credentials_exception from None

    if user_id_str is None or session_id is None:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception from None

    # 2 — Verify session is still active in DB (single-session enforcement)
    if not _verify_db_session(user_id, session_id):
        logger.info(
            "Session rejected for user %s — session was invalidated "
            "(另一个设备登录了同一账号)", user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已失效，您的账号在另一处登录了，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"user_id": user_id, "role": role}


def get_current_admin(
    user: dict = Depends(get_current_user),
) -> dict:
    """Same as *get_current_user* but additionally requires role == 'admin'."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> dict | None:
    """Return the user payload if a valid token is present, else None.

    Use this for endpoints that work for both guests and logged-in users
    (e.g. preview that shows more data when logged in).
    """
    if credentials is None:
        return None
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None
