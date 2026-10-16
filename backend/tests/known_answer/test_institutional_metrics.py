"""Known-answer and error handling tests for institutional metrics.

Tests Beta, Alpha, Tracking Error, and Information Ratio against hand-computed benchmarks.
"""

import math

import pytest

from backend.app.config.loader import ParameterError
from backend.app.config.models import ParametersConfig, RiskFreeConfig
from backend.app.features.f3_log.institutional_metrics import (
    beta_and_alpha,
    beta_and_alpha_result,
    information_ratio,
    resolve_risk_free_parameters,
    resolve_risk_free_rate,
    tracking_error,
)


def test_beta_and_alpha_hand_computed() -> None:
    """Verify OLS Beta and annualised Alpha against exact hand-computed values.

    Rb = [0.01, 0.02, 0.03] -> Mean = 0.02, Var(ddof=1) = 0.0001
    Rp = 1.5 * Rb + 0.005 = [0.020, 0.035, 0.050] -> Mean = 0.035
    Beta = 1.50, Alpha_period = 0.035 - 1.5 * 0.02 = 0.005
    Annualized with factor=250: Alpha = 0.005 * 250 = 1.25
    """
    rb = [0.01, 0.02, 0.03]
    rp = [0.020, 0.035, 0.050]
    ann_factor = 250.0

    beta, alpha = beta_and_alpha(rp, rb, annualisation_factor=ann_factor)
    assert math.isclose(beta, 1.50, rel_tol=1e-12)
    assert math.isclose(alpha, 1.25, rel_tol=1e-12)


def test_beta_and_alpha_with_risk_free_excess_returns() -> None:
    """Verify Beta and Alpha when deducting risk-free return series."""
    rf = [0.005, 0.005, 0.005]
    rb = [0.015, 0.025, 0.035]  # Excess = [0.01, 0.02, 0.03]
    rp = [0.025, 0.040, 0.055]  # Excess = [0.020, 0.035, 0.050]
    ann_factor = 250.0

    beta, alpha = beta_and_alpha(rp, rb, annualisation_factor=ann_factor, risk_free_returns=rf)
    assert math.isclose(beta, 1.50, rel_tol=1e-12)
    assert math.isclose(alpha, 1.25, rel_tol=1e-12)


def test_beta_zero_variance_benchmark_raises() -> None:
    """Benchmark with zero variance must raise ParameterError."""
    rb = [0.02, 0.02, 0.02]
    rp = [0.01, 0.02, 0.03]
    with pytest.raises(ParameterError, match="Benchmark return variance must be strictly positive"):
        beta_and_alpha(rp, rb, annualisation_factor=250.0)


def test_institutional_metrics_length_and_factor_validation() -> None:
    """Invalid length, mismatched series, or non-positive factor must raise ParameterError."""
    # Fewer than 2 observations
    with pytest.raises(ParameterError, match=">= 2 observations"):
        beta_and_alpha([0.01], [0.01], annualisation_factor=250.0)

    # Mismatched lengths
    with pytest.raises(ParameterError, match="identical length"):
        beta_and_alpha([0.01, 0.02], [0.01, 0.02, 0.03], annualisation_factor=250.0)

    # Non-positive annualisation factor
    with pytest.raises(ParameterError, match="strictly positive"):
        beta_and_alpha([0.01, 0.02], [0.01, 0.02], annualisation_factor=0.0)


def test_tracking_error_hand_computed() -> None:
    """Verify Tracking Error = Std(active, ddof=1) * sqrt(factor).

    Active diff = [0.01, 0.03] -> Mean=0.02, Var(ddof=1)=0.0002
    With factor=250: TE = sqrt(0.0002 * 250) = sqrt(0.05) ~ 0.2236067977
    """
    rb = [0.01, 0.02]
    rp = [0.02, 0.05]
    ann_factor = 250.0

    te = tracking_error(rp, rb, annualisation_factor=ann_factor)
    expected = math.sqrt(0.05)
    assert math.isclose(te, expected, rel_tol=1e-10)


def test_tracking_error_zero_variation_raises() -> None:
    """Active returns with zero standard deviation must raise ParameterError."""
    rb = [0.01, 0.02, 0.03]
    rp = [0.01, 0.02, 0.03]  # diff is constant 0.0
    with pytest.raises(ParameterError, match="tracking error cannot be zero"):
        tracking_error(rp, rb, annualisation_factor=250.0)


def test_information_ratio_hand_computed() -> None:
    """Verify Information Ratio = Mean(active) * factor / Tracking_Error.

    Active diff = [0.01, 0.03] -> Mean = 0.02 * 250 = 5.0
    TE = sqrt(0.05)
    IR = 5.0 / sqrt(0.05) ~ 22.36067977
    """
    rb = [0.01, 0.02]
    rp = [0.02, 0.05]
    ann_factor = 250.0

    ir = information_ratio(rp, rb, annualisation_factor=ann_factor)
    expected = (0.02 * 250.0) / math.sqrt(0.05)
    assert math.isclose(ir, expected, rel_tol=1e-10)


def test_resolve_risk_free_rate_raises() -> None:
    """Resolving unconfigured / null risk-free rate must raise ParameterError."""
    cfg = ParametersConfig(
        risk_free=RiskFreeConfig(value=None, status="pending", source=None, as_of=None),
        parameters={},
    )
    with pytest.raises(ParameterError, match="Risk-free rate is null"):
        resolve_risk_free_rate(cfg)


def test_resolve_risk_free_rate_configured() -> None:
    """Resolving configured risk-free rate returns converted decimal and records parameters."""
    rate = resolve_risk_free_rate()
    assert rate == 0.057281

    params = resolve_risk_free_parameters()
    assert params["value"] == 5.7281
    assert params["unit"] == "percent per annum"
    assert params["source"] == "RBI 91-day T-bill auction cut-off yield (Treasury Bills: Full Auction Result, press release 2026-2027/1326)"
    assert params["as_of"] == "14 October 2026 auction"
    assert params["decimal_rate"] == 0.057281


def test_beta_and_alpha_result_records_risk_free_parameters() -> None:
    """Verify result using risk-free rate records value, unit, source and as_of."""
    rb = [0.01, 0.02, 0.03]
    rp = [0.020, 0.035, 0.050]
    res = beta_and_alpha_result(rp, rb, annualisation_factor=250.0)
    assert math.isclose(res["beta"], 1.50, rel_tol=1e-12)
    assert math.isclose(res["alpha"], 1.25, rel_tol=1e-12)
    p = res["parameters"]
    assert p["value"] == 5.7281
    assert p["unit"] == "percent per annum"
    assert p["source"] == "RBI 91-day T-bill auction cut-off yield (Treasury Bills: Full Auction Result, press release 2026-2027/1326)"
    assert p["as_of"] == "14 October 2026 auction"

