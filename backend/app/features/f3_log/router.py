"""Feature 3 Investment Log Advisor API router."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from backend.app.auth.models import UserClaims
from backend.app.config.env import load_settings
from backend.app.contracts.portfolio import ColumnMapping, DecisionReview
from backend.app.db.connection import get_connection
from backend.app.entitlements.atomic import increment_quota_atomic
from backend.app.entitlements.guard import require_feature
from backend.app.features.f3_log.pipeline import (
    execute_feature3_review,
    parse_trade_log_csv,
)

router = APIRouter(prefix="/f3", tags=["feature3_forensic"])
_require_f3 = require_feature("feature3_forensic")


class F3ReviewRequest(BaseModel):
    """Payload for POST /f3/review."""

    model_config = ConfigDict(extra="forbid")

    csv_text: str
    mapping: ColumnMapping
    consent_given: bool = False
    benchmark_symbol: str = "NSEI"
    matched_index_symbol: str | None = None


@router.post("/review", response_model=DecisionReview)
async def review_trade_log(
    req: F3ReviewRequest,
    request: Request,
    user: Annotated[UserClaims, Depends(_require_f3)],
) -> DecisionReview:
    """Parse uploaded real trade log CSV, compute XIRR and metrics, and return DecisionReview."""


    try:
        trade_log = parse_trade_log_csv(
            csv_text=req.csv_text,
            mapping=req.mapping,
            consent_given=req.consent_given,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "trade_log_invalid", "message": str(exc)},
        ) from exc

    is_institutional = user.segment == "institutional" or "institutional" in user.plan

    try:
        review = execute_feature3_review(
            trade_log=trade_log,
            is_institutional=is_institutional,
            benchmark_symbol=req.benchmark_symbol,
            matched_index_symbol=req.matched_index_symbol,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "benchmark_data_error", "message": str(exc)},
        ) from exc

    # Record atomic usage
    try:
        settings = getattr(request.app.state, "settings", None) or load_settings()
        conn = get_connection(settings)
        increment_quota_atomic(conn, user.user_id, "investment_log", max_quota=999999)
        conn.close()
    except Exception:
        pass

    return review
