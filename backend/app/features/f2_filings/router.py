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
from backend.app.features.f2_filings.lookup import (
    UnsupportedCompanyTypeError,
    fetch_nifty50_constituents,
    fetch_nse_equity_list,
    perform_f2_lookup,
    search_nse_equities,
)

logger = logging.getLogger("backend.app.features.f2_filings")

router = APIRouter(prefix="/f2", tags=["feature2_filings"])
_require_f2 = require_feature("feature2_filings")


@router.get("/top50")
async def get_top50_companies(
    request: Request,
    user: UserClaims = Depends(get_current_user),
) -> list[dict[str, str]]:
    """Retrieve official Nifty 50 constituents from NSE archives with TTL cache."""
    settings = getattr(request.app.state, "settings", None) or load_settings()
    all_cfg = getattr(request.app.state, "all_config", None) or load_all_config()
    params = all_cfg.parameters.parameters if all_cfg else {}
    cache_ttl = int(params.get("f2_top50_cache_ttl_seconds").default) if "f2_top50_cache_ttl_seconds" in params else 86400
    rate_limit = float(params.get("nse_global_rate_limit_per_second").default) if "nse_global_rate_limit_per_second" in params else 5.0

    try:
        top50 = fetch_nifty50_constituents(cache_ttl_seconds=cache_ttl, rate_limit_per_sec=rate_limit)
        return top50
    except Exception as exc:
        logger.warning("Failed to fetch Nifty 50 constituents: %s", exc)
        raise HTTPException(
            status_code=502,
            detail={"code": "source_unavailable", "message": f"Failed to load Nifty 50 constituents: {exc}"},
        ) from exc


@router.get("/search")
async def search_companies(
    request: Request,
    q: str = Query(..., description="Company name or NSE equity symbol (min 2 chars)"),
    user: UserClaims = Depends(get_current_user),
) -> list[dict[str, str]]:
    """Search full NSE equity list on server by query (min 2 chars).

    Matches symbol and name (case-insensitive, symbol matches first), at most configured limit results.
    """
    clean_q = q.strip()
    if len(clean_q) < 2:
        raise HTTPException(
            status_code=400,
            detail={"code": "query_too_short", "message": "Search query must be at least 2 characters"},
        )

    settings = getattr(request.app.state, "settings", None) or load_settings()
    all_cfg = getattr(request.app.state, "all_config", None) or load_all_config()
    params = all_cfg.parameters.parameters if all_cfg else {}
    limit = int(params.get("f2_search_result_limit").default) if "f2_search_result_limit" in params else 20
    rate_limit = float(params.get("nse_global_rate_limit_per_second").default) if "nse_global_rate_limit_per_second" in params else 5.0

    try:
        results = search_nse_equities(query=clean_q, limit=limit, rate_limit_per_sec=rate_limit)
        return results
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_search_query", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "source_unavailable", "message": f"Failed to search NSE equity list: {exc}"},
        ) from exc


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
    request: Request,
    company: str = Query(..., min_length=1, description="Company name or NSE equity symbol"),
    period: str = Query(..., min_length=2, description="Fiscal period label (e.g. 'Q1 FY27' or 'Annual')"),
    custom_text: str | None = Query(default=None, description="Optional management commentary snippet to audit"),
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
            custom_text=custom_text,
            rate_limit_per_sec=rate_limit,
            cache_ttl_seconds=cache_ttl,
        )
        daily_limit = int(params.get("f2_daily_limit_per_user").default) if "f2_daily_limit_per_user" in params else 1000
        conn = None
        try:
            conn = get_connection(settings)
            increment_quota_atomic(conn, user.user_id, "filing_consistency", daily_limit, settings=settings)
        except Exception as exc:
            logger.warning("Could not record f2 lookup quota: %s", exc)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
        return result
    except UnsupportedCompanyTypeError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "UNSUPPORTED_COMPANY_TYPE", "message": "financial companies are not covered"},
        ) from exc
    except ValueError as exc:
        err_msg = str(exc)
        if "financial companies are not covered" in err_msg:
            raise HTTPException(
                status_code=422,
                detail={"code": "UNSUPPORTED_COMPANY_TYPE", "message": "financial companies are not covered"},
            ) from exc
        if "not found in official NSE equity list" in err_msg:
            raise HTTPException(
                status_code=404,
                detail={"code": "company_not_found", "message": err_msg},
            ) from exc
        if "no data for" in err_msg:
            available: list[str] = []
            if "Available periods:" in err_msg:
                avail_part = err_msg.split("Available periods:", 1)[1].strip()
                if avail_part and avail_part != "none found":
                    try:
                        import ast
                        val = ast.literal_eval(avail_part)
                        if isinstance(val, list):
                            available = [str(x) for x in val]
                    except Exception:
                        available = [p.strip(" []'\"") for p in avail_part.split(",") if p.strip(" []'\"")]
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "period_not_found",
                    "message": f"No data for {company} in {period}.",
                    "available_periods": available,
                },
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


from pydantic import BaseModel, Field


class TranscriptApiRequest(BaseModel):
    company: str = Field(..., description="Company name or NSE symbol")
    quarter: str = Field(..., description="Reporting quarter (Q1, Q2, Q3, Q4)")
    fiscal_year: str = Field(..., description="Fiscal year (e.g., FY25, FY26)")
    company_domain: str | None = Field(default=None, description="Official company domain")
    output_dir: str = Field(default="./transcripts", description="Target storage directory")


@router.post("/transcript")
async def retrieve_earnings_transcript(
    request: Request,
    body: TranscriptApiRequest,
    user: UserClaims = Depends(get_current_user),
    _entitled: None = Depends(_require_f2),
) -> dict[str, Any]:
    """Retrieve, validate, and archive an official earnings call transcript."""
    settings = getattr(request.app.state, "settings", None) or load_settings()
    from backend.app.features.f2_filings.transcript_retriever import (
        TranscriptRequest,
        TranscriptRetrievalAgent,
    )

    agent = TranscriptRetrievalAgent(settings=settings)
    req = TranscriptRequest(
        company=body.company,
        quarter=body.quarter,
        fiscal_year=body.fiscal_year,
        company_domain=body.company_domain,
        output_dir=body.output_dir,
    )
    result = agent.retrieve(req)
    if result.get("status") == "not_found":
        raise HTTPException(
            status_code=404,
            detail={
                "code": "transcript_not_found",
                "message": f"No valid transcript found for {body.company} {body.quarter} {body.fiscal_year}",
                "report": result.get("report"),
            },
        )
    return result

