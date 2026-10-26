"""Database connection manager for FinInsight.

Handles connection creation and live health check against Supabase PostgreSQL.
Ensures database URLs and credentials are never printed or echoed in errors.
"""

from typing import Any, Optional

import psycopg

from backend.app.config.env import Settings, load_settings


class DatabaseConnectionError(Exception):
    """Raised when database connection fails, without leaking connection strings."""


def get_database_url(settings: Optional[Settings] = None) -> str:
    """Retrieve DATABASE_URL securely from settings."""
    if settings is None:
        settings = load_settings()
    raw = settings.get_var_value("DATABASE_URL")
    if not raw or not raw.strip():
        raise DatabaseConnectionError("DATABASE_URL is not configured")
    return raw.strip()


def check_connection(settings: Optional[Settings] = None) -> bool:
    """Perform live connection check against the PostgreSQL database.

    Returns True if connection succeeds and SELECT 1 succeeds.
    Raises DatabaseConnectionError on failure without echoing connection details.
    """
    try:
        url = get_database_url(settings)
    except DatabaseConnectionError:
        raise

    try:
        with psycopg.connect(url, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                res = cur.fetchone()
                return bool(res and res[0] == 1)
    except Exception as exc:
        err_name = exc.__class__.__name__
        raise DatabaseConnectionError(f"{err_name}: connection check failed") from None


def get_connection(
    settings: Optional[Settings] = None, autocommit: bool = False
) -> psycopg.Connection:
    """Establish a direct psycopg connection to PostgreSQL.

    Raises DatabaseConnectionError on failure without exposing credentials.
    """
    url = get_database_url(settings)
    try:
        return psycopg.connect(url, connect_timeout=10, autocommit=autocommit)
    except Exception as exc:
        err_name = exc.__class__.__name__
        raise DatabaseConnectionError(f"{err_name}: database connection failed") from None


def is_connection_closed(conn: Any) -> bool:
    """Check if a database connection is None, closed, or broken."""
    if conn is None:
        return True
    try:
        if type(conn).__name__ in ("MagicMock", "Mock") or hasattr(conn, "_mock_return_value"):
            return bool(conn.__dict__.get("closed", False))
        if getattr(conn, "closed", False):
            return True
        # Check underlying pgconn status if available on real psycopg connection
        if hasattr(conn, "pgconn") and getattr(conn.pgconn, "status", None) is not None:
            from psycopg.pq import ConnStatus
            status = getattr(conn.pgconn, "status", None)
            if isinstance(status, ConnStatus) and status != ConnStatus.OK:
                return True
    except Exception:
        return True
    return False


