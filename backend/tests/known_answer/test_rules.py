"""Known-answer tests for consistency rule engine R0-R7 per PROGRESS.md A2.13."""

import pytest

from backend.app.config.loader import ParameterError
from backend.app.contracts.filings import Claim, FilingMetric
from backend.app.features.f2_filings.rules import (
    evaluate_all_rules,
    evaluate_r0_stated_number,
    evaluate_r1_direction,
    evaluate_r2_magnitude,
    evaluate_r3_trend,
    evaluate_r4_profitability,
    evaluate_r5_cash_quality,
    evaluate_r6_working_capital,
    evaluate_r7_understatement,
    validate_alignment,
)


@pytest.fixture
def base_metric() -> FilingMetric:
    return FilingMetric(
        company="Reliance Industries Limited",
        symbol="RELIANCE",
        fiscal_period="Q3 FY25",
        period_end_date="2024-12-31",
        basis="consolidated",
        metric="revenue",
        value=10.0,
        unit="INR_Crore",
        source_filing_reference="NSE_XBRL_Q3FY25",
        derived=False,
        retrieval_time="2025-01-20T10:00:00Z",
    )


@pytest.fixture
def base_claim() -> Claim:
    return Claim(
        metric="revenue",
        descriptor="strong",
        direction="grew",
        quote="revenue grew 10% YoY",
        start=0,
        end=20,
        period="Q3 FY25",
        basis="reported",
    )


# ---------------------------------------------------------------------------
# Alignment & Mismatch Tests
# ---------------------------------------------------------------------------


def test_period_mismatch_raises(base_claim: Claim, base_metric: FilingMetric) -> None:
    """Mismatched fiscal period between claim and metric must raise ParameterError."""
    mismatched_claim = base_claim.model_copy(update={"period": "Q2 FY25"})
    with pytest.raises(ParameterError) as exc:
        validate_alignment(mismatched_claim, base_metric)
    assert exc.value.field == "period"
    assert "Fiscal period mismatch" in exc.value.reason

    # Evaluator also raises
    with pytest.raises(ParameterError):
        evaluate_r0_stated_number(mismatched_claim, base_metric, stated_value=10.0)


def test_unit_mismatch_raises(base_claim: Claim, base_metric: FilingMetric) -> None:
    """Explicit unit mismatch between claim and metric must raise ParameterError."""
    with pytest.raises(ParameterError) as exc:
        validate_alignment(base_claim, base_metric, claimed_unit="INR_Lakh")
    assert exc.value.field == "unit"
    assert "Unit mismatch" in exc.value.reason


def test_basis_mismatch_raises(base_claim: Claim, base_metric: FilingMetric) -> None:
    """Reporting basis mismatch (standalone vs consolidated) must raise ParameterError."""
    with pytest.raises(ParameterError) as exc:
        validate_alignment(base_claim, base_metric, claim_metric_basis="standalone")
    assert exc.value.field == "basis"
    assert "Basis mismatch" in exc.value.reason


def test_adjusted_figure_guard(base_claim: Claim, base_metric: FilingMetric) -> None:
    """Adjusted or constant-currency claim returns not_applicable under FR-F2-005."""
    adj_claim = base_claim.model_copy(update={"basis": "adjusted"})
    res = evaluate_r0_stated_number(adj_claim, base_metric, stated_value=12.0)
    assert res.status == "not_applicable"
    assert "Adjusted" in (res.reason or "")

    cc_claim = base_claim.model_copy(update={"basis": "constant-currency"})
    res_cc = evaluate_r1_direction(cc_claim, base_metric, filing_change=-2.0)
    assert res_cc.status == "not_applicable"


# ---------------------------------------------------------------------------
# Rule R0: Stated Number
# ---------------------------------------------------------------------------


def test_r0_stated_number_pass(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R0 passes when stated figure is within tolerance of filed figure."""
    # Stated 10.2% vs filed 10.0%, tolerance 0.5 pp -> diff 0.2 <= 0.5
    res = evaluate_r0_stated_number(base_claim, base_metric, stated_value=10.2, tolerance_pp=0.5)
    assert res.rule_id == "R0"
    assert res.status == "pass"
    assert res.severity == "none"


def test_r0_stated_number_flag(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R0 flags when stated figure differs from filed figure by more than tolerance."""
    # Stated 12.0% vs filed 10.0%, diff 2.0 > 0.5 pp
    res = evaluate_r0_stated_number(base_claim, base_metric, stated_value=12.0, tolerance_pp=0.5)
    assert res.rule_id == "R0"
    assert res.status == "flag"
    assert res.severity == "high"


def test_r0_stated_number_not_applicable(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R0 returns not_applicable when no stated number is provided."""
    res = evaluate_r0_stated_number(base_claim, base_metric, stated_value=None)
    assert res.rule_id == "R0"
    assert res.status == "not_applicable"


# ---------------------------------------------------------------------------
# Rule R1: Direction
# ---------------------------------------------------------------------------


def test_r1_direction_pass(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R1 passes when claimed growth is accompanied by positive filed change."""
    res = evaluate_r1_direction(base_claim, base_metric, filing_change=5.2)
    assert res.rule_id == "R1"
    assert res.status == "pass"


def test_r1_direction_flag(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R1 flags when claimed growth is accompanied by flat or negative change."""
    # Claimed "grew" but filing change was -1.5%
    res = evaluate_r1_direction(base_claim, base_metric, filing_change=-1.5)
    assert res.rule_id == "R1"
    assert res.status == "flag"
    assert res.severity == "high"

    # Claimed "declined" but filing change was +2.0%
    dec_claim = base_claim.model_copy(update={"direction": "declined"})
    res_dec = evaluate_r1_direction(dec_claim, base_metric, filing_change=2.0)
    assert res_dec.status == "flag"
    assert res_dec.severity == "high"


def test_r1_direction_not_applicable(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R1 returns not_applicable when direction is neutral or filing change is missing."""
    neutral_claim = base_claim.model_copy(update={"direction": "stable"})
    res = evaluate_r1_direction(neutral_claim, base_metric, filing_change=1.0)
    assert res.rule_id == "R1"
    assert res.status == "not_applicable"

    res_missing = evaluate_r1_direction(base_claim, base_metric, filing_change=None)
    assert res_missing.status == "not_applicable"


# ---------------------------------------------------------------------------
# Rule R2: Magnitude
# ---------------------------------------------------------------------------


def test_r2_magnitude_pass(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R2 passes when growth meets or exceeds strong growth threshold."""
    # "strong" descriptor with growth 0.12 >= strong_threshold 0.08
    res = evaluate_r2_magnitude(base_claim, base_metric, growth=0.12, strong_threshold=0.08)
    assert res.rule_id == "R2"
    assert res.status == "pass"


def test_r2_magnitude_flag(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R2 flags when growth is below strong growth threshold."""
    # "strong" descriptor with growth 0.03 < 0.08
    res = evaluate_r2_magnitude(base_claim, base_metric, growth=0.03, strong_threshold=0.08)
    assert res.rule_id == "R2"
    assert res.status == "flag"
    assert res.severity == "medium"


def test_r2_magnitude_flag_with_sector_provisional_label(
    base_claim: Claim, base_metric: FilingMetric
) -> None:
    """R2 flag using sector threshold includes 'provisional threshold' in output."""
    res = evaluate_r2_magnitude(
        base_claim,
        base_metric,
        growth=0.03,
        sector="it_services",
        sector_thresholds={"it_services": 0.08},
    )
    assert res.rule_id == "R2"
    assert res.status == "flag"
    assert res.evidence["threshold_label"] == "provisional threshold"
    assert "provisional threshold" in (res.reason or "")


def test_r2_magnitude_not_applicable(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R2 returns not_applicable when descriptor is not a strong word."""
    modest_claim = base_claim.model_copy(update={"descriptor": "modest"})
    res = evaluate_r2_magnitude(modest_claim, base_metric, growth=0.04, strong_threshold=0.08)
    assert res.rule_id == "R2"
    assert res.status == "not_applicable"


def test_r2_magnitude_pending_threshold(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R2 returns not_applicable with reason 'threshold pending' when threshold is unconfigured."""
    # Unlisted sector "aerospace"
    res = evaluate_r2_magnitude(
        base_claim,
        base_metric,
        growth=0.05,
        sector="aerospace",
        sector_thresholds={"fmcg": 0.06},
    )
    assert res.rule_id == "R2"
    assert res.status == "not_applicable"
    assert res.reason == "threshold pending"


# ---------------------------------------------------------------------------
# Rule R3: Trend
# ---------------------------------------------------------------------------


def test_r3_trend_pass(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R3 passes when growth accelerated compared to prior period."""
    trend_claim = base_claim.model_copy(update={"descriptor": "accelerating"})
    res = evaluate_r3_trend(trend_claim, base_metric, current_growth=0.10, prior_growth=0.07)
    assert res.rule_id == "R3"
    assert res.status == "pass"


def test_r3_trend_flag(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R3 flags when growth decelerated despite claim of accelerating momentum."""
    trend_claim = base_claim.model_copy(update={"descriptor": "accelerating"})
    res = evaluate_r3_trend(trend_claim, base_metric, current_growth=0.05, prior_growth=0.08)
    assert res.rule_id == "R3"
    assert res.status == "flag"
    assert res.severity == "medium"


def test_r3_trend_not_applicable(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R3 returns not_applicable when descriptor is not a trend word or prior growth is missing."""
    non_trend_claim = base_claim.model_copy(update={"descriptor": "steady"})
    res = evaluate_r3_trend(non_trend_claim, base_metric, current_growth=0.08, prior_growth=0.05)
    assert res.rule_id == "R3"
    assert res.status == "not_applicable"

    trend_claim = base_claim.model_copy(update={"descriptor": "accelerating"})
    res_missing = evaluate_r3_trend(
        trend_claim, base_metric, current_growth=0.08, prior_growth=None
    )
    assert res_missing.status == "not_applicable"


# ---------------------------------------------------------------------------
# Rule R4: Profitability / Margin
# ---------------------------------------------------------------------------


def test_r4_profitability_pass(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R4 passes when margin expanded or change is within tolerance."""
    margin_claim = base_claim.model_copy(
        update={"descriptor": "margin expansion", "metric": "ebitda_margin"}
    )
    res = evaluate_r4_profitability(
        margin_claim, base_metric, margin_change=0.0050, margin_tolerance_bps=20
    )
    assert res.rule_id == "R4"
    assert res.status == "pass"


def test_r4_profitability_flag(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R4 flags when margin declined beyond tolerance."""
    margin_claim = base_claim.model_copy(
        update={"descriptor": "margin expansion", "metric": "ebitda_margin"}
    )
    # Declined by 50 bps (-0.0050) exceeding tolerance of 20 bps (-0.0020)
    res = evaluate_r4_profitability(
        margin_claim, base_metric, margin_change=-0.0050, margin_tolerance_bps=20
    )
    assert res.rule_id == "R4"
    assert res.status == "flag"
    assert res.severity == "high"


def test_r4_profitability_not_applicable(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R4 returns not_applicable for non-margin claims or missing data."""
    non_margin_claim = base_claim.model_copy(update={"descriptor": "strong", "metric": "revenue"})
    res = evaluate_r4_profitability(non_margin_claim, base_metric, margin_change=0.01)
    assert res.rule_id == "R4"
    assert res.status == "not_applicable"


# ---------------------------------------------------------------------------
# Rule R5: Cash Quality
# ---------------------------------------------------------------------------


def test_r5_cash_quality_pass(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R5 passes when cash generation grew and conversion exceeds floor."""
    cash_claim = base_claim.model_copy(
        update={"descriptor": "strong cash generation", "metric": "ocf"}
    )
    res = evaluate_r5_cash_quality(
        cash_claim,
        base_metric,
        ocf_yoy_growth=0.15,
        ocf_conversion=0.85,
        ocf_conversion_floor=0.5,
    )
    assert res.rule_id == "R5"
    assert res.status == "pass"


def test_r5_cash_quality_flag(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R5 flags when cash flow dropped YoY or conversion falls below floor."""
    cash_claim = base_claim.model_copy(
        update={"descriptor": "strong cash generation", "metric": "ocf"}
    )
    # Conversion 0.35 < floor 0.50
    res = evaluate_r5_cash_quality(
        cash_claim,
        base_metric,
        ocf_yoy_growth=0.05,
        ocf_conversion=0.35,
        ocf_conversion_floor=0.5,
    )
    assert res.rule_id == "R5"
    assert res.status == "flag"
    assert res.severity == "medium"


def test_r5_cash_quality_not_applicable(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R5 returns not_applicable for non-cash claims or missing inputs."""
    res = evaluate_r5_cash_quality(
        base_claim, base_metric, ocf_yoy_growth=0.10, ocf_conversion=0.80
    )
    assert res.rule_id == "R5"
    assert res.status == "not_applicable"


# ---------------------------------------------------------------------------
# Rule R6: Working Capital
# ---------------------------------------------------------------------------


def test_r6_working_capital_pass(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R6 passes when inventory growth aligns with revenue and DSO is steady."""
    wc_claim = base_claim.model_copy(
        update={"descriptor": "disciplined inventory", "metric": "inventory"}
    )
    res = evaluate_r6_working_capital(
        wc_claim,
        base_metric,
        inventory_growth=0.10,
        revenue_growth=0.08,
        dso_change=2.0,
        inventory_gap_threshold_pp=15.0,
        dso_increase_threshold_days=10,
    )
    assert res.rule_id == "R6"
    assert res.status == "pass"


def test_r6_working_capital_flag(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R6 flags when inventory growth vastly outpaces revenue or DSO spikes."""
    wc_claim = base_claim.model_copy(
        update={"descriptor": "disciplined inventory", "metric": "inventory"}
    )
    # Inventory grew 30%, revenue grew 10% -> gap 20 pp > 15 pp
    res = evaluate_r6_working_capital(
        wc_claim,
        base_metric,
        inventory_growth=0.30,
        revenue_growth=0.10,
        dso_change=2.0,
        inventory_gap_threshold_pp=15.0,
        dso_increase_threshold_days=10,
    )
    assert res.rule_id == "R6"
    assert res.status == "flag"
    assert res.severity == "low_medium"

    # Or DSO increased by 15 days > 10 days
    res_dso = evaluate_r6_working_capital(
        wc_claim,
        base_metric,
        inventory_growth=0.08,
        revenue_growth=0.08,
        dso_change=15.0,
        inventory_gap_threshold_pp=15.0,
        dso_increase_threshold_days=10,
    )
    assert res_dso.status == "flag"


def test_r6_working_capital_not_applicable(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R6 returns not_applicable for non-WC claims or missing metrics."""
    res = evaluate_r6_working_capital(
        base_claim, base_metric, inventory_growth=0.10, revenue_growth=0.10
    )
    assert res.rule_id == "R6"
    assert res.status == "not_applicable"


# ---------------------------------------------------------------------------
# Rule R7: Understatement
# ---------------------------------------------------------------------------


def test_r7_understatement_pass(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R7 passes when cautious claim matches ordinary growth."""
    cautious_claim = base_claim.model_copy(update={"descriptor": "subdued"})
    res = evaluate_r7_understatement(
        cautious_claim,
        base_metric,
        growth=0.08,
        strong_threshold=0.08,
        understatement_gap_pp=10.0,
    )
    assert res.rule_id == "R7"
    assert res.status == "pass"


def test_r7_understatement_flag(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R7 flags when cautious claim is contradicted by blowout growth."""
    cautious_claim = base_claim.model_copy(update={"descriptor": "muted"})
    # Growth 25% >= 8% + 10% = 18%
    res = evaluate_r7_understatement(
        cautious_claim,
        base_metric,
        growth=0.25,
        strong_threshold=0.08,
        understatement_gap_pp=10.0,
    )
    assert res.rule_id == "R7"
    assert res.status == "flag"
    assert res.severity == "low"


def test_r7_understatement_not_applicable(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R7 returns not_applicable when descriptor is not cautious."""
    res = evaluate_r7_understatement(base_claim, base_metric, growth=0.25, strong_threshold=0.08)
    assert res.rule_id == "R7"
    assert res.status == "not_applicable"


def test_r7_understatement_pending_threshold(base_claim: Claim, base_metric: FilingMetric) -> None:
    """R7 returns not_applicable with reason 'threshold pending' when threshold is missing."""
    cautious_claim = base_claim.model_copy(update={"descriptor": "muted"})
    res = evaluate_r7_understatement(
        cautious_claim,
        base_metric,
        growth=0.25,
        sector="mining",
        sector_thresholds={"fmcg": 0.06},
    )
    assert res.rule_id == "R7"
    assert res.status == "not_applicable"
    assert res.reason == "threshold pending"


# ---------------------------------------------------------------------------
# evaluate_all_rules: Ordering and Completeness
# ---------------------------------------------------------------------------


def test_evaluate_all_rules_order_and_completeness(
    base_claim: Claim, base_metric: FilingMetric
) -> None:
    """evaluate_all_rules returns 8 results in strict order R0 then R1 through R7."""
    results = evaluate_all_rules(
        base_claim,
        base_metric,
        stated_value=10.0,
        filing_change=5.0,
        growth=0.10,
        strong_threshold=0.08,
        current_growth=0.10,
        prior_growth=0.08,
    )
    assert len(results) == 8
    rule_ids = [r.rule_id for r in results]
    assert rule_ids == ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"]
