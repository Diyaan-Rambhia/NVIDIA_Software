"""Pure statistical and correlation estimators for Feature 1 Contagion Detector.

Implements covariance estimation, Forbes-Rigobon adjustment, Spearman rank correlation,
and absorption ratio calculations per PROJECT.md §5 and AGENTS.md rules.
"""

import math
from pathlib import Path

import numpy as np
import scipy.stats
from sklearn.covariance import ledoit_wolf

from backend.app.config.env import get_repo_root
from backend.app.config.loader import load_config_file
from backend.app.config.models import ParameterEntry, ParametersConfig

_DEFAULT_CONFIG_PATH = get_repo_root() / "config" / "parameters.yaml"


def get_parameters_config(config_path: Path | None = None) -> ParametersConfig:
    """Load parameter specifications from parameters.yaml without hardcoded bounds."""
    target_path = config_path if config_path is not None else _DEFAULT_CONFIG_PATH
    return load_config_file(target_path, ParametersConfig)


def get_parameter_def(name: str, config: ParametersConfig | None = None) -> ParameterEntry:
    """Retrieve parameter definition from loaded configuration."""
    cfg = config if config is not None else get_parameters_config()
    if name not in cfg.parameters:
        raise KeyError(f"Parameter '{name}' not found in configuration")
    return cfg.parameters[name]


def validate_parameter_bounds(
    name: str,
    value: int | float,
    config: ParametersConfig | None = None,
) -> None:
    """Validate numeric parameter value against its configuration bounds."""
    entry = get_parameter_def(name, config)
    if entry.min is not None and entry.max is not None:
        if not (entry.min <= value <= entry.max):
            raise ValueError(
                f"Parameter '{name}' value {value} is outside configured bounds "
                f"[{entry.min}, {entry.max}]"
            )


def cov_to_corr(cov: np.ndarray) -> np.ndarray:
    """Convert a 2D square covariance matrix into a correlation matrix."""
    if not isinstance(cov, np.ndarray):
        cov = np.asarray(cov, dtype=float)

    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        raise ValueError(f"Covariance matrix must be 2D square, got shape {cov.shape}")

    if not np.all(np.isfinite(cov)):
        raise ValueError("Covariance matrix contains non-finite values (NaN or Inf)")

    diag = np.diag(cov)
    if np.any(diag <= 0.0):
        raise ValueError("Covariance matrix diagonal contains non-positive variance values")

    stds = np.sqrt(diag)
    corr = cov / np.outer(stds, stds)
    np.fill_diagonal(corr, 1.0)
    return np.clip(corr, -1.0, 1.0)


def rolling_covariance(
    returns: np.ndarray,
    window: int | None = None,
    config: ParametersConfig | None = None,
) -> np.ndarray:
    """Estimate rolling sample covariance over the trailing window without lookahead."""
    if not isinstance(returns, np.ndarray):
        returns = np.asarray(returns, dtype=float)

    if returns.ndim != 2:
        raise ValueError(f"Returns array must be 2D with shape (T, N), got ndim={returns.ndim}")

    if not np.all(np.isfinite(returns)):
        raise ValueError("Returns array contains non-finite values (NaN or Inf)")

    if window is None:
        window = int(get_parameter_def("W", config).default)

    validate_parameter_bounds("W", window, config)

    n_obs = returns.shape[0]
    if n_obs < window:
        raise ValueError(
            f"Available history length {n_obs} is less than required estimation window {window}"
        )

    window_slice = returns[-window:]
    cov = np.cov(window_slice, rowvar=False, ddof=1)
    if returns.shape[1] == 1:
        return np.array([[float(cov)]], dtype=float)
    return cov


def rolling_correlation(
    returns: np.ndarray,
    window: int | None = None,
    config: ParametersConfig | None = None,
) -> np.ndarray:
    """Estimate rolling sample correlation over trailing window."""
    cov = rolling_covariance(returns, window=window, config=config)
    return cov_to_corr(cov)


def ewma_covariance(
    returns: np.ndarray,
    lambda_: float | None = None,
    initial_window: int | None = None,
    config: ParametersConfig | None = None,
) -> np.ndarray:
    """Estimate exponentially weighted moving average (EWMA) covariance matrix.

    Initialised from the sample covariance of the first W observations per PROJECT.md §5.2,
    then updated recursively via Sigma_t = lambda * Sigma_{t-1} + (1 - lambda) * r_t r_t^T.
    """
    if not isinstance(returns, np.ndarray):
        returns = np.asarray(returns, dtype=float)

    if returns.ndim != 2:
        raise ValueError(f"Returns array must be 2D with shape (T, N), got ndim={returns.ndim}")

    if not np.all(np.isfinite(returns)):
        raise ValueError("Returns array contains non-finite values (NaN or Inf)")

    if lambda_ is None:
        lambda_ = float(get_parameter_def("lambda", config).default)

    validate_parameter_bounds("lambda", lambda_, config)

    if initial_window is None:
        initial_window = int(get_parameter_def("W", config).default)

    validate_parameter_bounds("W", initial_window, config)

    n_obs = returns.shape[0]
    if n_obs < initial_window:
        raise ValueError(
            f"Available observations {n_obs} is less than initial EWMA window {initial_window}"
        )

    init_slice = returns[:initial_window]
    cov = np.cov(init_slice, rowvar=False, ddof=1)
    if returns.shape[1] == 1:
        sigma = np.array([[float(cov)]], dtype=float)
    else:
        sigma = np.asarray(cov, dtype=float)

    for t in range(initial_window, n_obs):
        r_t = returns[t : t + 1]
        outer = r_t.T @ r_t
        sigma = lambda_ * sigma + (1.0 - lambda_) * outer

    return sigma


def ewma_correlation(
    returns: np.ndarray,
    lambda_: float | None = None,
    initial_window: int | None = None,
    config: ParametersConfig | None = None,
) -> np.ndarray:
    """Estimate EWMA correlation matrix."""
    cov = ewma_covariance(
        returns,
        lambda_=lambda_,
        initial_window=initial_window,
        config=config,
    )
    return cov_to_corr(cov)


def ledoit_wolf_covariance(
    returns: np.ndarray,
    window: int | None = None,
    config: ParametersConfig | None = None,
) -> tuple[np.ndarray, float]:
    """Estimate Ledoit-Wolf shrunken covariance matrix over trailing window."""
    if not isinstance(returns, np.ndarray):
        returns = np.asarray(returns, dtype=float)

    if returns.ndim != 2:
        raise ValueError(f"Returns array must be 2D with shape (T, N), got ndim={returns.ndim}")

    if not np.all(np.isfinite(returns)):
        raise ValueError("Returns array contains non-finite values (NaN or Inf)")

    if window is not None:
        validate_parameter_bounds("W", window, config)
        if returns.shape[0] < window:
            raise ValueError(
                f"Available observations {returns.shape[0]} less than window {window}"
            )
        data = returns[-window:]
    else:
        data = returns

    shrunk_cov, shrinkage = ledoit_wolf(data, assume_centered=False)
    return shrunk_cov, float(shrinkage)


def ledoit_wolf_correlation(
    returns: np.ndarray,
    window: int | None = None,
    config: ParametersConfig | None = None,
) -> tuple[np.ndarray, float]:
    """Estimate Ledoit-Wolf correlation matrix and shrinkage intensity."""
    cov, shrinkage = ledoit_wolf_covariance(returns, window=window, config=config)
    return cov_to_corr(cov), shrinkage


def forbes_rigobon_adjust(
    rho: float,
    delta: float | None = None,
    var_high: float | None = None,
    var_low: float | None = None,
) -> float:
    """Adjust correlation for volatility bias per Forbes and Rigobon (PROJECT.md §5.3).

    Formula: rho* = rho / sqrt(1 + delta * (1 - rho^2))
    where delta = var_high / var_low - 1. If delta <= 0, returns rho (identity).
    """
    if not isinstance(rho, (int, float)) or not math.isfinite(rho):
        raise ValueError(f"Correlation rho must be a finite number, got {rho}")

    if not (-1.0 <= rho <= 1.0):
        raise ValueError(f"Correlation rho must be in [-1, 1], found: {rho}")

    if delta is None:
        if var_high is None or var_low is None:
            raise ValueError("Either delta or both var_high and var_low must be provided")
        if not math.isfinite(var_high) or not math.isfinite(var_low):
            raise ValueError("Variance values must be finite numbers")
        if var_low <= 0.0:
            raise ValueError(f"Baseline variance var_low must be strictly positive, got {var_low}")
        if var_high < 0.0:
            raise ValueError(
                f"High-volatility variance var_high cannot be negative, got {var_high}"
            )
        delta = (var_high / var_low) - 1.0

    if not math.isfinite(delta):
        raise ValueError(f"Relative variance shift delta must be finite, got {delta}")

    if delta <= 0.0:
        return float(rho)

    denom_sq = 1.0 + delta * (1.0 - (rho**2))
    if denom_sq <= 0.0:
        raise ValueError(f"Invalid non-positive denominator under root: {denom_sq}")

    adjusted = rho / math.sqrt(denom_sq)
    return float(np.clip(adjusted, -1.0, 1.0))


def spearman_correlation(
    x: np.ndarray,
    y: np.ndarray | None = None,
) -> float | np.ndarray:
    """Calculate Spearman rank correlation as robustness check against volatility bias."""
    if not isinstance(x, np.ndarray):
        x = np.asarray(x, dtype=float)

    if not np.all(np.isfinite(x)):
        raise ValueError("Input array x contains non-finite values")

    if y is not None:
        if not isinstance(y, np.ndarray):
            y = np.asarray(y, dtype=float)
        if not np.all(np.isfinite(y)):
            raise ValueError("Input array y contains non-finite values")
        if len(x) != len(y):
            raise ValueError(f"Arrays x (len {len(x)}) and y (len {len(y)}) length mismatch")
        res = scipy.stats.spearmanr(x, y)
        stat = getattr(res, "statistic", None)
        if stat is None:
            stat = res.correlation
        return float(stat)

    res = scipy.stats.spearmanr(x, axis=0)
    matrix = getattr(res, "statistic", None)
    if matrix is None:
        matrix = res.correlation
    arr = np.asarray(matrix, dtype=float)
    if arr.ndim == 0:
        val = float(arr)
        return np.array([[1.0, val], [val, 1.0]], dtype=float)
    return arr


def compute_ar_k(
    n_assets: int,
    k_fraction: float | None = None,
    config: ParametersConfig | None = None,
) -> int:
    """Calculate absorption ratio component count k from configured k_fraction."""
    if n_assets <= 0:
        raise ValueError(f"Number of assets must be positive, got {n_assets}")

    if k_fraction is None:
        k_fraction = float(get_parameter_def("k_fraction", config).default)

    validate_parameter_bounds("k_fraction", k_fraction, config)

    k = int(math.ceil(n_assets * k_fraction))
    return max(1, min(k, n_assets))


def absorption_ratio(
    matrix: np.ndarray,
    k: int,
) -> float:
    """Calculate absorption ratio measuring systemic variance concentration.

    AR = sum_{i=1..k} lambda_i / sum_{i=1..N} lambda_i
    where lambda_i are sorted eigenvalues of the matrix (correlation or covariance).
    Component count k is a required argument with no hardcoded default.
    """
    if not isinstance(matrix, np.ndarray):
        matrix = np.asarray(matrix, dtype=float)

    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"Matrix must be 2D square, got shape {matrix.shape}")

    if not np.all(np.isfinite(matrix)):
        raise ValueError("Matrix contains non-finite values")

    n = matrix.shape[0]
    if not isinstance(k, int) or isinstance(k, bool):
        raise ValueError(f"Component count k must be an integer, got {type(k).__name__}")

    if not (1 <= k <= n):
        raise ValueError(f"Component count k must satisfy 1 <= k <= {n}, got {k}")

    eigenvals = np.linalg.eigvalsh(matrix)
    eigenvals = np.sort(eigenvals)[::-1]

    total_var = float(np.sum(eigenvals))
    if total_var <= 0.0:
        raise ValueError(f"Sum of eigenvalues must be strictly positive, got {total_var}")

    explained_var = float(np.sum(eigenvals[:k]))
    return float(explained_var / total_var)


def standardized_absorption_ratio_shift(
    ar_series: np.ndarray,
    short_window: int | None = None,
    long_window: int | None = None,
    config: ParametersConfig | None = None,
) -> float:
    """Calculate standardized absorption ratio shift Delta AR.

    Delta AR = (mean AR over AR_short - mean AR over AR_long) / std AR over AR_long
    """
    if not isinstance(ar_series, np.ndarray):
        ar_series = np.asarray(ar_series, dtype=float)

    if ar_series.ndim != 1:
        raise ValueError(f"ar_series must be 1D array, got ndim={ar_series.ndim}")

    if not np.all(np.isfinite(ar_series)):
        raise ValueError("ar_series contains non-finite values")

    if short_window is None:
        short_window = int(get_parameter_def("AR_short", config).default)

    validate_parameter_bounds("AR_short", short_window, config)

    if long_window is None:
        long_window = int(get_parameter_def("AR_long", config).default)

    validate_parameter_bounds("AR_long", long_window, config)

    if short_window >= long_window:
        raise ValueError(
            f"short_window ({short_window}) must be strictly less than "
            f"long_window ({long_window})"
        )

    if len(ar_series) < long_window:
        raise ValueError(
            f"ar_series length {len(ar_series)} is less than required long_window {long_window}"
        )

    short_mean = float(np.mean(ar_series[-short_window:]))
    long_mean = float(np.mean(ar_series[-long_window:]))
    long_std = float(np.std(ar_series[-long_window:], ddof=1))

    if long_std <= 0.0 or not math.isfinite(long_std):
        raise ValueError("Long window absorption ratio has zero or non-finite standard deviation")

    return float((short_mean - long_mean) / long_std)
