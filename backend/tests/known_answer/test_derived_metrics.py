"""Known-answer and validation tests for derived filing metrics.

Tests YoY/QoQ growth, margins, DSO with dynamic fiscal days, OCF conversion,
and Q4 derivation including fiscal year and unit validation.
"""

import math

import pytest

from backend.app.config.loader import ParameterError
from backend.app.features.f2_filings.derived_metrics import (
    dso,
    margin,
    ocf_conversion,
    q4_derivation,
    qoq_growth,
    yoy_growth,
)


def test_yoy_growth_hand_computed() -> None:
    """Verify YoY growth between matching quarters of successive fiscal years."""
    # Q1 FY27 vs Q1 FY26: (120 - 100) / 100 = 0.20
    growth = yoy_growth(120.0, "Q1 FY27", 100.0, "Q1 FY26")
    assert math.isclose(growth, 0.20, rel_tol=1e-12)


def test_yoy_growth_mismatched_periods_raise() -> None:
    """Non-matching quarter or year gap != 1 must raise ParameterError."""
    # Different quarters
    with pytest.raises(ParameterError, match="does not match prior fiscal year"):
        yoy_growth(120.0, "Q1 FY27", 100.0, "Q2 FY26")

    # Gap of two years
    with pytest.raises(ParameterError, match="does not match prior fiscal year"):
        yoy_growth(120.0, "Q1 FY27", 100.0, "Q1 FY25")


def test_yoy_growth_non_positive_base_raises() -> None:
    """Zero or negative prior base value must raise ParameterError."""
    with pytest.raises(ParameterError, match="Zero or negative base value"):
        yoy_growth(100.0, "Q1 FY27", 0.0, "Q1 FY26")

    with pytest.raises(ParameterError, match="Zero or negative base value"):
        yoy_growth(100.0, "Q1 FY27", -50.0, "Q1 FY26")


def test_qoq_growth_hand_computed() -> None:
    """Verify QoQ growth between adjacent fiscal quarters."""
    # Intra-year: Q2 FY27 vs Q1 FY27: (110 - 100) / 100 = 0.10
    g1 = qoq_growth(110.0, "Q2 FY27", 100.0, "Q1 FY27")
    assert math.isclose(g1, 0.10, rel_tol=1e-12)

    # Cross-year boundary: Q1 FY28 vs Q4 FY27: (115 - 100) / 100 = 0.15
    g2 = qoq_growth(115.0, "Q1 FY28", 100.0, "Q4 FY27")
    assert math.isclose(g2, 0.15, rel_tol=1e-12)


def test_qoq_growth_mismatched_periods_raise() -> None:
    """Non-adjacent quarters must raise ParameterError."""
    with pytest.raises(ParameterError, match="does not match immediately preceding quarter"):
        qoq_growth(120.0, "Q3 FY27", 100.0, "Q1 FY27")


def test_margin_known_answers() -> None:
    """Verify margin calculation = metric / revenue_from_operations."""
    assert math.isclose(margin(25.0, 100.0), 0.25, rel_tol=1e-12)
    assert math.isclose(margin(-10.0, 100.0), -0.10, rel_tol=1e-12)


def test_margin_zero_or_negative_revenue_raises() -> None:
    """Zero or negative revenue must raise ParameterError."""
    with pytest.raises(ParameterError, match="strictly positive"):
        margin(10.0, 0.0)

    with pytest.raises(ParameterError, match="strictly positive"):
        margin(10.0, -100.0)


def test_dso_with_dynamic_fiscal_days() -> None:
    """Verify DSO uses exact calendar days from A2.1 fiscal utilities."""
    # Q1 FY27 runs April 1 to June 30 = 91 days
    # Receivables=50, Revenue=100 -> (50 / 100) * 91 = 45.5 days
    res = dso(50.0, 100.0, "Q1 FY27")
    assert math.isclose(res, 45.5, rel_tol=1e-12)


def test_dso_invalid_inputs_raise() -> None:
    """Zero revenue or negative receivables must raise ParameterError."""
    with pytest.raises(ParameterError, match="strictly positive"):
        dso(50.0, 0.0, "Q1 FY27")

    with pytest.raises(ParameterError, match="cannot be negative"):
        dso(-10.0, 100.0, "Q1 FY27")


def test_ocf_conversion_known_answer() -> None:
    """Verify OCF conversion = OCF / PAT."""
    assert math.isclose(ocf_conversion(80.0, 100.0), 0.80, rel_tol=1e-12)


def test_ocf_conversion_non_positive_pat_raises() -> None:
    """Zero or negative PAT must raise ParameterError."""
    with pytest.raises(ParameterError, match="strictly positive"):
        ocf_conversion(50.0, 0.0)

    with pytest.raises(ParameterError, match="strictly positive"):
        ocf_conversion(50.0, -100.0)


def test_q4_derivation_known_answer() -> None:
    """Verify Q4 derivation = Full Year - 9M cumulative for identical FY and units."""
    q4_rev = q4_derivation(
        full_year_value=400.0,
        full_year_label="FY27",
        full_year_unit="INR Crore",
        nine_month_value=300.0,
        nine_month_label="9M FY27",
        nine_month_unit="INR Crore",
        metric_type="revenue",
    )
    assert math.isclose(q4_rev, 100.0, rel_tol=1e-12)


def test_q4_derivation_mismatched_fiscal_year_raises() -> None:
    """Mismatched fiscal years between annual and 9M figures must raise ParameterError."""
    with pytest.raises(ParameterError, match="cover the same fiscal year"):
        q4_derivation(
            full_year_value=400.0,
            full_year_label="FY27",
            full_year_unit="crore",
            nine_month_value=300.0,
            nine_month_label="9M FY26",
            nine_month_unit="crore",
        )


def test_q4_derivation_mismatched_units_raises() -> None:
    """Mismatched units between annual and 9M figures must raise ParameterError."""
    with pytest.raises(ParameterError, match="identical units"):
        q4_derivation(
            full_year_value=400.0,
            full_year_label="FY27",
            full_year_unit="crore",
            nine_month_value=300.0,
            nine_month_label="9M FY27",
            nine_month_unit="lakh",
        )


def test_q4_derivation_negative_revenue_raises() -> None:
    """Derived Q4 revenue being negative must raise ParameterError."""
    with pytest.raises(ParameterError, match="revenue-type value cannot be negative"):
        q4_derivation(
            full_year_value=400.0,
            full_year_label="FY27",
            full_year_unit="crore",
            nine_month_value=450.0,
            nine_month_label="9M FY27",
            nine_month_unit="crore",
            metric_type="revenue",
        )


def test_q4_derivation_negative_profit_allowed() -> None:
    """Derived Q4 profit can be negative (quarterly loss)."""
    q4_profit = q4_derivation(
        full_year_value=50.0,
        full_year_label="FY27",
        full_year_unit="crore",
        nine_month_value=70.0,
        nine_month_label="9M FY27",
        nine_month_unit="crore",
        metric_type="net_profit",
    )
    assert math.isclose(q4_profit, -20.0, rel_tol=1e-12)
