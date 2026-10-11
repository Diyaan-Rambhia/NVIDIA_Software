"""Known-answer and error handling tests for process metrics.

Tests concentration (HHI), one-way turnover, disposition effect (PGR/PLR),
and maximum drawdown using hand-computed benchmark values.
"""

import math

import pytest

from backend.app.config.loader import ParameterError
from backend.app.features.f3_log.process_metrics import (
    concentration_hhi,
    disposition_effect,
    max_drawdown,
    turnover,
)


def test_concentration_hhi_known_answers() -> None:
    """Verify HHI calculation on hand-computed allocations."""
    # Two equal positions: 0.5^2 + 0.5^2 = 0.50
    assert math.isclose(concentration_hhi([50.0, 50.0]), 0.50, rel_tol=1e-12)

    # Four equal positions: 4 * 0.25^2 = 0.25
    assert math.isclose(concentration_hhi([25.0, 25.0, 25.0, 25.0]), 0.25, rel_tol=1e-12)

    # Concentrated single position: 1.0^2 = 1.0
    assert math.isclose(concentration_hhi([100.0]), 1.0, rel_tol=1e-12)


def test_concentration_hhi_invalid_inputs_raise() -> None:
    """Empty, negative, non-finite, or all-zero weights must raise ParameterError."""
    with pytest.raises(ParameterError, match="cannot be empty"):
        concentration_hhi([])

    with pytest.raises(ParameterError, match="cannot be negative"):
        concentration_hhi([10.0, -5.0])

    with pytest.raises(ParameterError, match="strictly positive sum"):
        concentration_hhi([0.0, 0.0])

    with pytest.raises(ParameterError, match="NaN or infinite"):
        concentration_hhi([10.0, float("nan")])


def test_turnover_one_way_known_answer() -> None:
    """Verify one-way turnover = sum |traded| / (2 * avg_portfolio_value)."""
    # Total traded = 100 + 200 + 100 = 400. One-way with avg=1000: 400 / 2000 = 0.20
    trades = [100.0, 200.0, 100.0]
    avg_val = 1000.0
    assert math.isclose(turnover(trades, avg_portfolio_value=avg_val), 0.20, rel_tol=1e-12)


def test_turnover_invalid_inputs_raise() -> None:
    """Non-positive portfolio value or empty trades must raise ParameterError."""
    with pytest.raises(ParameterError, match="strictly positive"):
        turnover([100.0], avg_portfolio_value=0.0)

    with pytest.raises(ParameterError, match="strictly positive"):
        turnover([100.0], avg_portfolio_value=-500.0)

    with pytest.raises(ParameterError, match="cannot be empty"):
        turnover([], avg_portfolio_value=1000.0)

    with pytest.raises(ParameterError, match="NaN or infinite"):
        turnover([float("inf")], avg_portfolio_value=1000.0)


def test_disposition_effect_known_answers() -> None:
    """Verify PGR and PLR on hand-computed gains and losses."""
    # Realized gains 100, paper gains 100 -> PGR = 100 / 200 = 0.50
    # Realized losses 50, paper losses 150 -> PLR = 50 / 200 = 0.25
    pgr, plr = disposition_effect(
        realized_gains=100.0,
        paper_gains=100.0,
        realized_losses=50.0,
        paper_losses=150.0,
        sale_count=10,
        min_sales=5,
    )
    assert math.isclose(pgr, 0.50, rel_tol=1e-12)
    assert math.isclose(plr, 0.25, rel_tol=1e-12)


def test_disposition_effect_zero_denominator_raises() -> None:
    """Zero gains or losses denominator must raise ParameterError."""
    with pytest.raises(ParameterError, match="strictly positive"):
        disposition_effect(0.0, 0.0, 50.0, 50.0, sale_count=10, min_sales=5)

    with pytest.raises(ParameterError, match="strictly positive"):
        disposition_effect(50.0, 50.0, 0.0, 0.0, sale_count=10, min_sales=5)


def test_disposition_effect_sale_count_threshold_raises() -> None:
    """Sale count below min_sales threshold must raise ParameterError."""
    with pytest.raises(ParameterError, match="less than required minimum sales"):
        disposition_effect(100.0, 100.0, 50.0, 50.0, sale_count=3, min_sales=5)


def test_max_drawdown_known_answer() -> None:
    """Verify MDD on hand-computed valuation trajectory."""
    # Peaks: 100, 120, 120, 120, 130
    # Worst drop: from 120 down to 90 -> (120 - 90) / 120 = 30 / 120 = 0.25
    vals = [100.0, 120.0, 90.0, 110.0, 130.0]
    assert math.isclose(max_drawdown(vals), 0.25, rel_tol=1e-12)


def test_max_drawdown_invalid_inputs_raise() -> None:
    """Empty, non-positive, or non-finite valuations must raise ParameterError."""
    with pytest.raises(ParameterError, match="cannot be empty"):
        max_drawdown([])

    with pytest.raises(ParameterError, match="strictly positive"):
        max_drawdown([100.0, 0.0, 50.0])

    with pytest.raises(ParameterError, match="strictly positive"):
        max_drawdown([100.0, -10.0, 50.0])

    with pytest.raises(ParameterError, match="NaN or infinite"):
        max_drawdown([100.0, float("nan"), 50.0])
