"""Generate environment variables markdown section in README.md from registry."""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.config.env import REGISTRY_BY_GROUP, REGISTRY_BY_NAME

ENV_VARS_START = "<!-- ENV_VARS_START -->"
ENV_VARS_END = "<!-- ENV_VARS_END -->"


def generate_env_markdown() -> str:
    """Generate markdown representation of environment variables grouped by runtime group."""
    # Verify every registered variable is categorized
    all_grouped: set[str] = set()
    for g in [
        "core",
        "supabase",
        "llm",
        "search",
        "budget",
        "accounts_seed",
        "payments",
        "oauth",
        "market_data",
        "filings",
        "optional",
    ]:
        all_grouped.update(v.name for v in REGISTRY_BY_GROUP.get(g, []))
    all_registry = set(REGISTRY_BY_NAME.keys())
    assert all_grouped == all_registry, (
        f"Registry group mismatch: missing in groups {all_registry - all_grouped}"
    )

    lines: list[str] = [ENV_VARS_START]

    # 1. Always needed on a host (core)
    lines.append("#### Always Needed on a Host")
    for var in REGISTRY_BY_GROUP.get("core", []):
        lines.append(f"- `{var.name}`")
    lines.append("")

    # 2. Needed per group (supabase, llm, search, budget)
    lines.append("#### Needed per Group")
    group_titles = [
        ("supabase", "Supabase"),
        ("llm", "LLM"),
        ("search", "Search"),
        ("budget", "Budget"),
    ]
    for grp_key, grp_title in group_titles:
        lines.append(f"##### {grp_title}")
        for var in REGISTRY_BY_GROUP.get(grp_key, []):
            lines.append(f"- `{var.name}`")
        lines.append("")

    # 3. Seed-script only (accounts_seed)
    lines.append("#### Seed-Script Only")
    for var in REGISTRY_BY_GROUP.get("accounts_seed", []):
        lines.append(f"- `{var.name}`")
    lines.append("")

    # 4. Not used yet (payments, oauth, market_data, filings, optional)
    lines.append("#### Not Used Yet")
    unused_titles = [
        ("payments", "Payments"),
        ("oauth", "OAuth"),
        ("market_data", "Market Data"),
        ("filings", "Filings"),
        ("optional", "Optional"),
    ]
    for grp_key, grp_title in unused_titles:
        lines.append(f"##### {grp_title}")
        for var in REGISTRY_BY_GROUP.get(grp_key, []):
            lines.append(f"- `{var.name}`")
        lines.append("")

    # Strip trailing empty line before end marker
    if lines[-1] == "":
        lines.pop()
    lines.append(ENV_VARS_END)

    return "\n".join(lines)


def update_readme(readme_path: Path | None = None) -> None:
    """Update README.md with generated environment variables block."""
    target_path = readme_path or (REPO_ROOT / "README.md")
    content = target_path.read_text(encoding="utf-8")
    generated = generate_env_markdown()

    if ENV_VARS_START in content and ENV_VARS_END in content:
        before = content.split(ENV_VARS_START)[0]
        after = content.split(ENV_VARS_END)[1]
        new_content = before + generated + after
    else:
        marker = "Fill in required operational variables in `.env` (kept strictly gitignored).\n"
        if marker in content:
            new_content = content.replace(
                marker,
                marker + "\n### Environment Variables\n\n" + generated + "\n",
            )
        else:
            new_content = content + "\n\n### Environment Variables\n\n" + generated + "\n"

    target_path.write_text(new_content, encoding="utf-8")


if __name__ == "__main__":
    update_readme()
    print("README.md environment variables successfully updated from registry.")
