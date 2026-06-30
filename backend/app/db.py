"""Postgres connection helper.

Reads DATABASE_URL from settings. The app stores it in SQLAlchemy-style
(`postgresql+psycopg://…`); psycopg itself wants the plain `postgresql://`
scheme, so we normalise here.

We connect through Supabase's transaction pooler (pgBouncer), which doesn't
play well with server-side prepared statements — so `prepare_threshold=None`
disables psycopg's auto-prepare.
"""
import psycopg
from psycopg_pool import ConnectionPool

from .config import settings

_pool = None


def conninfo() -> str:
    url = settings.database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set (backend/.env)")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def connect():
    """One-off connection (used by ETL + the one-time graph build)."""
    return psycopg.connect(conninfo(), prepare_threshold=None, connect_timeout=15)


def get_pool():
    """Shared connection pool for per-request queries — avoids paying TLS +
    pooler auth on every request. pgBouncer transaction mode needs prepared
    statements off."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo(), min_size=1, max_size=4, timeout=15,
            kwargs={"prepare_threshold": None}, open=True,
        )
    return _pool


def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
