"""Known-answer tests for entitlement decisions, quota arithmetic, and reset boundaries."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.config.loader import load_all_config
from backend.app.entitlements.decision import (
    EntitlementDecision,
    calculate_reset_time,
    decide,
)


@pytest.fixture
def plans_config():
    """Load real plans configuration."""
    return load_all_config().plans


@pytest.fixture
def sample_now():
    """Generate fixed timezone-aware timestamp for deterministic testing."""
    return datetime.fromtimestamp(1_000_000, tz=timezone.utc)


def test_reset_time_boundary_just_before_and_at_midnight():
    """Verify reset time boundary just before midnight and exactly at midnight UTC."""
    base_dt = datetime.fromtimestamp(1_000_000, tz=timezone.utc)
    midnight = base_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    just_before_midnight = midnight - timedelta(microseconds=1)

    # Just before midnight: reset time is current day's midnight
    reset_before = calculate_reset_time(just_before_midnight, "utc_calendar_day")
    assert reset_before == midnight

    # Exactly at midnight: reset time is next day's midnight
    reset_at = calculate_reset_time(midnight, "utc_calendar_day")
    assert reset_at == midnight + timedelta(days=1)


def test_calculate_reset_time_rejects_naive_datetime():
    """Naive datetime must raise ValueError."""
    naive_dt = datetime.fromtimestamp(1_000_000)
    with pytest.raises(ValueError, match="Naive datetime"):
        calculate_reset_time(naive_dt, "utc_calendar_day")


def test_calculate_reset_time_rejects_unknown_rule(sample_now):
    """Unsupported reset rule must raise ValueError."""
    with pytest.raises(ValueError, match="Unsupported reset rule"):
        calculate_reset_time(sample_now, "unsupported_rule")


@pytest.mark.parametrize(
    "plan,feature,expected_status,expected_decision,expected_allowed",
    [
        # Retail Free
        ("retail_free", "feature1_contagion", 403, "denied", False),
        ("retail_free", "feature2_filings", 200, "limited", True),
        ("retail_free", "feature3_forensic", 200, "limited", True),
        # Retail Paid
        ("retail_paid", "feature1_contagion", 403, "denied", False),
        ("retail_paid", "feature2_filings", 200, "full", True),
        ("retail_paid", "feature3_forensic", 200, "full", True),
        # Institutional Free
        ("institutional_free", "feature1_contagion", 402, "denied", False),
        ("institutional_free", "feature2_filings", 200, "limited", True),
        ("institutional_free", "feature3_forensic", 200, "limited", True),
        # Institutional Paid
        ("institutional_paid", "feature1_contagion", 200, "full", True),
        ("institutional_paid", "feature2_filings", 200, "limited", True),
        ("institutional_paid", "feature3_forensic", 200, "limited", True),
        # Judge All
        ("judge_all", "feature1_contagion", 200, "full", True),
        ("judge_all", "feature2_filings", 200, "full", True),
        ("judge_all", "feature3_forensic", 200, "full", True),
    ],
)
def test_all_plan_x_feature_combinations(
    plans_config,
    sample_now,
    plan,
    feature,
    expected_status,
    expected_decision,
    expected_allowed,
):
    """Verify all 15 plan x feature combinations under zero usage."""
    result: EntitlementDecision = decide(
        plan=plan,
        feature=feature,
        usage=0,
        now=sample_now,
        plans_config=plans_config,
    )
    assert result.status == expected_status
    assert result.decision == expected_decision
    assert result.allowed is expected_allowed

    if expected_status == 402:
        assert result.upgrade_targets is not None
        assert len(result.upgrade_targets) > 0
        assert "judge_all" not in result.upgrade_targets
    elif expected_status == 403:
        assert result.upgrade_targets is None


def test_quota_boundaries_limit_minus_one_at_limit_over_limit(plans_config, sample_now):
    """Verify quota boundary arithmetic: limit minus one, at limit, and over limit."""
    # retail_free on feature2_filings has daily quota 3
    plan = "retail_free"
    feature = "feature2_filings"
    quota = plans_config.plans[plan].features[feature].quota_per_day
    assert quota == 3

    # Limit minus one (usage 2 of 3) -> allowed 200, remaining 1
    res_minus_one = decide(
        plan, feature, usage=quota - 1, now=sample_now, plans_config=plans_config
    )
    assert res_minus_one.allowed is True
    assert res_minus_one.decision == "limited"
    assert res_minus_one.status == 200
    assert res_minus_one.remaining_quota == 1
    assert res_minus_one.reset_time is not None

    # At limit (usage 3 of 3) -> denied 429, remaining 0
    res_at_limit = decide(plan, feature, usage=quota, now=sample_now, plans_config=plans_config)
    assert res_at_limit.allowed is False
    assert res_at_limit.decision == "denied"
    assert res_at_limit.status == 429
    assert res_at_limit.remaining_quota == 0
    assert res_at_limit.reset_time is not None
    assert "exceeded" in res_at_limit.reason.lower()

    # Over limit (usage 4 of 3) -> denied 429, remaining 0
    res_over_limit = decide(
        plan, feature, usage=quota + 1, now=sample_now, plans_config=plans_config
    )
    assert res_over_limit.allowed is False
    assert res_over_limit.decision == "denied"
    assert res_over_limit.status == 429
    assert res_over_limit.remaining_quota == 0
    assert res_over_limit.reset_time is not None


def test_institutional_f1_upgrade_offer(plans_config, sample_now):
    """institutional_free on feature1 must offer upgrade to institutional_paid with status 402."""
    res = decide("institutional_free", "feature1_contagion", 0, sample_now, plans_config)
    assert res.status == 402
    assert res.allowed is False
    assert res.upgrade_targets == ["institutional_paid"]


def test_retail_f1_hard_deny(plans_config, sample_now):
    """retail plans on feature1 must hard deny with status 403 and no upgrade offer."""
    for plan in ("retail_free", "retail_paid"):
        res = decide(plan, "feature1_contagion", 0, sample_now, plans_config)
        assert res.status == 403
        assert res.allowed is False
        assert res.upgrade_targets is None


def test_judge_all_is_never_purchasable_and_never_upgrade_target(plans_config):
    """judge_all must not be purchasable and must never be referenced by unlocks_with."""
    assert plans_config.plans["judge_all"].purchasable is False

    for plan_name, plan in plans_config.plans.items():
        for feat_name, feat in plan.features.items():
            assert feat.unlocks_with != "judge_all", f"{plan_name}.{feat_name} references judge_all"


def test_error_unknown_plan(plans_config, sample_now):
    """Unknown plan name must raise ValueError."""
    with pytest.raises(ValueError, match="Unknown plan"):
        decide("non_existent_plan", "feature1_contagion", 0, sample_now, plans_config)


def test_error_unknown_feature(plans_config, sample_now):
    """Unknown feature name must raise ValueError."""
    with pytest.raises(ValueError, match="Unknown feature"):
        decide("retail_free", "non_existent_feature", 0, sample_now, plans_config)


def test_error_negative_usage(plans_config, sample_now):
    """Negative usage value must raise ValueError."""
    with pytest.raises(ValueError, match="Negative usage"):
        decide("retail_free", "feature2_filings", -1, sample_now, plans_config)


def test_error_naive_datetime(plans_config):
    """Naive datetime must raise ValueError in decide."""
    naive_dt = datetime.fromtimestamp(1_000_000)
    with pytest.raises(ValueError, match="Naive datetime"):
        decide("retail_free", "feature2_filings", 0, naive_dt, plans_config)


def test_institutional_paid_f3_quota_enforced(plans_config, sample_now):
    """institutional_paid on feature3_forensic allows within daily quota 5 and rejects above."""
    # Under quota (usage 0 out of 5)
    res_allowed = decide("institutional_paid", "feature3_forensic", 0, sample_now, plans_config)
    assert res_allowed.allowed is True
    assert res_allowed.status == 200

    # At quota (usage 5 out of 5)
    res_limited = decide("institutional_paid", "feature3_forensic", 5, sample_now, plans_config)
    assert res_limited.allowed is False
    assert res_limited.status == 429


def test_no_plan_x_feature_is_pending(plans_config):
    """Verify that no plan feature has quota_per_day as pending after resolution."""
    pending_items = []
    for plan_name, plan in plans_config.plans.items():
        for feat_name, feat in plan.features.items():
            if feat.quota_per_day == "pending":
                pending_items.append((plan_name, feat_name))

    assert pending_items == []


def test_schema_rejects_pending_marker_on_other_plans():
    """Schema must reject quota_per_day='pending' on any other plan or feature."""
    from backend.app.config.models import PlansConfig

    invalid_plans = {
        "reset_rule": "utc_calendar_day",
        "plans": {
            "retail_free": {
                "segment": "retail",
                "purchasable": True,
                "price_inr_per_month": 0,
                "features": {
                    "feature1_contagion": {"access": "none"},
                    "feature2_filings": {"access": "limited", "quota_per_day": "pending"},
                    "feature3_forensic": {"access": "limited", "quota_per_day": 1},
                },
            },
            "judge_all": {
                "segment": "internal",
                "purchasable": False,
                "price_inr_per_month": None,
                "features": {
                    "feature1_contagion": {"access": "full"},
                    "feature2_filings": {"access": "full"},
                    "feature3_forensic": {"access": "full"},
                },
            },
        },
    }
    with pytest.raises(ValueError, match="Quota pending marker is only permitted"):
        PlansConfig.model_validate(invalid_plans)
