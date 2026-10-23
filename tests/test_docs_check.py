"""Tests for documentation integrity and table syntax verification."""

from pathlib import Path
from scripts.docs_check import check_docs, check_markdown_tables


def test_documentation_integrity() -> None:
    """Ensure all required symbols, endpoints, parameters, tables, and IDs are present in docs."""
    missing = check_docs()
    assert not missing, f"Documentation integrity check failed: {missing}"


def test_markdown_table_validator(tmp_path: Path) -> None:
    """Ensure check_markdown_tables correctly flags broken tables."""
    # 1. Valid table
    valid_file = tmp_path / "valid.md"
    valid_file.write_text(
        "| Col1 | Col2 |\n|---|---|\n| val1 | val2 |\n",
        encoding="utf-8",
    )
    assert not check_markdown_tables(valid_file)

    # 2. Column count mismatch
    broken_cols = tmp_path / "broken_cols.md"
    broken_cols.write_text(
        "| Col1 | Col2 |\n|---|---|\n| val1 | val2 | extra |\n",
        encoding="utf-8",
    )
    errors = check_markdown_tables(broken_cols)
    assert len(errors) == 1
    assert "mismatch" in errors[0]

    # 3. Broken separator row
    broken_sep = tmp_path / "broken_sep.md"
    broken_sep.write_text(
        "| Col1 | Col2 |\n|---|not_sep|\n| val1 | val2 |\n",
        encoding="utf-8",
    )
    errors = check_markdown_tables(broken_sep)
    assert len(errors) == 1
    assert "separator" in errors[0]
