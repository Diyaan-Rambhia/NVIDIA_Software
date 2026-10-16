"""Process metrics for Feature 3 Investment Log Advisor.

Implements portfolio concentration (HHI), one-way turnover, disposition effect (PGR/PLR),
and maximum drawdown per PROJECT.md §5.11 and AGENTS.md rules.
"""

from collections.abc import Sequence

import numpy as np

from backend.app.config.loader import ParameterError


def concentration_hhi(weights: Sequence[float] | np.ndarray) -> float:
    """Compute Herfindahl-Hirschman Index (HHI) of portfolio position weights in [0, 1].

    Formula: HHI = sum_i w_i^2, where w_i = V_i / sum_j V_j.
    """
    if len(weights) == 0:
        raise ParameterError(
            field="weights",
            value="empty sequence",
            allowed_range="non-empty sequence",
            reason="Position weights sequence cannot be empty",
        )

    w_arr = np.asarray(weights, dtype=float)
    if not np.all(np.isfinite(w_arr)):
        raise ParameterError(
            field="weights",
            value="non-finite elements",
            allowed_range="finite numbers",
            reason="Weights array contains NaN or infinite values",
        )

    if np.any(w_arr < 0.0):
        raise ParameterError(
            field="weights",
            value="negative weight",
            allowed_range="non-negative weights",
            reason="Position weights cannot be negative",
        )

    total_weight = float(np.sum(w_arr))
    if total_weight <= 0.0:
        raise ParameterError(
            field="weights",
            value=total_weight,
            allowed_range="strictly positive sum",
            reason="Sum of position weights must be strictly positive",
        )

    normalized_weights = w_arr / total_weight
    hhi = float(np.sum(normalized_weights**2))
    return float(np.clip(hhi, 0.0, 1.0))


def turnover(
    traded_values: Sequence[float] | np.ndarray,
    avg_portfolio_value: float,
) -> float:
    """Compute one-way portfolio turnover.

    Formula: Turnover = sum |V_traded| / (2 * avg_portfolio_value).
    """
    if not isinstance(avg_portfolio_value, (int, float)) or avg_portfolio_value <= 0.0:
        raise ParameterError(
            field="avg_portfolio_value",
            value=avg_portfolio_value,
            allowed_range="strictly positive float",
            reason="Average portfolio value must be strictly positive",
        )

    vals = np.asarray(traded_values, dtype=float)
    if len(vals) == 0:
        raise ParameterError(
            field="traded_values",
            value="empty sequence",
            allowed_range="non-empty sequence",
            reason="Traded values sequence cannot be empty",
        )

    if not np.all(np.isfinite(vals)):
        raise ParameterError(
            field="traded_values",
            value="non-finite values",
            allowed_range="finite numbers",
            reason="Traded values contain NaN or infinite numbers",
        )

    total_traded = float(np.sum(np.abs(vals)))
    divisor = 2.0 * avg_portfolio_value
    return float(total_traded / divisor)


def disposition_effect(
    realized_gains: float,
    paper_gains: float,
    realized_losses: float,
    paper_losses: float,
    sale_count: int,
    min_sales: int,
) -> tuple[float, float]:
    """Compute Proportion of Gains Realized (PGR) and Proportion of Losses Realized (PLR).

    PGR = Realized Gains / (Realized Gains + Paper Gains)
    PLR = Realized Losses / (Realized Losses + Paper Losses)
    """
    for name, val in [
        ("realized_gains", realized_gains),
        ("paper_gains", paper_gains),
        ("realized_losses", realized_losses),
        ("paper_losses", paper_losses),
    ]:
        if not isinstance(val, (int, float)) or not np.isfinite(val) or val < 0.0:
            raise ParameterError(
                field=name,
                value=val,
                allowed_range="non-negative finite float",
                reason=f"{name} must be a non-negative finite number",
            )

    if not isinstance(min_sales, int) or min_sales <= 0:
        raise ParameterError(
            field="min_sales",
            value=min_sales,
            allowed_range="strictly positive int",
            reason="Minimum sales threshold must be a strictly positive integer",
        )

    if not isinstance(sale_count, int) or sale_count < min_sales:
        raise ParameterError(
            field="sale_count",
            value=sale_count,
            allowed_range=f">= min_sales ({min_sales})",
            reason=(
                f"Sale count {sale_count} is less than required minimum sales threshold {min_sales}"
            ),
        )

    gains_denom = realized_gains + paper_gains
    if gains_denom <= 0.0:
        raise ParameterError(
            field="gains_denominator",
            value=gains_denom,
            allowed_range="strictly positive",
            reason="Sum of realized gains and paper gains must be strictly positive",
        )

    losses_denom = realized_losses + paper_losses
    if losses_denom <= 0.0:
        raise ParameterError(
            field="losses_denominator",
            value=losses_denom,
            allowed_range="strictly positive",
            reason="Sum of realized losses and paper losses must be strictly positive",
        )

    pgr = float(realized_gains / gains_denom)
    plr = float(realized_losses / losses_denom)
    return pgr, plr


def max_drawdown(values: Sequence[float] | np.ndarray) -> float:
    """Compute Maximum Drawdown (MDD) from a peak in portfolio valuation.

    Formula: MDD = max_t (1 - V_t / peak_t).
    """
    v_arr = np.asarray(values, dtype=float)
    if len(v_arr) == 0:
        raise ParameterError(
            field="values",
            value="empty sequence",
            allowed_range="non-empty sequence",
            reason="Portfolio values sequence cannot be empty",
        )

    if not np.all(np.isfinite(v_arr)):
        raise ParameterError(
            field="values",
            value="non-finite elements",
            allowed_range="finite numbers",
            reason="Portfolio values contain NaN or infinite numbers",
        )

    if np.any(v_arr <= 0.0):
        raise ParameterError(
            field="values",
            value="non-positive value",
            allowed_range="strictly positive values",
            reason="Portfolio values must be strictly positive",
        )

    peaks = np.maximum.accumulate(v_arr)
    drawdowns = (peaks - v_arr) / peaks
    mdd = float(np.max(drawdowns))
    return float(np.clip(mdd, 0.0, 1.0))
