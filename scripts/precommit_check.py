"""Pre-commit check script to prevent committing secrets and unallowed paths."""

import re
import subprocess
import sys
from pathlib import Path

BLOCKED_PATTERNS = [
    (re.compile(r"^\.env(\..+)?$"), "BLOCKED_ENV_FILE"),
    (re.compile(r"^(private|data)(/|\\)"), "BLOCKED_DATA_DIRECTORY"),
]

SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"), "SECRET_PRIVATE_KEY"),
    (
        re.compile(
            r"(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-+/=]{16,}['\"]",
            re.IGNORECASE,
        ),
        "SECRET_KEY_ASSIGNMENT",
    ),
    (re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"), "SECRET_JWT_TOKEN"),
    (re.compile(r"sbp_[a-zA-Z0-9]{30,}"), "SECRET_SUPABASE_TOKEN"),
    (re.compile(r"(?:sk|pk)_(?:live|test)_[0-9a-zA-Z]{20,}"), "SECRET_PAYMENT_KEY"),
]


def is_blocked_path(file_path: Path) -> tuple[bool, str | None]:
    posix_name = file_path.as_posix()
    name = file_path.name

    # Allow .env.example
    if name == ".env.example":
        return False, None

    # Check for .env or .env.* anywhere as filename or path
    if name == ".env" or name.startswith(".env."):
        return True, "BLOCKED_ENV_FILE"

    # Check for private/ or data/ directories in path parts
    parts = file_path.parts
    if any(p in ("private", "data") for p in parts):
        return True, "BLOCKED_DATA_DIRECTORY"

    for pattern, rule_name in BLOCKED_PATTERNS:
        if pattern.search(posix_name):
            return True, rule_name

    return False, None


def check_file_content(file_path: Path) -> list[str]:
    triggered_rules: list[str] = []
    if not file_path.is_file():
        return triggered_rules
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return triggered_rules

    for pattern, rule_name in SECRET_PATTERNS:
        if pattern.search(content):
            triggered_rules.append(rule_name)

    return triggered_rules


def check_paths(file_paths: list[Path]) -> int:
    violations: list[tuple[str, str]] = []

    for file_path in file_paths:
        posix_name = file_path.as_posix()
        blocked, rule = is_blocked_path(file_path)
        if blocked and rule:
            violations.append((posix_name, rule))

        # Check content if file exists
        if file_path.is_file():
            content_rules = check_file_content(file_path)
            for cr in content_rules:
                violations.append((posix_name, cr))

    if violations:
        sys.stderr.write("Commit blocked by pre-commit check.\n")
        for filename, rule_name in violations:
            sys.stderr.write(f"File: {filename} | Rule: {rule_name}\n")
        return 1

    return 0


def get_staged_files() -> list[Path]:
    res = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        return []
    lines = res.stdout.strip().splitlines()
    return [Path(line.strip()) for line in lines if line.strip()]


def main() -> int:
    if len(sys.argv) > 1:
        paths = [Path(arg) for arg in sys.argv[1:]]
    else:
        paths = get_staged_files()

    return check_paths(paths)


if __name__ == "__main__":
    sys.exit(main())
