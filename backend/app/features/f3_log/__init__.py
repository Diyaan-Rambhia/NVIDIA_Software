"""Feature 3 Investment Log Advisor package."""

from backend.app.features.f3_log.institutional_metrics import (
    beta_and_alpha,
    beta_and_alpha_result,
    information_ratio,
    resolve_risk_free_parameters,
    resolve_risk_free_rate,
    tracking_error,
)
from backend.app.features.f3_log.process_metrics import (
    concentration_hhi,
    disposition_effect,
    max_drawdown,
    turnover,
)
from backend.app.features.f3_log.xirr import (
    DAYS_PER_YEAR,
    MultipleRootsError,
    XIRRConvergenceError,
    XIRRError,
    XIRRSignError,
    xirr,
)

__all__ = [
    "DAYS_PER_YEAR",
    "MultipleRootsError",
    "XIRRConvergenceError",
    "XIRRError",
    "XIRRSignError",
    "beta_and_alpha",
    "beta_and_alpha_result",
    "concentration_hhi",
    "disposition_effect",
    "information_ratio",
    "max_drawdown",
    "resolve_risk_free_parameters",
    "resolve_risk_free_rate",
    "tracking_error",
    "turnover",
    "xirr",
]
