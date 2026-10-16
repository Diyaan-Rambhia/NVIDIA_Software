"""Test ensuring README environment variables match registry exactly."""

from pathlib import Path

from backend.app.config.env import get_repo_root
from scripts.generate_readme_env import (
    ENV_VARS_END,
    ENV_VARS_START,
    generate_env_markdown,
)


def test_readme_environment_variables_match_registry() -> None:
    """Fail if the environment variable list in README differs from registry."""
    readme_path = get_repo_root() / "README.md"
    assert readme_path.exists(), f"README.md not found at {readme_path}"

    content = readme_path.read_text(encoding="utf-8")
    assert ENV_VARS_START in content, f"Missing start marker {ENV_VARS_START} in README.md"
    assert ENV_VARS_END in content, f"Missing end marker {ENV_VARS_END} in README.md"

    start_idx = content.index(ENV_VARS_START)
    end_idx = content.index(ENV_VARS_END) + len(ENV_VARS_END)
    readme_section = content[start_idx:end_idx]

    expected_section = generate_env_markdown()
    assert readme_section == expected_section, (
        "README.md environment variables section does not match registry.\n"
        "Run `python scripts/generate_readme_env.py` to synchronize."
    )
