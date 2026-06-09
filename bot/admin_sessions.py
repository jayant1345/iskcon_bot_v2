# bot/admin_sessions.py
# =====================
# Tracks active admin sessions in PostgreSQL.
# Works correctly across multiple gunicorn workers.

import secrets
import psycopg2
from datetime import datetime, timezone
from config.settings import Config

SESSION_COOKIE   = "admin_token"
SESSION_TIMEOUT  = 30  # minutes of inactivity before session expires


def _conn():
    return psycopg2.connect(Config.DATABASE_URL)


def init_table():
    """Create admin_sessions table if it does not exist."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    id          SERIAL PRIMARY KEY,
                    token       TEXT UNIQUE NOT NULL,
                    ip_address  TEXT,
                    user_agent  TEXT,
                    login_at    TIMESTAMPTZ DEFAULT NOW(),
                    last_seen   TIMESTAMPTZ DEFAULT NOW(),
                    is_active   BOOLEAN DEFAULT TRUE
                );
            """)
        conn.commit()


def create_session(ip: str, user_agent: str) -> str:
    """Inserts a new active session. Returns the session token."""
    token = secrets.token_urlsafe(32)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO admin_sessions (token, ip_address, user_agent)
                VALUES (%s, %s, %s);
            """, (token, ip[:100], (user_agent or "")[:200]))
        conn.commit()
    return token


def refresh_session(token: str) -> bool:
    """Updates last_seen. Returns True if session is still active."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE admin_sessions
                SET last_seen = NOW()
                WHERE token = %s
                  AND is_active = TRUE
                  AND last_seen > NOW() - INTERVAL '%s minutes'
                RETURNING id;
            """ , (token, SESSION_TIMEOUT))
            found = cur.fetchone() is not None
        conn.commit()
    return found


def end_session(token: str):
    """Marks a session as inactive (logout)."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE admin_sessions SET is_active = FALSE WHERE token = %s;",
                (token,)
            )
        conn.commit()


def get_active_sessions() -> list:
    """Returns all sessions active within the last SESSION_TIMEOUT minutes."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ip_address, user_agent, login_at, last_seen
                FROM admin_sessions
                WHERE is_active = TRUE
                  AND last_seen > NOW() - INTERVAL '%s minutes'
                ORDER BY last_seen DESC;
            """ % SESSION_TIMEOUT)
            rows = cur.fetchall()

    return [
        {
            "ip":         row[0],
            "user_agent": row[1],
            "login_at":   row[2].strftime("%Y-%m-%d %H:%M:%S UTC") if row[2] else "",
            "last_seen":  row[3].strftime("%Y-%m-%d %H:%M:%S UTC") if row[3] else "",
        }
        for row in rows
    ]


def get_recent_logins(limit: int = 20) -> list:
    """Returns the most recent login records (active + inactive) for audit."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ip_address, user_agent, login_at, last_seen, is_active
                FROM admin_sessions
                ORDER BY login_at DESC
                LIMIT %s;
            """, (limit,))
            rows = cur.fetchall()

    return [
        {
            "ip":         row[0],
            "user_agent": row[1],
            "login_at":   row[2].strftime("%Y-%m-%d %H:%M:%S UTC") if row[2] else "",
            "last_seen":  row[3].strftime("%Y-%m-%d %H:%M:%S UTC") if row[3] else "",
            "is_active":  row[4],
        }
        for row in rows
    ]
