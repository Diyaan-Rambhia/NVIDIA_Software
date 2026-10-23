"""Feature 2 Filing Consistency API router."""

import json
import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import UserClaims
from backend.app.config.env import load_settings
from backend.app.config.loader import load_all_config
from backend.app.db.connection import get_connection
from backend.app.entitlements.atomic import get_today_usage, increment_quota_atomic
from backend.app.entitlements.guard import require_feature
from backend.app.features.f2_filings.lookup import fetch_nse_equity_list, perform_f2_lookup

logger = logging.getLogger("backend.app.features.f2_filings")

router = APIRouter(prefix="/f2", tags=["feature2_filings"])
_require_f2 = require_feature("feature2_filings")


@router.get("/companies")
async def list_companies(
    user: UserClaims = Depends(get_current_user),
) -> list[dict[str, str]]:
    """Retrieve official list of listed equities from NSE archives, with caching.

    Returns symbol and name for autocomplete suggestions in the filings audit view.
    Raises 502 source_unavailable if the NSE archives service cannot be reached.
    """
    try:
        equities = fetch_nse_equity_list()
        return equities
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "source_unavailable", "message": f"Failed to load NSE equity list: {exc}"},
        ) from exc


@router.get("/lookup")
async def lookup_filing(
    company: str = Query(..., min_length=1, description="Company name or NSE equity symbol"),
    period: str = Query(..., min_length=2, description="Fiscal period label (e.g. 'Q1 FY27' or 'Annual')"),
    request: Request = None,
    user: UserClaims = Depends(_require_f2),
) -> dict[str, Any]:
    """Find company by name or symbol and audit reported XBRL metrics against consistency rules.

    Enforces:
    - User authentication and feature2_filings entitlement
    - Configured per-user daily lookup limit
    - Configured global NSE archive request rate limit
    - Server cache with TTL from configuration
    - Clear errors for missing period or source unavailable
    - Operating cash flow rules evaluate on annual data only
    - Never returns raw XML files
    """
    settings = getattr(request.app.state, "settings", None) or load_settings()
    all_cfg = getattr(request.app.state, "all_config", None) or load_all_config()

    params = all_cfg.parameters.parameters if all_cfg else {}
    rate_limit = float(params.get("nse_global_rate_limit_per_second").default) if "nse_global_rate_limit_per_second" in params else 5.0
    cache_ttl = int(params.get("f2_lookup_cache_ttl_seconds").default) if "f2_lookup_cache_ttl_seconds" in params else 86400

    try:
        result = perform_f2_lookup(
            company_query=company,
            period_query=period,
            rate_limit_per_sec=rate_limit,
            cache_ttl_seconds=cache_ttl,
        )
        daily_limit = int(params.get("f2_daily_limit_per_user").default) if "f2_daily_limit_per_user" in params else 1000
        try:
            conn = get_connection(settings)
            increment_quota_atomic(conn, user.user_id, "filing_consistency", daily_limit)
            conn.close()
        except Exception as exc:
            logger.warning("Could not record f2 lookup quota: %s", exc)
        return result
    except ValueError as exc:
        err_msg = str(exc)
        if "not found in official NSE equity list" in err_msg:
            raise HTTPException(
                status_code=404,
                detail={"code": "company_not_found", "message": err_msg},
            ) from exc
        if "no data for" in err_msg:
            raise HTTPException(
                status_code=404,
                detail={"code": "period_not_found", "message": err_msg},
            ) from exc
        if "Invalid fiscal period" in err_msg:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_period_format", "message": err_msg},
            ) from exc
        raise HTTPException(
            status_code=400,
            detail={"code": "lookup_error", "message": err_msg},
        ) from exc
    except RuntimeError as exc:
        err_msg = str(exc)
        if "source unavailable" in err_msg:
            raise HTTPException(
                status_code=503,
                detail={"code": "source_unavailable", "message": err_msg},
            ) from exc
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_lookup_error", "message": err_msg},
        ) from exc
