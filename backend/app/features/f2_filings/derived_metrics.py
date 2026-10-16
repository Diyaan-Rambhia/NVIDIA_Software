"""Derived filing metrics for Feature 2 Filing Consistency Checker.

Implements YoY growth, QoQ growth, margins, DSO with dynamic fiscal period days,
OCF conversion, and Q4 derivation per PROJECT.md §5.10 and finance/04.
"""

import math
import re

from backend.app.config.loader import ParameterError
from backend.app.data.fiscal import fiscal_period_to_dates, parse_fiscal_label

_FY_REGEX = re.compile(r"(?:^|\b)(?:9M\s+)?FY(\d{2}|\d{4})(?:\b|$)", re.IGNORECASE)


def _parse_fiscal_year(label: str) -> int:
    """Extract 4-digit fiscal year from full year or 9M cumulative label."""
    match = _FY_REGEX.search(label.strip())
    if not match:
        raise ParameterError(
            field="fiscal_label",
            value=label,
            allowed_range="canonical label with FY{YY}",
            reason=f"Could not parse fiscal year from label '{label}'",
        )
    raw_year = int(match.group(1))
    if raw_year < 100:
        return 2000 + raw_year
    return raw_year


def yoy_growth(
    current_value: float,
    current_period: str,
    prior_value: float,
    prior_period: str,
) -> float:
    """Calculate Year-over-Year (YoY) growth strictly between matching quarters of successive years.

    Formula: g_YoY = (v_t - v_{t-4Q}) / v_{t-4Q}.
    """
    if not math.isfinite(current_value) or not math.isfinite(prior_value):
        raise ParameterError(
            field="values",
            value=f"current={current_value}, prior={prior_value}",
            allowed_range="finite numbers",
            reason="Metric values must be finite numbers",
        )

    q_curr, fy_curr = parse_fiscal_label(current_period)
    q_prior, fy_prior = parse_fiscal_label(prior_period)

    if q_curr != q_prior or fy_curr != fy_prior + 1:
        raise ParameterError(
            field="periods",
            value=f"current='{current_period}', prior='{prior_period}'",
            allowed_range="matching quarter of immediately preceding fiscal year",
            reason=(
                f"Prior period '{prior_period}' does not match prior fiscal year "
                f"for current period '{current_period}'"
            ),
        )

    if prior_value <= 0.0:
        raise ParameterError(
            field="prior_value",
            value=prior_value,
            allowed_range="strictly positive base value",
            reason="Zero or negative base value is not allowed for growth rate",
        )

    return float((current_value - prior_value) / prior_value)


def qoq_growth(
    current_value: float,
    current_period: str,
    prior_value: float,
    prior_period: str,
) -> float:
    """Calculate Quarter-over-Quarter (QoQ) growth strictly between adjacent fiscal quarters.

    Formula: g_QoQ = (v_t - v_{t-1Q}) / v_{t-1Q}.
    """
    if not math.isfinite(current_value) or not math.isfinite(prior_value):
        raise ParameterError(
            field="values",
            value=f"current={current_value}, prior={prior_value}",
            allowed_range="finite numbers",
            reason="Metric values must be finite numbers",
        )

    q_curr, fy_curr = parse_fiscal_label(current_period)
    q_prior, fy_prior = parse_fiscal_label(prior_period)

    if q_curr > 1:
        is_adjacent = (q_prior == q_curr - 1) and (fy_prior == fy_curr)
    else:
        is_adjacent = (q_prior == 4) and (fy_prior == fy_curr - 1)

    if not is_adjacent:
        raise ParameterError(
            field="periods",
            value=f"current='{current_period}', prior='{prior_period}'",
            allowed_range="immediately preceding fiscal quarter",
            reason=(
                f"Prior period '{prior_period}' does not match immediately preceding "
                f"quarter for '{current_period}'"
            ),
        )

    if prior_value <= 0.0:
        raise ParameterError(
            field="prior_value",
            value=prior_value,
            allowed_range="strictly positive base value",
            reason="Zero or negative base value is not allowed for growth rate",
        )

    return float((current_value - prior_value) / prior_value)


def margin(
    metric_value: float,
    revenue_from_operations: float,
) -> float:
    """Compute financial margin as metric divided by Revenue from Operations.

    Formula: Margin = Metric / Revenue_from_Operations.
    """
    if not math.isfinite(metric_value) or not math.isfinite(revenue_from_operations):
        raise ParameterError(
            field="values",
            value=f"metric={metric_value}, revenue={revenue_from_operations}",
            allowed_range="finite numbers",
            reason="Metric and revenue must be finite numbers",
        )

    if revenue_from_operations <= 0.0:
        raise ParameterError(
            field="revenue_from_operations",
            value=revenue_from_operations,
            allowed_range="strictly positive revenue",
            reason="Revenue from operations must be strictly positive",
        )

    return float(metric_value / revenue_from_operations)


def dso(
    trade_receivables: float,
    revenue_from_operations: float,
    period_label: str,
) -> float:
    """Compute Days Sales Outstanding (DSO) using calendar day count from fiscal utilities.

    Formula: DSO = (Trade_Receivables / Revenue_from_Operations) * Period_Days.
    """
    if not math.isfinite(trade_receivables) or not math.isfinite(revenue_from_operations):
        raise ParameterError(
            field="values",
            value=f"receivables={trade_receivables}, revenue={revenue_from_operations}",
            allowed_range="finite numbers",
            reason="Receivables and revenue must be finite numbers",
        )

    if trade_receivables < 0.0:
        raise ParameterError(
            field="trade_receivables",
            value=trade_receivables,
            allowed_range="non-negative receivables",
            reason="Trade receivables cannot be negative",
        )

    if revenue_from_operations <= 0.0:
        raise ParameterError(
            field="revenue_from_operations",
            value=revenue_from_operations,
            allowed_range="strictly positive revenue",
            reason="Revenue from operations must be strictly positive for DSO",
        )

    start_date, end_date = fiscal_period_to_dates(period_label)
    period_days = (end_date - start_date).days + 1

    return float((trade_receivables / revenue_from_operations) * period_days)


def ocf_conversion(
    operating_cash_flow: float,
    pat: float,
) -> float:
    """Compute Operating Cash Flow (OCF) conversion ratio against Profit After Tax (PAT).

    Formula: OCF Conversion = Operating_Cash_Flow / PAT.
    """
    if not math.isfinite(operating_cash_flow) or not math.isfinite(pat):
        raise ParameterError(
            field="values",
            value=f"ocf={operating_cash_flow}, pat={pat}",
            allowed_range="finite numbers",
            reason="Operating cash flow and PAT must be finite numbers",
        )

    if pat <= 0.0:
        raise ParameterError(
            field="pat",
            value=pat,
            allowed_range="strictly positive PAT",
            reason="PAT must be strictly positive for OCF conversion",
        )

    return float(operating_cash_flow / pat)


def q4_derivation(
    full_year_value: float,
    full_year_label: str,
    full_year_unit: str,
    nine_month_value: float,
    nine_month_label: str,
    nine_month_unit: str,
    metric_type: str = "general",
) -> float:
    """Derive fourth-quarter (Q4) figure by subtracting nine-month cumulative from full year.

    Formula: v_Q4 = v_Full_Year - v_9M_Cumulative.
    Verifies that annual and nine-month figures share identical fiscal year and units.
    """
    if not math.isfinite(full_year_value) or not math.isfinite(nine_month_value):
        raise ParameterError(
            field="values",
            value=f"full_year={full_year_value}, 9M={nine_month_value}",
            allowed_range="finite numbers",
            reason="Full year and nine-month values must be finite numbers",
        )

    fy_annual = _parse_fiscal_year(full_year_label)
    fy_9m = _parse_fiscal_year(nine_month_label)

    if fy_annual != fy_9m:
        raise ParameterError(
            field="fiscal_year",
            value=f"annual={full_year_label} ({fy_annual}), 9M={nine_month_label} ({fy_9m})",
            allowed_range="matching fiscal year",
            reason="Annual and nine-month figures must cover the same fiscal year",
        )

    if full_year_unit.strip().lower() != nine_month_unit.strip().lower():
        raise ParameterError(
            field="units",
            value=f"annual='{full_year_unit}', 9M='{nine_month_unit}'",
            allowed_range="identical units",
            reason="Annual and nine-month figures must have identical units",
        )

    q4_val = float(full_year_value - nine_month_value)

    # Revenue-type figures cannot be negative
    if (
        metric_type.strip().lower()
        in (
            "revenue",
            "revenue_from_operations",
            "income",
            "sales",
        )
        and q4_val < 0.0
    ):
        raise ParameterError(
            field="q4_value",
            value=q4_val,
            allowed_range="non-negative derived revenue",
            reason="Derived Q4 revenue-type value cannot be negative",
        )

    return q4_val
