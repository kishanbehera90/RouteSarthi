"""Auth logic: password hashing, JWT sessions, password-reset tokens.

Mirrors the engine.py/metrics.py split — business logic lives here, main.py
stays a thin endpoint layer.

SECRET_KEY must be identical across every process (unlike DB/graph, which
degrade gracefully without a .env) — a per-process auto-generated secret would
cause intermittent 401s under multiple workers, which is worse than a clean
failure. So this module raises loudly, lazily, the same pattern db.py's
conninfo() uses for DATABASE_URL: only auth endpoints fail until it's set.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Header, HTTPException

from .config import settings
from .db import get_pool

TOKEN_TTL_DAYS = 14          # short-lived on purpose: no revocation list exists
RESET_TTL_MINUTES = 60
RESET_RATE_LIMIT_MINUTES = 2  # don't send another reset email faster than this
ALGORITHM = "HS256"


def _secret_key() -> str:
    if not settings.secret_key:
        raise RuntimeError("SECRET_KEY is not set (backend/.env) — auth is unavailable")
    return settings.secret_key


# --- passwords ---------------------------------------------------------------
def hash_password(password: str) -> str:
    try:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    except ValueError as e:  # bcrypt's 72-byte input limit
        raise ValueError("password is too long") from e


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# --- JWT sessions --------------------------------------------------------------
def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def decode_token(token: str) -> int:
    """Returns the user id, or raises jwt.PyJWTError on any invalid/expired token."""
    payload = jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
    return int(payload["sub"])


def _fetch_user(user_id: int):
    """One quick indexed query, connection released immediately — never hold
    a pool connection (max_size=4, shared with the routing engine) across a
    bcrypt call or any other CPU-bound work."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, email, name FROM users WHERE id=%s;", (user_id,))
        row = cur.fetchone()
    return {"id": row[0], "email": row[1], "name": row[2]} if row else None


def _fetch_user_by_email(email: str):
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, email, password_hash, name FROM users WHERE email=%s;", (email,))
        row = cur.fetchone()
    return {"id": row[0], "email": row[1], "password_hash": row[2], "name": row[3]} if row else None


def get_current_user(authorization: str | None = Header(None)):
    """FastAPI dependency: 401 on any missing/malformed/invalid/expired token
    or a since-deleted user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization[len("Bearer "):].strip()
    try:
        user_id = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired session")
    user = _fetch_user(user_id)
    if not user:
        raise HTTPException(401, "Invalid or expired session")
    return user


def signup(email: str, password: str, name: str | None):
    email = email.strip().lower()
    if _fetch_user_by_email(email):
        raise ValueError("An account with this email already exists")
    password_hash = hash_password(password)  # outside any DB connection
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (%s,%s,%s) RETURNING id;",
            (email, password_hash, (name or "").strip() or None),
        )
        user_id = cur.fetchone()[0]
        conn.commit()
    return {"id": user_id, "email": email, "name": (name or "").strip() or None}


def login(email: str, password: str):
    user = _fetch_user_by_email(email.strip().lower())
    if not user or not verify_password(password, user["password_hash"]):
        raise ValueError("Incorrect email or password")
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


# --- password reset ------------------------------------------------------------
def create_reset_token(email: str) -> str | None:
    """Returns a raw token to email, or None (silently) if the email doesn't
    exist or a reset was already sent recently — caller always responds 200
    either way, so this never leaks which branch happened."""
    user = _fetch_user_by_email(email.strip().lower())
    if not user:
        return None
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT 1 FROM password_resets
                WHERE user_id=%s AND created_at > now() - INTERVAL '{RESET_RATE_LIMIT_MINUTES} minutes'
                ORDER BY id DESC LIMIT 1;""",
            (user["id"],),
        )
        if cur.fetchone():
            return None
        cur.execute(
            "UPDATE password_resets SET used_at=now() WHERE user_id=%s AND used_at IS NULL;",
            (user["id"],),
        )
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TTL_MINUTES)
        cur.execute(
            "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (%s,%s,%s);",
            (user["id"], token_hash, expires_at),
        )
        conn.commit()
    return raw_token


def redeem_reset_token(raw_token: str, new_password: str):
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id, user_id FROM password_resets
               WHERE token_hash=%s AND used_at IS NULL AND expires_at > now();""",
            (token_hash,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("This reset link is invalid or has expired")
        reset_id, user_id = row
        password_hash = hash_password(new_password)
        cur.execute("UPDATE users SET password_hash=%s WHERE id=%s;", (password_hash, user_id))
        cur.execute("UPDATE password_resets SET used_at=now() WHERE id=%s;", (reset_id,))
        conn.commit()
