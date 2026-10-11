"""Known-answer and property-based test suite for Feature 1 estimators.

Tests rolling covariance/correlation, EWMA covariance, Ledoit-Wolf shrinkage,
Forbes-Rigobon adjustment, Spearman rank correlation, and absorption ratio.
Adheres strictly to AGENTS.md rules (no dates, no mocks, real known-answers).
"""

import math

import numpy as np
import pytest

from backend.app.features.f1_contagion.estimators import (
    absorption_ratio,
    compute_ar_k,
    cov_to_corr,
    ewma_correlation,
    ewma_covariance,
    forbes_rigobon_adjust,
    ledoit_wolf_correlation,
    ledoit_wolf_covariance,
    rolling_correlation,
    rolling_covariance,
    spearman_correlation,
    standardized_absorption_ratio_shift,
)

# ---------------------------------------------------------------------------
# cov_to_corr tests
# ---------------------------------------------------------------------------


def test_cov_to_corr_known_answer() -> None:
    """Verify covariance to correlation conversion on hand-computed 2x2 matrix."""
    cov = np.array([[4.0, 1.2], [1.2, 9.0]])
    corr = cov_to_corr(cov)

    assert math.isclose(corr[0, 0], 1.0, abs_tol=1e-12)
    assert math.isclose(corr[1, 1], 1.0, abs_tol=1e-12)
    assert math.isclose(corr[0, 1], 0.20, rel_tol=1e-12)
    assert math.isclose(corr[1, 0], 0.20, rel_tol=1e-12)


def test_cov_to_corr_invalid_inputs_raise() -> None:
    """Non-square, non-finite, or non-positive variance must raise ValueError."""
    with pytest.raises(ValueError, match="2D square"):
        cov_to_corr(np.array([1.0, 2.0]))

    with pytest.raises(ValueError, match="non-finite"):
        cov_to_corr(np.array([[1.0, float("nan")], [float("nan"), 1.0]]))

    with pytest.raises(ValueError, match="positive variance"):
        cov_to_corr(np.array([[0.0, 0.0], [0.0, 1.0]]))


# ---------------------------------------------------------------------------
# Rolling Covariance and Correlation tests
# ---------------------------------------------------------------------------


def test_rolling_covariance_no_lookahead() -> None:
    """Verify rolling covariance uses trailing window and ignores past outside window."""
    rng = np.random.default_rng(42)
    returns = rng.normal(0, 0.01, size=(70, 3))

    cov1 = rolling_covariance(returns, window=60)
    assert cov1.shape == (3, 3)

    # Mutate observation at index 0 (outside trailing window of 60 observations)
    returns_mutated = returns.copy()
    returns_mutated[0, :] = 999.0

    cov2 = rolling_covariance(returns_mutated, window=60)
    assert np.allclose(cov1, cov2, atol=1e-12)


def test_rolling_covariance_known_manual_slice() -> None:
    """Verify rolling covariance equals direct numpy sample covariance over slice."""
    rng = np.random.default_rng(101)
    returns = rng.normal(0, 0.02, size=(65, 2))

    cov = rolling_covariance(returns, window=60)
    expected = np.cov(returns[-60:], rowvar=False, ddof=1)
    assert np.allclose(cov, expected, atol=1e-12)

    corr = rolling_correlation(returns, window=60)
    assert math.isclose(corr[0, 0], 1.0, abs_tol=1e-12)
    assert math.isclose(corr[1, 1], 1.0, abs_tol=1e-12)


def test_rolling_covariance_bounds_and_length_enforcement() -> None:
    """Enforce window bounds from config and reject insufficient history."""
    rng = np.random.default_rng(7)
    returns = rng.normal(0, 0.01, size=(30, 2))

    # Window smaller than W min (configured min is 20)
    with pytest.raises(ValueError, match="outside configured bounds"):
        rolling_covariance(returns, window=10)

    # Window larger than W max (configured max is 500)
    with pytest.raises(ValueError, match="outside configured bounds"):
        rolling_covariance(returns, window=600)

    # History shorter than requested window
    with pytest.raises(ValueError, match="less than required estimation window"):
        rolling_covariance(returns, window=50)


# ---------------------------------------------------------------------------
# EWMA Covariance and Correlation tests
# ---------------------------------------------------------------------------


def test_ewma_covariance_initialization_and_recursion() -> None:
    """Verify EWMA initialization from first W observations and recursive step."""
    t_steps = 62
    initial_w = 60
    decay = 0.94

    rng = np.random.default_rng(123)
    returns = rng.normal(0, 0.01, size=(t_steps, 2))

    ewma_cov = ewma_covariance(returns, lambda_=decay, initial_window=initial_w)

    # Manual step-by-step reproduction
    sigma = np.cov(returns[:initial_w], rowvar=False, ddof=1)
    for t in range(initial_w, t_steps):
        r_t = returns[t : t + 1]
        sigma = decay * sigma + (1.0 - decay) * (r_t.T @ r_t)

    assert np.allclose(ewma_cov, sigma, atol=1e-12)

    ewma_corr = ewma_correlation(returns, lambda_=decay, initial_window=initial_w)
    assert math.isclose(ewma_corr[0, 0], 1.0, abs_tol=1e-12)
    assert math.isclose(ewma_corr[1, 1], 1.0, abs_tol=1e-12)


def test_ewma_bounds_enforcement() -> None:
    """Enforce lambda and initial window bounds from parameters.yaml."""
    returns = np.zeros((70, 2))

    # lambda out of bounds (configured bounds: 0.80 to 0.99)
    with pytest.raises(ValueError, match="outside configured bounds"):
        ewma_covariance(returns, lambda_=0.50, initial_window=60)

    with pytest.raises(ValueError, match="outside configured bounds"):
        ewma_covariance(returns, lambda_=1.05, initial_window=60)

    # initial_window out of bounds (W bounds: 20 to 500)
    with pytest.raises(ValueError, match="outside configured bounds"):
        ewma_covariance(returns, lambda_=0.94, initial_window=10)


# ---------------------------------------------------------------------------
# Ledoit-Wolf Shrinkage tests
# ---------------------------------------------------------------------------


def test_ledoit_wolf_covariance_and_correlation() -> None:
    """Verify Ledoit-Wolf produces valid positive definite covariance and bounded shrinkage."""
    rng = np.random.default_rng(456)
    returns = rng.normal(0, 0.01, size=(65, 4))

    cov, shrinkage = ledoit_wolf_covariance(returns, window=60)
    assert cov.shape == (4, 4)
    assert 0.0 <= shrinkage <= 1.0

    corr, s2 = ledoit_wolf_correlation(returns, window=60)
    assert math.isclose(s2, shrinkage, abs_tol=1e-12)
    for i in range(4):
        assert math.isclose(corr[i, i], 1.0, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# Forbes-Rigobon Adjustment tests
# ---------------------------------------------------------------------------


def test_forbes_rigobon_hand_computed() -> None:
    """Verify exact formula against hand-computed example.

    With rho = 0.5, var_high = 2.0, var_low = 1.0:
    delta = 2.0 / 1.0 - 1.0 = 1.0
    denom = sqrt(1 + 1.0 * (1 - 0.25)) = sqrt(1.75) ~ 1.3228756555
    rho* = 0.5 / sqrt(1.75) ~ 0.3779644730
    """
    rho = 0.5
    var_high = 2.0
    var_low = 1.0
    expected = 0.5 / math.sqrt(1.75)

    res = forbes_rigobon_adjust(rho, var_high=var_high, var_low=var_low)
    assert math.isclose(res, expected, rel_tol=1e-12)

    # Direct delta argument
    res_delta = forbes_rigobon_adjust(rho, delta=1.0)
    assert math.isclose(res_delta, expected, rel_tol=1e-12)


def test_forbes_rigobon_identity_when_delta_non_positive() -> None:
    """Identity check: when delta <= 0, adjustment must return rho exactly."""
    # Variance decreased (delta < 0)
    res1 = forbes_rigobon_adjust(0.65, var_high=0.8, var_low=1.0)
    assert math.isclose(res1, 0.65, abs_tol=1e-12)

    # Variance unchanged (delta == 0)
    res2 = forbes_rigobon_adjust(0.65, delta=0.0)
    assert math.isclose(res2, 0.65, abs_tol=1e-12)

    # Negative delta directly
    res3 = forbes_rigobon_adjust(-0.40, delta=-0.25)
    assert math.isclose(res3, -0.40, abs_tol=1e-12)


def test_forbes_rigobon_invalid_inputs_raise() -> None:
    """Reject correlation out of [-1, 1] or non-positive baseline variance."""
    with pytest.raises(ValueError, match=r"in \[-1, 1\]"):
        forbes_rigobon_adjust(1.5, delta=1.0)

    with pytest.raises(ValueError, match="strictly positive"):
        forbes_rigobon_adjust(0.5, var_high=1.0, var_low=0.0)


# ---------------------------------------------------------------------------
# Spearman Rank Correlation tests
# ---------------------------------------------------------------------------


def test_spearman_monotonic_relationship() -> None:
    """Spearman correlation of monotonically increasing series must equal 1.0."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([1.0, 8.0, 27.0, 64.0, 125.0])  # Non-linear cubic

    spearman = spearman_correlation(x, y)
    assert math.isclose(spearman, 1.0, abs_tol=1e-12)


def test_spearman_matrix_evaluation() -> None:
    """Spearman correlation on 2D matrix returns pairwise correlation matrix."""
    x = np.array([
        [1.0, 10.0],
        [2.0, 9.0],
        [3.0, 8.0],
        [4.0, 7.0],
        [5.0, 6.0],
    ])
    corr = spearman_correlation(x)
    assert isinstance(corr, np.ndarray)
    assert corr.shape == (2, 2)
    assert math.isclose(corr[0, 0], 1.0, abs_tol=1e-12)
    assert math.isclose(corr[1, 1], 1.0, abs_tol=1e-12)
    assert math.isclose(corr[0, 1], -1.0, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# Absorption Ratio tests (Known-Answer Checks per §5.5)
# ---------------------------------------------------------------------------


def test_absorption_ratio_identity_gives_k_over_n() -> None:
    """Known-answer check (§5.5): Identity matrix of size N gives AR = k / N."""
    n = 10
    identity_mat = np.eye(n)

    for k in range(1, n + 1):
        ar = absorption_ratio(identity_mat, k=k)
        expected = k / n
        assert math.isclose(ar, expected, abs_tol=1e-12)


def test_absorption_ratio_rank_one_gives_one() -> None:
    """Known-answer check (§5.5): Rank-one matrix gives AR = 1.0 for any k >= 1."""
    n = 6
    # Matrix of all ones has rank 1 with sole non-zero eigenvalue equal to n
    rank_one_mat = np.ones((n, n))

    for k in range(1, n + 1):
        ar = absorption_ratio(rank_one_mat, k=k)
        assert math.isclose(ar, 1.0, abs_tol=1e-12)


def test_absorption_ratio_k_is_required_argument() -> None:
    """Component count k must be a required argument with no default in Python."""
    mat = np.eye(5)
    with pytest.raises(TypeError):
        absorption_ratio(mat)  # type: ignore[call-arg]


def test_absorption_ratio_invalid_k_raises() -> None:
    """k < 1 or k > N must raise ValueError."""
    mat = np.eye(5)
    with pytest.raises(ValueError, match="must satisfy 1 <= k <= 5"):
        absorption_ratio(mat, k=0)

    with pytest.raises(ValueError, match="must satisfy 1 <= k <= 5"):
        absorption_ratio(mat, k=6)


def test_compute_ar_k_from_config() -> None:
    """Derive k from configured k_fraction without numeric literals in Python."""
    # Default k_fraction is 0.20
    assert compute_ar_k(10) == 2
    assert compute_ar_k(5) == 1
    assert compute_ar_k(11) == 3

    # Bounds enforcement (configured bounds: 0.10 to 0.50)
    with pytest.raises(ValueError, match="outside configured bounds"):
        compute_ar_k(10, k_fraction=0.05)

    with pytest.raises(ValueError, match="outside configured bounds"):
        compute_ar_k(10, k_fraction=0.60)


def test_standardized_absorption_ratio_shift() -> None:
    """Verify Delta AR calculation on hand-computed synthetic series."""
    # Series of 260 observations: 245 of 0.20 followed by 15 of 0.80
    ar_series = np.array([0.20] * 245 + [0.80] * 15)
    short_w = 15
    long_w = 250

    delta_ar = standardized_absorption_ratio_shift(
        ar_series,
        short_window=short_w,
        long_window=long_w,
    )

    expected_short_mean = 0.80
    long_slice = ar_series[-long_w:]
    expected_long_mean = float(np.mean(long_slice))
    expected_long_std = float(np.std(long_slice, ddof=1))
    expected_delta = (expected_short_mean - expected_long_mean) / expected_long_std

    assert math.isclose(delta_ar, expected_delta, rel_tol=1e-12)


def test_standardized_absorption_ratio_shift_bounds_and_invariants() -> None:
    """Window bounds and invariants for Delta AR must be enforced."""
    series = np.ones(300) * 0.5

    # Short window >= long window (short_window=60 and long_window=60 are both within bounds)
    with pytest.raises(ValueError, match="strictly less than"):
        standardized_absorption_ratio_shift(series, short_window=60, long_window=60)

    # Series shorter than long window
    with pytest.raises(ValueError, match="less than required long_window"):
        standardized_absorption_ratio_shift(series[:100], short_window=15, long_window=250)
