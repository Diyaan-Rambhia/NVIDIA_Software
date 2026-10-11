"""Pure entitlement and quota decision logic."""

from datetime import datetime, time, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.app.config.models import PlansConfig


class EntitlementDecision(BaseModel):
    """Internal decision outcome model for entitlement checks."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    decision: Literal["full", "limited", "denied"]
    status: int
    reason: str | None = None
    remaining_quota: int | None = None
    reset_time: datetime | None = None
    upgrade_targets: list[str] | None = None


def calculate_reset_time(now: datetime, reset_rule: str) -> datetime:
    """Calculate the next quota reset timestamp from a timezone-aware datetime.

    Reset cadence is driven by configuration (e.g. 'utc_calendar_day').
    """
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ValueError("Naive datetime is not permitted; timezone-aware datetime required")

    now_utc = now.astimezone(timezone.utc)

    if reset_rule == "utc_calendar_day":
        next_date = now_utc.date() + timedelta(days=1)
        return datetime.combine(next_date, time.min, tzinfo=timezone.utc)

    raise ValueError(f"Unsupported reset rule: '{reset_rule}'")


def decide(
    plan: str,
    feature: str,
    usage: int,
    now: datetime,
    plans_config: PlansConfig | None = None,
) -> EntitlementDecision:
    """Evaluate feature entitlement, quota availability, or upgrade requirement.

    Pure function: no external services, no database, no system clock reading.
    """
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ValueError("Naive datetime is not permitted; timezone-aware datetime required")

    if usage < 0:
        raise ValueError(f"Negative usage is not permitted: {usage}")

    if plans_config is None:
        from backend.app.config.loader import load_all_config

        plans_config = load_all_config().plans

    if plan not in plans_config.plans:
        raise ValueError(
            f"Unknown plan: '{plan}'. Allowed plans: {sorted(plans_config.plans.keys())}"
        )

    plan_entry = plans_config.plans[plan]

    if feature not in plan_entry.features:
        raise ValueError(
            f"Unknown feature: '{feature}'. Allowed features: {sorted(plan_entry.features.keys())}"
        )

    feat_rule = plan_entry.features[feature]

    if feat_rule.quota_per_day == "pending":
        raise ValueError(
            f"Plan '{plan}' feature '{feature}': quota pending advisor confirmation"
        )

    if feat_rule.access == "full":
        return EntitlementDecision(
            allowed=True,
            decision="full",
            status=200,
            remaining_quota=None,
            reset_time=None,
            upgrade_targets=None,
        )

    if feat_rule.access == "limited":
        quota = feat_rule.quota_per_day
        if quota is None:
            raise ValueError(
                f"Plan '{plan}' feature '{feature}' configured as limited but lacks quota_per_day"
            )
        reset_time = calculate_reset_time(now, plans_config.reset_rule)
        if usage < quota:
            remaining = quota - usage
            return EntitlementDecision(
                allowed=True,
                decision="limited",
                status=200,
                remaining_quota=remaining,
                reset_time=reset_time,
                upgrade_targets=None,
            )
        return EntitlementDecision(
            allowed=False,
            decision="denied",
            status=429,
            reason=f"Daily quota of {quota} exceeded. Resets at {reset_time.isoformat()}",
            remaining_quota=0,
            reset_time=reset_time,
            upgrade_targets=None,
        )

    if feat_rule.access == "locked":
        target = feat_rule.unlocks_with
        if not target:
            raise ValueError(
                f"Plan '{plan}' feature '{feature}' configured as locked but lacks unlocks_with"
            )
        reason = (
            f"Feature '{feature}' is locked on plan '{plan}'. "
            f"Upgrade to '{target}' to unlock."
        )
        return EntitlementDecision(
            allowed=False,
            decision="denied",
            status=402,
            reason=reason,
            remaining_quota=None,
            reset_time=None,
            upgrade_targets=[target],
        )

    if feat_rule.access == "none":
        reason = (
            f"Feature '{feature}' is unavailable to segment '{plan_entry.segment}' at any price."
        )
        return EntitlementDecision(
            allowed=False,
            decision="denied",
            status=403,
            reason=reason,
            remaining_quota=None,
            reset_time=None,
            upgrade_targets=None,
        )

    raise ValueError(f"Unhandled access type: '{feat_rule.access}'")
