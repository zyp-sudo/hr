"""Authentication routes — login, logout, current-user, seed accounts.

Single-session enforcement (互斥登入):
- Every successful login generates a new session_id stored in the users table.
- The JWT carries that session_id.
- ``get_current_user`` verifies the JWT session_id against the DB on EVERY request.
- So when the same account logs in from a second device, the first device's
  session_id becomes stale → its next request gets 401 "会话已失效".
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from app.core.security import (
    create_access_token,
    generate_session_id,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db.session import engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ====================================================================
# Seed accounts (pre-hashed at module load)
# ====================================================================

_SEED_ACCOUNTS = [
    {"email": "admin@talentmatch.cn",   "password": "admin123",   "name": "系统管理员", "role": "admin"},
    {"email": "hr_zhang@talentmatch.cn", "password": "hr123456",  "name": "张HR",       "role": "user"},
    {"email": "hr_li@talentmatch.cn",    "password": "hr123456",  "name": "李HR",       "role": "user"},
    {"email": "iv_wang@talentmatch.cn",  "password": "iv123456",  "name": "王面试官",    "role": "user"},
    {"email": "iv_chen@talentmatch.cn",  "password": "iv123456",  "name": "陈面试官",    "role": "user"},
]


# ====================================================================
# POST /api/auth/login
# ====================================================================

@router.post("/login")
def login(body: dict) -> dict:
    """Authenticate with email + password.

    Returns a JWT token. Calling this **invalidates any previous session**
    for the same account (互斥登入).
    """
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="邮箱和密码不能为空",
        )

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, name, password_hash, role, is_active "
                "FROM users WHERE email = :email LIMIT 1"
            ),
            {"email": email},
        ).fetchone()

    if row is None:
        logger.info("Login attempt for unknown email: %s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    if not row.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用，请联系管理员",
        )

    if not verify_password(password, row.password_hash):
        logger.info("Wrong password for user %s (%s)", row.id, email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    # ---- Generate new session — this invalidates any old session ----
    session_id = generate_session_id()
    token = create_access_token(user_id=row.id, role=row.role, session_id=session_id)

    with engine.connect() as conn:
        conn.execute(
            text("UPDATE users SET session_id = :sid WHERE id = :uid"),
            {"sid": session_id, "uid": row.id},
        )
        conn.commit()

    logger.info("User %s (%s) logged in, new session issued", row.id, email)
    return {
        "token": token,
        "user": {
            "id": row.id,
            "name": row.name,
            "email": email,
            "role": row.role,
        },
    }


# ====================================================================
# GET /api/auth/me
# ====================================================================

@router.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    """Return the currently logged-in user's profile."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, name, email, phone, city, role, is_active, "
                "target_position, target_city, created_at "
                "FROM users WHERE id = :uid LIMIT 1"
            ),
            {"uid": user["user_id"]},
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return {
        "id": row.id,
        "name": row.name,
        "email": row.email,
        "phone": row.phone,
        "city": row.city,
        "role": row.role,
        "is_active": row.is_active,
        "target_position": row.target_position,
        "target_city": row.target_city,
        "created_at": str(row.created_at) if row.created_at else None,
    }


# ====================================================================
# POST /api/auth/logout
# ====================================================================

@router.post("/logout")
def logout(user: dict = Depends(get_current_user)) -> dict:
    """Clear the current session — logs out from ALL devices for this account."""
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE users SET session_id = NULL WHERE id = :uid"),
            {"uid": user["user_id"]},
        )
        conn.commit()
    logger.info("User %s logged out, session cleared", user["user_id"])
    return {"message": "已登出"}


# ====================================================================
# POST /api/auth/seed — one-time account seeder
# ====================================================================

@router.post("/seed")
def seed_accounts() -> dict:
    """Create / update the 5 built-in test accounts.

    Idempotent: existing accounts are updated (password reset), new ones inserted.
    Safe to call multiple times.
    """
    created, updated = 0, 0
    with engine.connect() as conn:
        for acct in _SEED_ACCOUNTS:
            existing = conn.execute(
                text("SELECT id FROM users WHERE email = :email LIMIT 1"),
                {"email": acct["email"]},
            ).fetchone()

            hashed = hash_password(acct["password"])
            if existing:
                conn.execute(
                    text(
                        "UPDATE users SET password_hash = :pw, name = :nm, role = :rl, "
                        "is_active = 1, session_id = NULL WHERE id = :uid"
                    ),
                    {"pw": hashed, "nm": acct["name"], "rl": acct["role"], "uid": existing.id},
                )
                updated += 1
            else:
                conn.execute(
                    text(
                        "INSERT INTO users (name, email, password_hash, role, is_active) "
                        "VALUES (:nm, :em, :pw, :rl, 1)"
                    ),
                    {"nm": acct["name"], "em": acct["email"], "pw": hashed, "rl": acct["role"]},
                )
                created += 1
        conn.commit()

    logger.info("Seed complete: %d created, %d updated", created, updated)
    return {
        "message": f"种子账户已就绪（新建 {created}，更新 {updated}）",
        "accounts": [
            {"email": a["email"], "password": a["password"], "name": a["name"], "role": a["role"]}
            for a in _SEED_ACCOUNTS
        ],
    }
