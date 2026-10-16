"""Known-answer tests for database connection and migration modules."""

from pathlib import Path

import pytest

from backend.app.config.env import Settings
from backend.app.db.connection import (
    DatabaseConnectionError,
    check_connection,
    get_database_url,
)
from backend.app.db.migrate import run_migrations


def test_get_database_url_empty_raises(tmp_path: Path) -> None:
    """Empty or unconfigured DATABASE_URL raises DatabaseConnectionError."""
    env_file = tmp_path / "empty_db.env"
    env_file.write_text("DATABASE_URL=\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)

    with pytest.raises(DatabaseConnectionError, match="DATABASE_URL is not configured"):
        get_database_url(settings)


def test_check_connection_unconfigured_raises(tmp_path: Path) -> None:
    """Connection check with unconfigured DATABASE_URL raises DatabaseConnectionError."""
    env_file = tmp_path / "empty_db.env"
    env_file.write_text("DATABASE_URL=\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)

    with pytest.raises(DatabaseConnectionError, match="DATABASE_URL is not configured"):
        check_connection(settings)


def test_check_connection_invalid_host_raises_sanitized(tmp_path: Path) -> None:
    """Invalid database host fails with sanitized class name and never leaks URL."""
    fake_url = "postgresql://user:secret_password_123@127.0.0.1:59999/nonexistent"
    env_file = tmp_path / "bad_db.env"
    env_file.write_text(f"DATABASE_URL={fake_url}\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)

    with pytest.raises(DatabaseConnectionError) as exc_info:
        check_connection(settings)

    err_text = str(exc_info.value)
    assert "secret_password_123" not in err_text
    assert "connection check failed" in err_text


def test_run_migrations_empty_directory_returns_empty(tmp_path: Path) -> None:
    """Running migrations on an empty directory returns empty list."""
    empty_dir = tmp_path / "empty_migrations"
    empty_dir.mkdir()
    settings = Settings(_env_file=tmp_path / "unused.env")
    assert run_migrations(migrations_dir=empty_dir, settings=settings) == []


def test_run_migrations_missing_dir_raises(tmp_path: Path) -> None:
    """Running migrations on a nonexistent directory raises DatabaseConnectionError."""
    missing_dir = tmp_path / "nonexistent_dir"
    settings = Settings(_env_file=tmp_path / "unused.env")
    with pytest.raises(DatabaseConnectionError, match="Migrations directory not found"):
        run_migrations(migrations_dir=missing_dir, settings=settings)
