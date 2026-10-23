"""Documentation integrity verification script.

Ensures no required symbols, parameters, endpoints, contracts, tables,
decisions, or FR IDs are omitted across the 3 core documentation files:
- project_docs/project.md
- project_docs/tech_stack.md
- project_docs/finance_stack.md

Also verifies that all Markdown pipe tables in the 3 files are well-formed:
- Valid header row and separator row
- Exact column-count match across all rows in each table
- Valid separator syntax (:?-+:?)
"""

import json
from pathlib import Path
import re
import sys
import yaml

from backend.app.config.env import REGISTRY


def check_markdown_tables(file_path: Path) -> list[str]:
    """Parse every table in a markdown file and report malformed rows or column mismatches."""
    if not file_path.is_file():
        return [f"File not found: {file_path}"]

    lines = file_path.read_text(encoding="utf-8").splitlines()
    errors = []
    in_table = False
    table_lines: list[tuple[int, str]] = []

    def validate_current_table(t_lines: list[tuple[int, str]]) -> None:
        if len(t_lines) < 2:
            start_num, line_txt = t_lines[0]
            errors.append(f"{file_path.name}:{start_num}: Table has fewer than 2 rows: '{line_txt}'")
            return

        def split_row(r_text: str) -> list[str]:
            # Protect escaped pipes
            protected = r_text.replace(r"\|", "___ESCAPED_PIPE___").strip()
            if protected.startswith("|"):
                protected = protected[1:]
            if protected.endswith("|"):
                protected = protected[:-1]
            return [c.replace("___ESCAPED_PIPE___", "|").strip() for c in protected.split("|")]

        header_line_num, header_text = t_lines[0]
        header_cols = split_row(header_text)
        col_count = len(header_cols)

        if col_count == 0:
            errors.append(f"{file_path.name}:{header_line_num}: Empty table header")
            return

        sep_line_num, sep_text = t_lines[1]
        sep_cols = split_row(sep_text)
        if len(sep_cols) != col_count:
            errors.append(
                f"{file_path.name}:{sep_line_num}: Separator column count mismatch: "
                f"expected {col_count}, got {len(sep_cols)}"
            )
            return

        for sc in sep_cols:
            if not re.match(r"^:?-+:?$", sc):
                errors.append(f"{file_path.name}:{sep_line_num}: Broken table separator syntax: '{sc}'")
                return

        for row_line_num, row_text in t_lines[2:]:
            row_cols = split_row(row_text)
            if len(row_cols) != col_count:
                errors.append(
                    f"{file_path.name}:{row_line_num}: Row column count mismatch: "
                    f"expected {col_count}, got {len(row_cols)} in '{row_text}'"
                )

    for line_idx, line in enumerate(lines, 1):
        s_line = line.strip()
        if s_line.startswith("|") and s_line.endswith("|"):
            in_table = True
            table_lines.append((line_idx, s_line))
        else:
            if in_table:
                validate_current_table(table_lines)
                table_lines = []
                in_table = False

    if in_table:
        validate_current_table(table_lines)

    return errors


def check_docs() -> dict[str, list[str]]:
    docs_dir = Path("project_docs")
    target_files = [
        docs_dir / "project.md",
        docs_dir / "tech_stack.md",
        docs_dir / "finance_stack.md",
    ]
    for tf in target_files:
        if not tf.is_file():
            print(f"Error: Required documentation file missing: {tf}")
            return {"missing_files": [str(tf)]}

    combined_text = "\n".join(tf.read_text(encoding="utf-8") for tf in target_files)
    missing: dict[str, list[str]] = {}

    # 0. Table validation across all 3 files
    table_errors = []
    for tf in target_files:
        errs = check_markdown_tables(tf)
        if errs:
            table_errors.extend(errs)
    if table_errors:
        missing["table_syntax_errors"] = table_errors

    # 1. Environment variables
    missing_envs = []
    for env in REGISTRY:
        if env.name not in combined_text:
            missing_envs.append(env.name)
    if missing_envs:
        missing["environment_variables"] = missing_envs

    # 2. Endpoints
    openapi_file = Path("docs/openapi.json")
    if openapi_file.is_file():
        openapi_data = json.loads(openapi_file.read_text(encoding="utf-8"))
        missing_endpoints = []
        for path in openapi_data.get("paths", {}):
            if path not in combined_text:
                missing_endpoints.append(path)
        if missing_endpoints:
            missing["endpoints"] = missing_endpoints

    # 3. Decisions numbers
    decisions_file = Path("DECISIONS.md")
    if decisions_file.is_file():
        dec_text = decisions_file.read_text(encoding="utf-8")
        dec_numbers = re.findall(r"D-\d+", dec_text)
        dec_numbers = sorted(list(set(dec_numbers)), key=lambda x: int(x.split("-")[1]))
        missing_decisions = []
        for d in dec_numbers:
            if d not in combined_text:
                missing_decisions.append(d)
        if missing_decisions:
            missing["decisions"] = missing_decisions

    # 4. Config parameters & thresholds
    missing_params = []
    params_file = Path("config/parameters.yaml")
    if params_file.is_file():
        pdata = yaml.safe_load(params_file.read_text(encoding="utf-8"))
        for p in pdata.get("parameters", {}):
            if p not in combined_text:
                missing_params.append(p)
    thresh_file = Path("config/thresholds.yaml")
    if thresh_file.is_file():
        tdata = yaml.safe_load(thresh_file.read_text(encoding="utf-8"))
        for t in tdata:
            if t not in combined_text:
                missing_params.append(t)
    if missing_params:
        missing["config_parameters"] = missing_params

    # 5. Database tables
    mig_file = Path("migrations/001_initial_schema.sql")
    if mig_file.is_file():
        mig_text = mig_file.read_text(encoding="utf-8")
        tables = [
            t.replace("public.", "")
            for t in re.findall(
                r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+([a-zA-Z0-9_.]+)", mig_text, re.I
            )
        ]
        missing_tables = []
        for t in tables:
            if t not in combined_text:
                missing_tables.append(t)
        if missing_tables:
            missing["database_tables"] = missing_tables

    # 6. Contract names
    contracts_dir = Path("docs/contracts")
    if contracts_dir.is_dir():
        contracts = [f.stem for f in contracts_dir.glob("*.json")]
        missing_contracts = []
        for c in contracts:
            if c not in combined_text:
                missing_contracts.append(c)
        if missing_contracts:
            missing["contracts"] = missing_contracts

    # 7. FR IDs
    fr_ids = [
        "FR-CFG",
        "FR-AUTH",
        "FR-ENT",
        "FR-QUO",
        "FR-PAY",
        "FR-LLM",
        "FR-MKT",
        "FR-F1",
        "FR-FIL",
        "FR-F2",
        "FR-F3",
        "FR-AGT",
        "FR-CAC",
        "FR-OBS",
        "FR-UI",
    ]
    missing_frs = []
    for fr in fr_ids:
        if fr not in combined_text:
            missing_frs.append(fr)
    if missing_frs:
        missing["fr_ids"] = missing_frs

    return missing


def main() -> int:
    missing = check_docs()
    if not missing:
        print("PASS: All required symbols, endpoints, parameters, tables, and IDs present in documentation.")
        print("PASS: All Markdown pipe tables verified.")
        return 0

    print("FAIL: Documentation integrity check failed:")
    for category, items in missing.items():
        print(f"  {category} ({len(items)}): {', '.join(items)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
