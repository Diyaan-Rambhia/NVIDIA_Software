"""Unit tests for Feature 2 XBRL extraction and consistency rule evaluation."""

import json
from pathlib import Path

from backend.app.features.f2_filings.xbrl_parser import (
    TARGET_SYMBOLS,
    evaluate_company_rules,
    parse_xbrl_file,
)


def test_target_symbols_list() -> None:
    """Verify target non-financial company symbols."""
    assert TARGET_SYMBOLS == ["INFY", "ITC", "MARUTI", "RELIANCE", "TATASTEEL"]


def test_parse_individual_xbrl_files() -> None:
    """Verify parsing of real stored XBRL XML files."""
    for sym in TARGET_SYMBOLS:
        xml_path = Path("data") / "xbrl" / f"{sym}.xml"
        assert xml_path.exists(), f"Missing XBRL file {xml_path}"
        parsed = parse_xbrl_file(xml_path)

        assert parsed["symbol"] == sym
        assert parsed["company"]
        metrics = parsed["metrics"]
        assert "RevenueFromOperations" in metrics
        assert float(metrics["RevenueFromOperations"]["value"]) > 0.0
        assert "ProfitBeforeTax" in metrics


def test_evaluate_company_rules() -> None:
    """Verify consistency rules evaluation against parsed company metrics."""
    xml_path = Path("data") / "xbrl" / "INFY.xml"
    parsed = parse_xbrl_file(xml_path)
    rule_results = evaluate_company_rules(parsed)

    assert len(rule_results) == 8
    rule_ids = [r.rule_id for r in rule_results]
    assert rule_ids == ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"]
    # R0 stated number should pass for exact match
    assert rule_results[0].status == "pass"


def test_precomputed_f2_demo_file_exists() -> None:
    """Ensure data/f2_filings_demo.json exists and contains all 5 companies."""
    fpath = Path("data") / "f2_filings_demo.json"
    assert fpath.exists(), "data/f2_filings_demo.json must exist"
    data = json.loads(fpath.read_text(encoding="utf-8"))

    assert data["source_label"] == "unofficial source, demo only"
    comps = data["companies_evaluated"]
    assert len(comps) == 5
    symbols = [c["symbol"] for c in comps]
    for sym in TARGET_SYMBOLS:
        assert sym in symbols
