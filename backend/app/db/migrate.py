"""Migration runner executing additive SQL migrations against PostgreSQL."""

from pathlib import Path
from typing import Optional

import psycopg

from backend.app.config.env import Settings, get_repo_root
from backend.app.db.connection import DatabaseConnectionError, get_database_url


def run_migrations(
    migrations_dir: Optional[Path] = None,
    settings: Optional[Settings] = None,
) -> list[str]:
    """Execute SQL migrations from the migrations directory.

    Migrations are applied in alphabetical filename order.
    Returns the list of applied migration filenames.
    Raises DatabaseConnectionError if connection or execution fails.
    """
    if migrations_dir is None:
        migrations_dir = get_repo_root() / "migrations"

    if not migrations_dir.is_dir():
        raise DatabaseConnectionError(f"Migrations directory not found: {migrations_dir}")

    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        return []

    url = get_database_url(settings)

    applied: list[str] = []
    try:
        with psycopg.connect(url, connect_timeout=15, autocommit=True) as conn:
            with conn.cursor() as cur:
                for sql_path in migration_files:
                    sql_content = sql_path.read_text(encoding="utf-8")
                    cur.execute(sql_content)
                    applied.append(sql_path.name)
    except Exception as exc:
        raise DatabaseConnectionError(
            f"{exc.__class__.__name__}: failed applying migrations"
        ) from None

    return applied
