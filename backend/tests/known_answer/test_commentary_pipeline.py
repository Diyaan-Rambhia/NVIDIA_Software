"""Known-answer tests for Feature 2 Management Commentary and guidance auditing."""

import pytest

from backend.app.contracts.filings import FilingMetric
from backend.app.features.f2_filings.commentary_extractor import (
    audit_guidance_against_metrics,
    extract_commentary_items,
)
from backend.app.features.f2_filings.quote_verifier import verify_quote


SAMPLE_TRANSCRIPT = (
    "Good morning everyone and welcome to the earnings call. "
    "We expect full year revenue growth of 14.5% driven by strong enterprise digital transformation. "
    "However, operating margin compressed by 120 basis points due to wage hikes and higher travel costs. "
    "Revenue growth was led by BFSI and manufacturing verticals across North America. "
    "Capital expenditure planned for next year stands at Rs. 2500 crore for cloud infrastructure. "
    "We continue to navigate headwinds from global macro uncertainty and cautious client spending."
)


def test_extract_commentary_items_and_offsets():
    """Verify that extracted commentary segments match exact character offsets verbatim."""
    items = extract_commentary_items(SAMPLE_TRANSCRIPT)
    assert len(items) >= 4

    # Every item must match source text verbatim at its slice
    for item in items:
        assert verify_quote(SAMPLE_TRANSCRIPT, item.quote, item.start, item.end)

    # Check guidance section
    guidance_items = [it for it in items if it.section == "guidance"]
    assert len(guidance_items) >= 1
    assert "14.5%" in guidance_items[0].quote
    assert guidance_items[0].target_value == 14.5

    # Check margin commentary section
    margin_items = [it for it in items if it.section == "margin_commentary"]
    assert len(margin_items) >= 1
    assert "operating margin compressed" in margin_items[0].quote.lower()
    assert margin_items[0].tone == "cautious"

    # Check capex commentary section
    capex_items = [it for it in items if it.section == "capex_commentary"]
    assert len(capex_items) >= 1
    assert "2500" in capex_items[0].quote


def test_audit_guidance_divergence_flagged():
    """Verify guidance target is flagged when filed metrics show significant divergence."""
    items = extract_commentary_items(SAMPLE_TRANSCRIPT)

    # Filed revenue growth is only 5.2% vs 14.5% guided
    filed_metrics = [
        FilingMetric(
            company="INFY",
            symbol="INFY",
            fiscal_period="Q1 FY27",
            period_end_date="2026-06-30",
            basis="consolidated",
            metric="revenue from operations",
            value=5.2,
            unit="percent",
            source_filing_reference="XBRL_RESULTS",
            derived=True,
            retrieval_time="recent",
        )
    ]

    inconsistencies = audit_guidance_against_metrics(items, filed_metrics, SAMPLE_TRANSCRIPT)
    assert len(inconsistencies) >= 1

    inc = inconsistencies[0]
    assert inc.rule_id == "R0_GUIDANCE_DIVERGENCE"
    assert inc.verdict == "confirm"
    assert inc.stated_value == 14.5
    assert inc.filed_value == 5.2
    assert inc.difference_value == 9.3
    assert verify_quote(SAMPLE_TRANSCRIPT, inc.claim_quote, inc.quote_start, inc.quote_end)


def test_empty_or_whitespace_transcript():
    """Verify empty transcript handling."""
    assert extract_commentary_items("") == []
    assert extract_commentary_items("   \n\t  ") == []
