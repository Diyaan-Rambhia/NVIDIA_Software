"""Institutional metrics for Feature 3 Investment Log Advisor.

Implements Beta, Alpha, Tracking Error, and Information Ratio per PROJECT.md §5.11.
Annualisation factors and return series are required arguments with no literals in logic.
"""

import math
from collections.abc import Sequence
from typing import Any

import numpy as np

from backend.app.config.loader import (
    ParameterError,
    get_risk_free_rate,
    get_risk_free_rate_parameters,
)
from backend.app.config.models import ParametersConfig


def resolve_risk_free_rate(params_config: ParametersConfig | None = None) -> float:
    """Resolve configured risk-free rate, raising ParameterError if null or unit invalid."""
    return get_risk_free_rate(params_config)


def resolve_risk_free_parameters(
    params_config: ParametersConfig | None = None,
) -> dict[str, Any]:
    """Resolve recorded parameters for the risk-free rate (value, unit, source, as_of)."""
    return get_risk_free_rate_parameters(params_config)


def _validate_return_pair(
    portfolio_returns: Sequence[float] | np.ndarray,
    benchmark_returns: Sequence[float] | np.ndarray,
    annualisation_factor: float,
    risk_free_returns: Sequence[float] | np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Validate paired return series and required annualisation factor."""
    if not isinstance(annualisation_factor, (int, float)) or annualisation_factor <= 0.0:
        raise ParameterError(
            field="annualisation_factor",
            value=annualisation_factor,
            allowed_range="strictly positive float",
            reason="Annualisation factor must be a strictly positive number",
        )

    rp = np.asarray(portfolio_returns, dtype=float)
    rb = np.asarray(benchmark_returns, dtype=float)

    if len(rp) < 2 or len(rb) < 2:
        raise ParameterError(
            field="returns",
            value=len(rp),
            allowed_range=">= 2 observations",
            reason="At least two return observations are required for statistical metrics",
        )

    if len(rp) != len(rb):
        raise ParameterError(
            field="returns",
            value=f"portfolio len {len(rp)} vs benchmark len {len(rb)}",
            allowed_range="equal length sequences",
            reason="Portfolio and benchmark return series must have identical length",
        )

    if not (np.all(np.isfinite(rp)) and np.all(np.isfinite(rb))):
        raise ParameterError(
            field="returns",
            value="non-finite elements",
            allowed_range="finite numbers",
            reason="Return series contain NaN or infinite numbers",
        )

    rf: np.ndarray | None = None
    if risk_free_returns is not None:
        rf = np.asarray(risk_free_returns, dtype=float)
        if len(rf) != len(rp):
            raise ParameterError(
                field="risk_free_returns",
                value=len(rf),
                allowed_range=f"equal length ({len(rp)})",
                reason="Risk-free return series must match portfolio return series length",
            )
        if not np.all(np.isfinite(rf)):
            raise ParameterError(
                field="risk_free_returns",
                value="non-finite elements",
                allowed_range="finite numbers",
                reason="Risk-free return series contains NaN or infinite numbers",
            )

    return rp, rb, rf


def beta_and_alpha(
    portfolio_returns: Sequence[float] | np.ndarray,
    benchmark_returns: Sequence[float] | np.ndarray,
    annualisation_factor: float,
    risk_free_returns: Sequence[float] | np.ndarray | None = None,
) -> tuple[float, float]:
    """Compute Beta and annualised Alpha against a benchmark using OLS regression.

    Beta = Cov(R_p - R_f, R_b - R_f) / Var(R_b - R_f) [ddof=1]
    Alpha = (Mean(R_p - R_f) - Beta * Mean(R_b - R_f)) * annualisation_factor
    """
    rp, rb, rf = _validate_return_pair(
        portfolio_returns,
        benchmark_returns,
        annualisation_factor,
        risk_free_returns,
    )

    if rf is not None:
        y = rp - rf
        x = rb - rf
    else:
        y = rp
        x = rb

    var_x = float(np.var(x, ddof=1))
    if var_x <= 0.0 or not math.isfinite(var_x):
        raise ParameterError(
            field="benchmark_variance",
            value=var_x,
            allowed_range="strictly positive variance",
            reason="Benchmark return variance must be strictly positive to compute Beta",
        )

    cov_matrix = np.cov(y, x, ddof=1)
    cov_xy = float(cov_matrix[0, 1])

    beta = float(cov_xy / var_x)
    alpha_period = float(np.mean(y) - beta * np.mean(x))
    alpha_annualized = float(alpha_period * annualisation_factor)

    return beta, alpha_annualized


def beta_and_alpha_result(
    portfolio_returns: Sequence[float] | np.ndarray,
    benchmark_returns: Sequence[float] | np.ndarray,
    annualisation_factor: float,
    risk_free_returns: Sequence[float] | np.ndarray | None = None,
    params_config: ParametersConfig | None = None,
) -> dict[str, Any]:
    """Compute Beta and Alpha recording risk-free rate parameters (value, unit, source, as_of)."""
    beta, alpha = beta_and_alpha(
        portfolio_returns,
        benchmark_returns,
        annualisation_factor,
        risk_free_returns,
    )
    rf_params = resolve_risk_free_parameters(params_config)
    return {
        "beta": beta,
        "alpha": alpha,
        "parameters": rf_params,
    }


def tracking_error(
    portfolio_returns: Sequence[float] | np.ndarray,
    benchmark_returns: Sequence[float] | np.ndarray,
    annualisation_factor: float,
) -> float:
    """Compute annualised Tracking Error (volatility of active returns).

    Formula: TE = Std(R_p - R_b, ddof=1) * sqrt(annualisation_factor).
    """
    rp, rb, _ = _validate_return_pair(
        portfolio_returns,
        benchmark_returns,
        annualisation_factor,
    )

    diff = rp - rb
    sample_std = float(np.std(diff, ddof=1))

    if sample_std == 0.0:
        raise ParameterError(
            field="tracking_error",
            value=sample_std,
            allowed_range="strictly positive active return variation",
            reason="Active return standard deviation is zero; tracking error cannot be zero",
        )

    te = sample_std * math.sqrt(annualisation_factor)
    return float(te)


def information_ratio(
    portfolio_returns: Sequence[float] | np.ndarray,
    benchmark_returns: Sequence[float] | np.ndarray,
    annualisation_factor: float,
) -> float:
    """Compute Information Ratio (annualised active return divided by tracking error).

    Formula: IR = (Mean(R_p - R_b) * annualisation_factor) / Tracking_Error.
    """
    rp, rb, _ = _validate_return_pair(
        portfolio_returns,
        benchmark_returns,
        annualisation_factor,
    )

    te = tracking_error(rp, rb, annualisation_factor)
    mean_active_annualized = float(np.mean(rp - rb) * annualisation_factor)

    return float(mean_active_annualized / te)
