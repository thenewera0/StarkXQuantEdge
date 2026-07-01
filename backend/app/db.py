"""Postgres (Supabase) connection helper for Phase 3 persistence.

Design goals:
  * Persistence is OPTIONAL. If DATABASE_URL is unset or still has the [YOUR-PASSWORD]
    placeholder, `enabled()` is False and every write becomes a no-op — the API keeps working.
  * Server-side writes use a direct Postgres connection (psycopg), which owns the schema and
    bypasses RLS. Supabase requires SSL, so we ensure sslmode=require.
"""

from __future__ import annotations

from contextlib import contextmanager

import psycopg

from .config import settings

_PLACEHOLDER = "[YOUR-PASSWORD]"


def enabled() -> bool:
    """True only when a real connection string is configured (no placeholder)."""
    url = settings.database_url
    return bool(url) and _PLACEHOLDER not in url


def _dsn() -> str:
    url = settings.database_url
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


@contextmanager
def get_conn():
    """Short-lived connection context. Raises if persistence is not configured."""
    if not enabled():
        raise RuntimeError("DATABASE_URL not configured (or still a placeholder)")
    conn = psycopg.connect(_dsn(), connect_timeout=8)
    try:
        yield conn
    finally:
        conn.close()


def ping() -> bool:
    """Return True if a trivial query succeeds. Never raises."""
    if not enabled():
        return False
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("select 1")
            return cur.fetchone()[0] == 1
    except Exception:
        return False
