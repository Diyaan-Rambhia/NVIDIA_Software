"""Entitlement and quota evaluation dependency for API routes."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import UserClaims
from backend.app.config import load_all_config
from backend.app.config.env import load_settings
from backend.app.db.connection import get_connection
from backend.app.entitlements.atomic import get_today_usage
from backend.app.entitlements.decision import decide

FEATURE_DB_MAP = {
    "feature1_contagion": "contagion",
    "feature2_filings": "filing_consistency",
    "feature3_forensic": "investment_log",
}


def require_feature(feature_key: str) -> Callable[..., UserClaims]:
    """Return a dependency requiring active entitlement for feature_key."""

    async def _dependency(
        request: Request,
        user: Annotated[UserClaims, Depends(get_current_user)],
    ) -> UserClaims:
        settings = getattr(request.app.state, "settings", None) or load_settings()
        all_cfg = getattr(request.app.state, "all_config", None) or load_all_config()

        db_feature = FEATURE_DB_MAP.get(feature_key, feature_key)
        usage = 0
        conn = None
        try:
            conn = get_connection(settings)
            usage = get_today_usage(conn, user.user_id, db_feature, settings=settings)
        except Exception:
            usage = 0
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        now = datetime.now(timezone.utc)
        decision = decide(
            plan=user.plan,
            feature=feature_key,
            usage=usage,
            now=now,
            plans_config=all_cfg.plans,
        )

        if not decision.allowed:
            raise HTTPException(
                status_code=decision.status,
                detail={
                    "code": decision.decision,
                    "message": decision.reason,
                    "upgrade_targets": decision.upgrade_targets,
                    "reset_time": decision.reset_time.isoformat() if decision.reset_time else None,
                },
            )

        return user

    return _dependency
