"""Feature 1 Contagion Detector package."""

from backend.app.features.f1_contagion.bootstrap import (
    BootstrapResult,
    moving_block_bootstrap,
)
from backend.app.features.f1_contagion.estimators import (
    absorption_ratio,
    compute_ar_k,
    cov_to_corr,
    ewma_correlation,
    ewma_covariance,
    forbes_rigobon_adjust,
    get_parameter_def,
    get_parameters_config,
    ledoit_wolf_correlation,
    ledoit_wolf_covariance,
    rolling_correlation,
    rolling_covariance,
    spearman_correlation,
    standardized_absorption_ratio_shift,
    validate_parameter_bounds,
)

__all__ = [
    "BootstrapResult",
    "absorption_ratio",
    "compute_ar_k",
    "cov_to_corr",
    "ewma_correlation",
    "ewma_covariance",
    "forbes_rigobon_adjust",
    "get_parameter_def",
    "get_parameters_config",
    "ledoit_wolf_correlation",
    "ledoit_wolf_covariance",
    "moving_block_bootstrap",
    "rolling_correlation",
    "rolling_covariance",
    "spearman_correlation",
    "standardized_absorption_ratio_shift",
    "validate_parameter_bounds",
]
