"""Test that demo_data contains exclusively derived outputs and no raw files or placeholders."""

import json
from pathlib import Path
from backend.app.llm.placeholder import PLACEHOLDER_MARKER


def test_demo_data_contains_only_derived_outputs_and_no_placeholders() -> None:
    """demo_data directory must exist, contain only derived JSON files, zero raw files, zero placeholders."""
    demo_dir = Path("demo_data")
    assert demo_dir.is_dir(), "demo_data/ must exist as a committed directory in the repo"

    disallowed_extensions = {".csv", ".xml", ".html", ".zip", ".tar", ".gz", ".parquet"}
    raw_keywords = ["raw", "yfinance", "trade_log", "xbrl_raw"]

    files = list(demo_dir.iterdir())
    assert len(files) > 0, "demo_data/ must not be empty"

    for file_path in files:
        assert file_path.is_file(), f"demo_data/ should only contain files: {file_path}"
        assert file_path.suffix.lower() == ".json", f"Only derived JSON files allowed in demo_data/: {file_path.name}"

        # Ensure no disallowed extensions or raw naming
        for ext in disallowed_extensions:
            assert not file_path.name.lower().endswith(ext), f"Raw file format detected in demo_data/: {file_path.name}"

        for kw in raw_keywords:
            assert kw not in file_path.name.lower(), f"Raw file name pattern detected in demo_data/: {file_path.name}"

        content = file_path.read_text(encoding="utf-8")

        # Zero placeholder text or markers
        assert PLACEHOLDER_MARKER not in content, f"Placeholder marker found in {file_path.name}"
        assert "placeholder template" not in content.lower(), f"Placeholder template text found in {file_path.name}"

        # Verify valid JSON
        parsed = json.loads(content)
        assert isinstance(parsed, (dict, list)), f"File {file_path.name} must be valid JSON object or array"
