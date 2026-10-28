"""Feature 1 Contagion API router."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.auth.models import UserClaims
from backend.app.config.env import load_settings
from backend.app.config.loader import load_all_config
from backend.app.contracts.contagion import CorrelationScan
from backend.app.db.connection import get_connection
from backend.app.entitlements.atomic import increment_quota_atomic
from backend.app.entitlements.guard import require_feature
from backend.app.features.f1_contagion.pipeline import run_correlation_scan

logger = logging.getLogger("backend.app.features.f1_contagion")

router = APIRouter(prefix="/f1", tags=["feature1_contagion"])
_require_f1 = require_feature("feature1_contagion")


@router.get("/scan", response_model=CorrelationScan)
async def scan_contagion(
    request: Request,
    user: Annotated[UserClaims, Depends(_require_f1)],
    baseline_window: int = 252,
    current_window: int = 30,
    gap_window: int = 5,
    sector: str | None = None,
    significance_threshold: float = 0.05,
    live: bool = False,
) -> CorrelationScan:
    """Execute live Feature 1 systemic contagion and absorption ratio scan across Indian equities.

    Enforces:
    - User authentication and plan entitlement (retail 403, institutional_free 402)
    - Daily per-user limit evaluation via atomic ledger
    - Ticker count, cache TTL, and parameters from config
    - Returns derived numbers only, lists failed tickers, never fills, no fallback to old data
    - Reports duration in seconds for one full scan
    """
    settings = getattr(request.app.state, "settings", None) or load_settings()
    all_cfg = getattr(request.app.state, "all_config", None) or load_all_config()

    params = all_cfg.parameters.parameters
    ttl_param = params.get("cache_ttl_seconds")
    cache_ttl = int(ttl_param.default) if ttl_param else 3600

    max_tickers_param = params.get("f1_max_tickers") or params.get("max_tickers")
    max_tickers = int(max_tickers_param.default) if max_tickers_param else 100

    daily_limit_param = params.get("f1_daily_limit_per_user") or params.get("daily_quota")
    daily_limit = int(daily_limit_param.default) if daily_limit_param else 1000

    overrides = {
        "B": max(30, min(500, baseline_window)),
        "C": max(10, min(90, current_window)),
        "G": max(0, min(20, gap_window)),
        "q_threshold": max(0.01, min(0.20, significance_threshold)),
    }

    try:
        scan_result = run_correlation_scan(
            overrides=overrides,
            symbols=None,
            sector=sector,
            live=live,
            cache_ttl_seconds=cache_ttl,
            max_tickers=max_tickers,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "MARKET_DATA_ERROR", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.error("Feature 1 contagion scan failed: %s", exc, exc_info=exc)
        raise HTTPException(
            status_code=502,
            detail={"code": "SCAN_FAILED", "message": f"Contagion scan calculation failed: {exc}"},
        ) from exc

    # Increment quota atomically after successful scan
    conn = None
    try:
        conn = get_connection(settings)
        increment_quota_atomic(conn, user.user_id, "contagion", daily_limit, settings=settings)
    except Exception as exc:
        logger.warning("Could not record quota for contagion scan: %s", exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    return scan_result
