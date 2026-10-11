"""Known-answer tests for infrastructure logic per PROGRESS.md A3."""

from pathlib import Path

import pytest

from backend.app.config.loader import ParameterError
from backend.app.infra.budget_guard import (
    BudgetExceededError,
    ModelPrice,
    UnknownModelPriceError,
    calculate_call_cost,
    check_budget_guard,
)
from backend.app.infra.cache_key import compute_cache_key
from backend.app.infra.cost_report import (
    UsageRecord,
    aggregate_cost_report,
)

# ---------------------------------------------------------------------------
# 1. Response-Cache Key Tests
# ---------------------------------------------------------------------------


def test_cache_key_determinism() -> None:
    """Same inputs must always produce the exact same cache key."""
    key1 = compute_cache_key(
        model="deep",
        prompt="Analyze revenue consistency for Q3 FY25.",
        parameters={"temperature": 0.0, "max_tokens": 1000},
        data_version="digest_v1",
    )
    key2 = compute_cache_key(
        model="deep",
        prompt="Analyze revenue consistency for Q3 FY25.",
        parameters={"temperature": 0.0, "max_tokens": 1000},
        data_version="digest_v1",
    )
    assert key1 == key2
    assert len(key1) == 64  # SHA-256 hex string


def test_cache_key_parameter_order_independence() -> None:
    """Parameter dictionary key ordering must not change the computed cache key."""
    key_order_a = compute_cache_key(
        model="fast",
        prompt="Extract claims from text chunk.",
        parameters={"temperature": 0.1, "top_p": 0.95, "seed": 42},
        data_version="v2.0",
    )
    key_order_b = compute_cache_key(
        model="fast",
        prompt="Extract claims from text chunk.",
        parameters={"seed": 42, "temperature": 0.1, "top_p": 0.95},
        data_version="v2.0",
    )
    assert key_order_a == key_order_b


def test_cache_key_sensitivity_to_each_input() -> None:
    """Any variation in model, prompt, parameters, or data_version produces a different key."""
    base = compute_cache_key(
        model="mid",
        prompt="Summarize disclosures.",
        parameters={"temperature": 0.2},
        data_version="v1",
    )

    diff_model = compute_cache_key(
        model="deep",
        prompt="Summarize disclosures.",
        parameters={"temperature": 0.2},
        data_version="v1",
    )
    assert base != diff_model

    diff_prompt = compute_cache_key(
        model="mid",
        prompt="Summarize disclosures today.",
        parameters={"temperature": 0.2},
        data_version="v1",
    )
    assert base != diff_prompt

    diff_params = compute_cache_key(
        model="mid",
        prompt="Summarize disclosures.",
        parameters={"temperature": 0.3},
        data_version="v1",
    )
    assert base != diff_params

    diff_data = compute_cache_key(
        model="mid",
        prompt="Summarize disclosures.",
        parameters={"temperature": 0.2},
        data_version="v2",
    )
    assert base != diff_data


# ---------------------------------------------------------------------------
# 2. Budget Guard Tests
# ---------------------------------------------------------------------------


def test_budget_guard_under_limit_passes() -> None:
    """Spend below limit minus one cent passes."""
    # Spend $0.99, call cost $0.00, limit $1.00 -> total $0.99 < $1.00
    assert check_budget_guard(
        spend_so_far=0.99,
        estimated_cost=0.00,
        daily_limit=1.00,
    ) is True

    # Spend $0.50, call cost $0.49, limit $1.00 -> total $0.99 < $1.00
    assert check_budget_guard(
        spend_so_far=0.50,
        estimated_cost=0.49,
        daily_limit=1.00,
    ) is True


def test_budget_guard_at_limit_refuses() -> None:
    """At the limit exactly refuses with BudgetExceededError."""
    # Spend $0.50, call cost $0.50, limit $1.00 -> total $1.00 >= $1.00
    with pytest.raises(BudgetExceededError) as exc:
        check_budget_guard(
            spend_so_far=0.50,
            estimated_cost=0.50,
            daily_limit=1.00,
        )
    assert exc.value.spend_so_far == 0.50
    assert exc.value.estimated_cost == 0.50
    assert exc.value.limit == 1.00
    assert isinstance(exc.value, ParameterError)


def test_budget_guard_over_limit_refuses() -> None:
    """Over the limit refuses with BudgetExceededError."""
    # Spend $0.95, call cost $0.10, limit $1.00 -> total $1.05 >= $1.00
    with pytest.raises(BudgetExceededError):
        check_budget_guard(
            spend_so_far=0.95,
            estimated_cost=0.10,
            daily_limit=1.00,
        )


def test_budget_guard_test_limit_selection() -> None:
    """Caller passes test limit ($0.10) versus production limit ($1.00)."""
    # Allowed under production ($1.00) but refused under test limit ($0.10)
    assert check_budget_guard(spend_so_far=0.05, estimated_cost=0.04, daily_limit=1.00) is True

    with pytest.raises(BudgetExceededError):
        check_budget_guard(spend_so_far=0.05, estimated_cost=0.06, daily_limit=0.10)


def test_budget_guard_invalid_inputs_raise() -> None:
    """Negative spend, negative cost, or non-positive limit raise ParameterError."""
    with pytest.raises(ParameterError) as exc1:
        check_budget_guard(spend_so_far=-0.01, estimated_cost=0.05, daily_limit=1.00)
    assert exc1.value.field == "spend_so_far"

    with pytest.raises(ParameterError) as exc2:
        check_budget_guard(spend_so_far=0.10, estimated_cost=-0.01, daily_limit=1.00)
    assert exc2.value.field == "estimated_cost"

    with pytest.raises(ParameterError) as exc3:
        check_budget_guard(spend_so_far=0.10, estimated_cost=0.01, daily_limit=0.0)
    assert exc3.value.field == "daily_limit"


# ---------------------------------------------------------------------------
# 3. Model Pricing Calculation Tests
# ---------------------------------------------------------------------------


def test_calculate_call_cost_hand_computed() -> None:
    """Call cost equals hand-computed arithmetic using supplied prices."""
    pricing = {
        "fast": ModelPrice(input_price_per_million=0.20, output_price_per_million=0.80),
        "deep": {"input_price_per_million": 2.00, "output_price_per_million": 6.00},
    }

    # Fast: 50,000 input @ $0.20/M = $0.01; 10,000 output @ $0.80/M = $0.008 -> total $0.018
    cost_fast = calculate_call_cost(
        "fast", input_tokens=50_000, output_tokens=10_000, pricing_table=pricing
    )
    assert abs(cost_fast - 0.018) < 1e-9

    # Deep: 1,000,000 input @ $2.00/M = $2.00; 500,000 output @ $6.00/M = $3.00 -> total $5.00
    cost_deep = calculate_call_cost(
        "deep", input_tokens=1_000_000, output_tokens=500_000, pricing_table=pricing
    )
    assert abs(cost_deep - 5.00) < 1e-9


def test_calculate_call_cost_unknown_or_pending_raises() -> None:
    """Unknown model or pending price raises UnknownModelPriceError."""
    pricing = {
        "fast": ModelPrice(input_price_per_million=0.20, output_price_per_million=0.80),
        "pending_model": "pending",
        "none_model": None,
    }

    with pytest.raises(UnknownModelPriceError) as exc1:
        calculate_call_cost("unregistered_model", 100, 100, pricing_table=pricing)
    assert exc1.value.model == "unregistered_model"
    assert isinstance(exc1.value, ParameterError)

    with pytest.raises(UnknownModelPriceError):
        calculate_call_cost("pending_model", 100, 100, pricing_table=pricing)

    with pytest.raises(UnknownModelPriceError):
        calculate_call_cost("none_model", 100, 100, pricing_table=pricing)


def test_calculate_call_cost_negative_tokens_raises() -> None:
    """Negative token count raises ParameterError."""
    pricing = {"fast": ModelPrice(input_price_per_million=0.20, output_price_per_million=0.80)}
    with pytest.raises(ParameterError):
        calculate_call_cost("fast", input_tokens=-10, output_tokens=5, pricing_table=pricing)


# ---------------------------------------------------------------------------
# 4. Cost Report Aggregation Tests
# ---------------------------------------------------------------------------


def test_cost_report_aggregation_hand_computed() -> None:
    """Aggregates usage records by model and day with exact hand-computed totals."""
    records = [
        UsageRecord(
            timestamp="2026-03-01T10:15:00Z",
            model="fast",
            input_tokens=10_000,
            output_tokens=2_000,
            cost_usd=0.0036,
            cache_hit=False,
        ),
        UsageRecord(
            timestamp="2026-03-01T14:30:00Z",
            model="fast",
            input_tokens=5_000,
            output_tokens=1_000,
            cost_usd=0.0018,
            cache_hit=True,
        ),
        UsageRecord(
            timestamp="2026-03-02T09:00:00Z",
            model="deep",
            input_tokens=20_000,
            output_tokens=5_000,
            cost_usd=0.0700,
            cache_hit=False,
        ),
    ]

    report = aggregate_cost_report(records)

    # Total spend: 0.0036 + 0.0018 + 0.0700 = 0.0754
    assert report.total_spend_usd == 0.0754
    assert report.total_calls == 3
    assert report.total_input_tokens == 35_000
    assert report.total_output_tokens == 8_000
    assert report.cache_hits == 1
    assert report.cache_misses == 2

    # Per model breakdowns
    assert "fast" in report.by_model
    fast_summary = report.by_model["fast"]
    assert fast_summary.call_count == 2
    assert fast_summary.input_tokens == 15_000
    assert fast_summary.output_tokens == 3_000
    assert fast_summary.cost_usd == 0.0054
    assert fast_summary.cache_hits == 1

    assert "deep" in report.by_model
    deep_summary = report.by_model["deep"]
    assert deep_summary.call_count == 1
    assert deep_summary.input_tokens == 20_000
    assert deep_summary.output_tokens == 5_000
    assert deep_summary.cost_usd == 0.0700
    assert deep_summary.cache_hits == 0

    # Per day breakdowns (UTC calendar days)
    assert "2026-03-01" in report.by_day
    day1 = report.by_day["2026-03-01"]
    assert day1.call_count == 2
    assert day1.cost_usd == 0.0054
    assert day1.cache_hits == 1

    assert "2026-03-02" in report.by_day
    day2 = report.by_day["2026-03-02"]
    assert day2.call_count == 1
    assert day2.cost_usd == 0.0700
    assert day2.cache_hits == 0


def test_cost_report_computes_cost_from_pricing_table() -> None:
    """When record.cost_usd is None, calculates cost via pricing table."""
    pricing = {"fast": ModelPrice(input_price_per_million=1.00, output_price_per_million=2.00)}
    records = [
        UsageRecord(
            timestamp="2026-04-10T11:00:00Z",
            model="fast",
            input_tokens=1_000_000,
            output_tokens=500_000,
            cost_usd=None,  # needs calculation: $1.00 + $1.00 = $2.00
            cache_hit=False,
        )
    ]
    report = aggregate_cost_report(records, pricing_table=pricing)
    assert report.total_spend_usd == 2.00
    assert report.by_model["fast"].cost_usd == 2.00


# ---------------------------------------------------------------------------
# 5. Dockerfile & .dockerignore Static Verification Tests
# ---------------------------------------------------------------------------


def test_dockerfile_and_dockerignore_configuration() -> None:
    """Verify Dockerfile runs create_app factory and .dockerignore protects secrets."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    dockerfile_path = repo_root / "Dockerfile"
    dockerignore_path = repo_root / ".dockerignore"

    assert dockerfile_path.is_file()
    assert dockerignore_path.is_file()

    dockerfile_content = dockerfile_path.read_text(encoding="utf-8")
    assert "uvicorn" in dockerfile_content
    assert "backend.app.main:create_app" in dockerfile_content
    assert "--factory" in dockerfile_content
    # Ensures .env is never explicitly copied
    assert "COPY .env" not in dockerfile_content

    dockerignore_content = dockerignore_path.read_text(encoding="utf-8")
    assert ".env" in dockerignore_content
    assert ".env.*" in dockerignore_content
    assert "private/" in dockerignore_content
    assert "data/" in dockerignore_content
