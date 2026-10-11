"""Known-answer and validation tests for Extended Internal Rate of Return (XIRR).

Tests standard one-year rate, multi-flow convergence, root bracket sign enforcement,
multiple-root rejection, and strict error handling on invalid cash flow inputs.
"""

import math
from datetime import date, datetime, timezone

import pytest

from backend.app.config.loader import ParameterError
from backend.app.features.f3_log.xirr import (
    DAYS_PER_YEAR,
    MultipleRootsError,
    XIRRConvergenceError,
    XIRRSignError,
    xirr,
)


def test_xirr_one_year_hand_computed() -> None:
    """Verify known-answer benchmark: -100 then +110 exactly one year later yields 10%."""
    d0 = date(2026, 1, 1)
    d1 = date(2027, 1, 1)  # exactly 365 calendar days later
    flows = [(d0, -100.0), (d1, 110.0)]

    rate = xirr(
        flows,
        bracket=(-0.5, 2.0),
        tol=1e-8,
        max_iter=100,
        grid_points=50,
    )

    assert math.isclose(rate, 0.10, rel_tol=1e-7)


def test_xirr_first_flow_positive_accepted() -> None:
    """Verify that a positive initial flow is accepted as long as both signs are present."""
    d0 = date(2026, 1, 1)
    d1 = date(2027, 1, 1)
    flows = [(d0, 100.0), (d1, -110.0)]

    rate = xirr(
        flows,
        bracket=(-0.5, 2.0),
        tol=1e-8,
        max_iter=100,
        grid_points=50,
    )

    assert math.isclose(rate, 0.10, rel_tol=1e-7)


def test_xirr_multi_flow_convergence() -> None:
    """Verify multi-flow investment sequence satisfies NPV(rate) == 0."""
    d0 = date(2026, 1, 1)
    d1 = date(2026, 7, 2)
    d2 = date(2027, 1, 1)

    flows = [
        (d0, -1000.0),
        (d1, 200.0),
        (d2, 900.0),
    ]

    rate = xirr(
        flows,
        bracket=(-0.5, 1.0),
        tol=1e-8,
        max_iter=100,
        grid_points=50,
    )

    # Reconstruct NPV at the calculated rate
    t0 = d0
    npv = sum(amt / ((1.0 + rate) ** ((d - t0).days / DAYS_PER_YEAR)) for d, amt in flows)
    assert math.isclose(npv, 0.0, abs_tol=1e-5)


def test_xirr_timezone_aware_datetime_accepted() -> None:
    """Verify that timezone-aware datetime instances are accepted."""
    d0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    d1 = datetime(2027, 1, 1, 10, 0, tzinfo=timezone.utc)
    flows = [(d0, -100.0), (d1, 110.0)]

    rate = xirr(
        flows,
        bracket=(-0.5, 2.0),
        tol=1e-8,
        max_iter=100,
        grid_points=50,
    )
    assert math.isclose(rate, 0.10, rel_tol=1e-7)


def test_xirr_no_sign_change_in_flows_raises() -> None:
    """Cash flows with solely positive or negative values must raise XIRRSignError."""
    d0 = date(2026, 1, 1)
    d1 = date(2026, 6, 1)

    with pytest.raises(XIRRSignError):
        xirr([(d0, 100.0), (d1, 50.0)], bracket=(-0.5, 1.0), tol=1e-6, max_iter=50, grid_points=20)

    with pytest.raises(XIRRSignError):
        xirr(
            [(d0, -100.0), (d1, -50.0)],
            bracket=(-0.5, 1.0),
            tol=1e-6,
            max_iter=50,
            grid_points=20,
        )


def test_xirr_no_root_in_bracket_raises() -> None:
    """When bracket contains no sign change of NPV, must raise XIRRConvergenceError."""
    d0 = date(2026, 1, 1)
    d1 = date(2027, 1, 1)
    flows = [(d0, -100.0), (d1, 110.0)]  # Root is exactly 0.10

    # Bracket strictly above the root [0.50, 2.00]
    with pytest.raises(XIRRConvergenceError, match="No sign change"):
        xirr(flows, bracket=(0.50, 2.00), tol=1e-8, max_iter=100, grid_points=50)


def test_xirr_multiple_roots_raises() -> None:
    """When cash flows produce multiple NPV roots across the bracket, raise MultipleRootsError."""
    # Polynomial -100 + 230/(1+r) - 132/(1+r)^2 has roots at r = 0.10 and r = 0.20
    d0 = date(2026, 1, 1)
    d1 = date(2027, 1, 1)  # 365 days
    d2 = date(2028, 1, 1)  # 730 days

    flows = [
        (d0, -100.0),
        (d1, 230.0),
        (d2, -132.0),
    ]

    with pytest.raises(MultipleRootsError, match="Multiple sign changes"):
        xirr(
            flows,
            bracket=(0.05, 0.25),
            tol=1e-8,
            max_iter=100,
            grid_points=50,
        )


def test_xirr_non_convergence_raises() -> None:
    """When iteration limit is exceeded, raise XIRRConvergenceError."""
    d0 = date(2026, 1, 1)
    d1 = date(2027, 1, 1)
    flows = [(d0, -100.0), (d1, 110.0)]

    with pytest.raises(XIRRConvergenceError, match="failed to converge"):
        xirr(
            flows,
            bracket=(-0.5, 2.0),
            tol=1e-15,
            max_iter=1,  # Impractically small max iterations
            grid_points=20,
        )


def test_xirr_naive_datetime_raises() -> None:
    """Naive datetime objects must raise ParameterError."""
    d0 = datetime(2026, 1, 1, 10, 0)  # naive (no tzinfo)
    d1 = date(2027, 1, 1)
    with pytest.raises(ParameterError, match="Naive datetimes are not permitted"):
        xirr(
            [(d0, -100.0), (d1, 110.0)],
            bracket=(-0.5, 1.0),
            tol=1e-6,
            max_iter=50,
            grid_points=20,
        )


def test_xirr_unsorted_dates_raises() -> None:
    """Out-of-order dates must raise ParameterError."""
    d0 = date(2027, 1, 1)
    d1 = date(2026, 1, 1)
    with pytest.raises(ParameterError, match="strictly sorted"):
        xirr(
            [(d0, -100.0), (d1, 110.0)],
            bracket=(-0.5, 1.0),
            tol=1e-6,
            max_iter=50,
            grid_points=20,
        )


def test_xirr_duplicate_dates_raises() -> None:
    """Duplicate dates must raise ParameterError."""
    d0 = date(2026, 1, 1)
    with pytest.raises(ParameterError, match="strictly sorted"):
        xirr(
            [(d0, -100.0), (d0, 110.0)],
            bracket=(-0.5, 1.0),
            tol=1e-6,
            max_iter=50,
            grid_points=20,
        )


def test_xirr_all_zero_amounts_raises() -> None:
    """All-zero flows must raise ParameterError."""
    d0 = date(2026, 1, 1)
    d1 = date(2027, 1, 1)
    with pytest.raises(ParameterError, match="cannot be all zero"):
        xirr([(d0, 0.0), (d1, 0.0)], bracket=(-0.5, 1.0), tol=1e-6, max_iter=50, grid_points=20)


def test_xirr_empty_flows_raises() -> None:
    """Empty flow sequence must raise ParameterError."""
    with pytest.raises(ParameterError, match="cannot be empty"):
        xirr([], bracket=(-0.5, 1.0), tol=1e-6, max_iter=50, grid_points=20)


def test_xirr_non_finite_amount_raises() -> None:
    """NaN or infinite amounts must raise ParameterError."""
    d0 = date(2026, 1, 1)
    d1 = date(2027, 1, 1)
    with pytest.raises(ParameterError, match="finite number"):
        xirr(
            [(d0, -100.0), (d1, float("nan"))],
            bracket=(-0.5, 1.0),
            tol=1e-6,
            max_iter=50,
            grid_points=20,
        )
