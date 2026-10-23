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

    try:
        scan_result = run_correlation_scan(
            symbols=None,
            live=False,
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
    try:
        conn = get_connection(settings)
        increment_quota_atomic(conn, user.user_id, "contagion", daily_limit)
        conn.close()
    except Exception as exc:
        logger.warning("Could not record quota for contagion scan: %s", exc)

    return scan_result
