"""Entitlements API routes."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import UserClaims
from backend.app.config import load_all_config
from backend.app.config.env import load_settings
from backend.app.db.connection import get_connection
from backend.app.entitlements.atomic import get_today_usage
from backend.app.entitlements.decision import decide

router = APIRouter(prefix="/api/entitlements", tags=["entitlements"])

# Mapping between config feature names and db usage feature names
FEATURE_DB_MAP = {
    "feature1_contagion": "contagion",
    "feature2_filings": "filing_consistency",
    "feature3_forensic": "investment_log",
}


class FeatureEntitlementDetail(BaseModel):
    """Status of a specific feature entitlement."""

    model_config = ConfigDict(extra="forbid")

    state: str
    decision: str
    status: int
    allowed: bool
    remaining_quota: int | None = None
    reset_time: datetime | None = None
    upgrade_targets: list[str] | None = None
    reason: str | None = None


class EntitlementsResponse(BaseModel):
    """Response payload for GET /api/entitlements."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    plan: str
    segment: str
    features: dict[str, FeatureEntitlementDetail]


@router.get("", response_model=EntitlementsResponse)
def get_user_entitlements(
    user: Annotated[UserClaims, Depends(get_current_user)],
    request: Request,
) -> EntitlementsResponse:
    """Return entitlement statuses and remaining quotas for authenticated user."""
    settings = getattr(request.app.state, "settings", None) or load_settings()
    all_cfg = getattr(request.app.state, "all_config", None) or load_all_config()
    plans_cfg = all_cfg.plans

    conn = get_connection(settings)
    try:
        # Load user plan and segment from profiles
        with conn.cursor() as cur:
            cur.execute(
                "SELECT plan, segment FROM public.profiles WHERE user_id = %s;",
                (user.user_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "profile_not_found", "message": "User profile not found"},
                )
            plan, segment = row

        now_utc = datetime.now(timezone.utc)
        features_result: dict[str, FeatureEntitlementDetail] = {}

        for feat_name in ["feature1_contagion", "feature2_filings", "feature3_forensic"]:
            db_feat = FEATURE_DB_MAP.get(feat_name, feat_name)
            usage = get_today_usage(conn, user.user_id, db_feat)

            dec = decide(plan, feat_name, usage, now_utc, plans_config=plans_cfg)

            if dec.status == 200 and dec.decision == "full":
                state = "allowed"
            elif dec.status == 200 and dec.decision == "limited":
                state = "limited"
            elif dec.status == 429:
                state = "limited"  # quota exceeded
            elif dec.status == 402:
                state = "upgrade_available"
            elif dec.status == 403:
                state = "segment_restricted"
            else:
                state = dec.decision

            features_result[feat_name] = FeatureEntitlementDetail(
                state=state,
                decision=dec.decision,
                status=dec.status,
                allowed=dec.allowed,
                remaining_quota=dec.remaining_quota,
                reset_time=dec.reset_time,
                upgrade_targets=dec.upgrade_targets,
                reason=dec.reason,
            )

    finally:
        conn.close()

    return EntitlementsResponse(
        user_id=str(user.user_id),
        plan=plan,
        segment=segment,
        features=features_result,
    )
