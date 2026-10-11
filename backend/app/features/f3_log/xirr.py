"""Extended Internal Rate of Return (XIRR) solver over dated cash flows.

Implements bracketed root-finding via Brent's method per PROJECT.md §5.11,
using standard spreadsheet 365-day year basis without bare numeric literals.
"""

import math
from collections.abc import Sequence
from datetime import date, datetime

import numpy as np
import scipy.optimize

from backend.app.config.loader import ParameterError

# Standard spreadsheet day-count basis recorded in DECISIONS.md D-18
DAYS_PER_YEAR: float = 365.0


class XIRRError(ArithmeticError):
    """Base exception for XIRR calculation errors."""


class XIRRConvergenceError(XIRRError):
    """Raised when the solver fails to converge or no root exists in the bracket."""


class MultipleRootsError(XIRRError):
    """Raised when multiple sign changes are detected in NPV across the bracket."""


class XIRRSignError(XIRRError):
    """Raised when cash flows lack both positive and negative entries."""


def _extract_calendar_date(d: date | datetime) -> date:
    """Extract standard calendar date, strictly rejecting naive datetime objects."""
    if isinstance(d, datetime):
        if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
            raise ParameterError(
                field="cash_flows",
                value=str(d),
                allowed_range="timezone-aware datetime or calendar date",
                reason="Naive datetimes are not permitted; datetime objects must be timezone-aware",
            )
        return d.date()
    if isinstance(d, date):
        return d
    raise ParameterError(
        field="cash_flows",
        value=type(d).__name__,
        allowed_range="date or datetime",
        reason=f"Expected date or datetime instance, got {type(d).__name__}",
    )


def xirr(
    cash_flows: Sequence[tuple[date | datetime, float]],
    bracket: tuple[float, float],
    tol: float,
    max_iter: int,
    grid_points: int,
    days_per_year: float = DAYS_PER_YEAR,
) -> float:
    """Compute XIRR annualised rate equating net present value of dated cash flows to zero.

    Solves sum_i CF_i / (1 + r)^((d_i - d_0) / days_per_year) == 0.
    """
    if not cash_flows or len(cash_flows) == 0:
        raise ParameterError(
            field="cash_flows",
            value="empty sequence",
            allowed_range="non-empty sequence",
            reason="Cash flows sequence cannot be empty",
        )

    if not isinstance(bracket, tuple) or len(bracket) != 2:
        raise ParameterError(
            field="bracket",
            value=bracket,
            allowed_range="tuple of (r_min, r_max)",
            reason="Bracket must be a 2-tuple of (r_min, r_max)",
        )

    r_min, r_max = bracket
    if not (math.isfinite(r_min) and math.isfinite(r_max)):
        raise ParameterError(
            field="bracket",
            value=bracket,
            allowed_range="finite floats",
            reason="Bracket bounds must be finite numbers",
        )

    if r_min <= -1.0:
        raise ParameterError(
            field="bracket",
            value=r_min,
            allowed_range="> -1.0",
            reason="Bracket lower bound must be strictly greater than -1.0",
        )

    if r_min >= r_max:
        raise ParameterError(
            field="bracket",
            value=bracket,
            allowed_range="r_min < r_max",
            reason="Bracket lower bound must be strictly less than upper bound",
        )

    if not math.isfinite(tol) or tol <= 0.0:
        raise ParameterError(
            field="tol",
            value=tol,
            allowed_range="strictly positive float",
            reason="Solver tolerance must be strictly positive",
        )

    if not isinstance(max_iter, int) or isinstance(max_iter, bool) or max_iter <= 0:
        raise ParameterError(
            field="max_iter",
            value=max_iter,
            allowed_range="positive int",
            reason="Maximum iterations must be a positive integer",
        )

    if not isinstance(grid_points, int) or isinstance(grid_points, bool) or grid_points < 2:
        raise ParameterError(
            field="grid_points",
            value=grid_points,
            allowed_range="int >= 2",
            reason="Grid evaluation points must be an integer >= 2",
        )

    if not math.isfinite(days_per_year) or days_per_year <= 0.0:
        raise ParameterError(
            field="days_per_year",
            value=days_per_year,
            allowed_range="positive float",
            reason="Day count basis divisor must be strictly positive",
        )

    parsed_dates: list[date] = []
    amounts: list[float] = []

    for idx, (raw_dt, amt) in enumerate(cash_flows):
        cal_date = _extract_calendar_date(raw_dt)
        parsed_dates.append(cal_date)

        if not isinstance(amt, (int, float)) or not math.isfinite(amt):
            raise ParameterError(
                field=f"cash_flows[{idx}].amount",
                value=amt,
                allowed_range="finite number",
                reason=f"Cash flow amount at index {idx} must be a finite number",
            )
        amounts.append(float(amt))

    # Check for strictly increasing sorted dates without duplicates
    for i in range(len(parsed_dates) - 1):
        if parsed_dates[i + 1] <= parsed_dates[i]:
            raise ParameterError(
                field="cash_flows.dates",
                value=f"{parsed_dates[i]} and {parsed_dates[i + 1]}",
                allowed_range="strictly ascending unique dates",
                reason=(
                    "Cash flows must be strictly sorted by date in ascending order "
                    "without duplicate dates"
                ),
            )

    # Check for non-zero flows
    if all(amt == 0.0 for amt in amounts):
        raise ParameterError(
            field="cash_flows.amounts",
            value="all zero",
            allowed_range="at least one non-zero flow",
            reason="Cash flows cannot be all zero",
        )

    # Check sign requirement: at least one positive and one negative flow
    has_pos = any(amt > 0.0 for amt in amounts)
    has_neg = any(amt < 0.0 for amt in amounts)
    if not (has_pos and has_neg):
        raise XIRRSignError(
            "Cash flows must contain at least one positive flow and at least one negative flow"
        )

    d0 = parsed_dates[0]
    time_deltas = [(d - d0).days / days_per_year for d in parsed_dates]

    def npv(rate: float) -> float:
        total = 0.0
        for dt, amt in zip(time_deltas, amounts, strict=True):
            total += amt / ((1.0 + rate) ** dt)
        return total

    # Evaluate NPV on bracket grid to count sign changes
    eval_rates = np.linspace(r_min, r_max, grid_points)
    npv_vals = [npv(float(r)) for r in eval_rates]

    sign_changes = 0
    bracket_pairs: list[tuple[float, float]] = []

    for i in range(len(npv_vals) - 1):
        v1, v2 = npv_vals[i], npv_vals[i + 1]
        r1, r2 = float(eval_rates[i]), float(eval_rates[i + 1])

        if v1 == 0.0:
            return r1
        if v2 == 0.0:
            return r2

        if (v1 > 0.0 and v2 < 0.0) or (v1 < 0.0 and v2 > 0.0):
            sign_changes += 1
            bracket_pairs.append((r1, r2))

    if sign_changes == 0:
        raise XIRRConvergenceError(
            f"No sign change in NPV detected across bracket [{r_min}, {r_max}]; no root exists"
        )

    if sign_changes > 1:
        raise MultipleRootsError(
            f"Multiple sign changes ({sign_changes}) detected in NPV across "
            f"bracket [{r_min}, {r_max}]"
        )

    root_bracket_a, root_bracket_b = bracket_pairs[0]

    try:
        sol = scipy.optimize.brentq(
            npv,
            root_bracket_a,
            root_bracket_b,
            xtol=tol,
            maxiter=max_iter,
        )
        return float(sol)
    except Exception as exc:
        raise XIRRConvergenceError(f"Brent solver failed to converge: {exc}") from exc
