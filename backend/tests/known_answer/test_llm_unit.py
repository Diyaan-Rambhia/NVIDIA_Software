"""Unit tests for LLM gateway components, guards, budgeting, and cache."""

import pytest

from backend.app.llm.cache import make_cache_key
from backend.app.llm.exceptions import (
    BudgetExceededError,
    FinancialAdviceError,
    ModelResolutionError,
)
from backend.app.llm.guard import assert_no_financial_advice
from backend.app.llm.ledger import calculate_cost_usd, check_budget_guard
from backend.app.llm.registry import match_alias_to_model


def test_advice_guard_detects_prohibited_recommendations() -> None:
    """Advice guard raises FinancialAdviceError on buy/sell/hold directives."""
    prohibited_samples = [
        "We recommend you buy shares of Reliance.",
        "Our rating for this equity is Strong Buy.",
        "Recommendation: sell the position immediately.",
        "You should consider selling stock in this sector.",
        "We advise to hold options until expiry.",
        "The model suggests holding shares of HDFC Bank.",
    ]
    for sample in prohibited_samples:
        with pytest.raises(FinancialAdviceError):
            assert_no_financial_advice(sample)


def test_advice_guard_allows_factual_analytical_statements() -> None:
    """Factual, non-advisory statements pass advice inspection."""
    clean_samples = [
        "Revenue from operations increased by 14.2% YoY.",
        "The absorption ratio shifted by 2.1 standard deviations.",
        "The company reported net profit of 2400 crore INR.",
        "A cluster correlation was identified across the banking sector.",
        "",
    ]
    for sample in clean_samples:
        assert_no_financial_advice(sample)


def test_cost_calculation_matches_exact_formula() -> None:
    """Cost calculation in USD correctly computes proportional pricing per 1M tokens."""
    # 1000 input tokens at $1.00/1M = $0.001
    # 2000 output tokens at $3.00/1M = $0.006
    # Total = $0.007
    cost = calculate_cost_usd(1000, 2000, 1.00, 3.00)
    assert cost == 0.007

    # Zero tokens = $0.0
    assert calculate_cost_usd(0, 0, 1.00, 3.00) == 0.0


def test_budget_guard_raises_when_exceeded() -> None:
    """check_budget_guard raises BudgetExceededError when projected cost exceeds limit."""
    from unittest.mock import MagicMock

    conn = MagicMock()
    # Mock current spent = 5.0
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("backend.app.llm.ledger.get_today_spent_usd", lambda c: 5.0)

        # Limit is 5.5, projected is 0.6 -> 5.6 > 5.5 -> raises
        with pytest.raises(BudgetExceededError):
            check_budget_guard(conn, projected_cost_usd=0.6, daily_budget_usd=5.5)

        # Limit is 6.0, projected is 0.5 -> 5.5 <= 6.0 -> passes
        check_budget_guard(conn, projected_cost_usd=0.5, daily_budget_usd=6.0)


def test_model_alias_resolution_matches_substrings() -> None:
    """Aliases resolve to appropriate catalog entries based on preferred substrings."""
    alias_cfg = {
        "fast": {"preferred_substrings": ["nemotron-nano", "nano"]},
        "mid": {"preferred_substrings": ["nemotron-super", "super"]},
        "deep": {"preferred_substrings": ["nemotron-ultra", "ultra"]},
    }
    catalog = [
        "meta-llama/Llama-3-8B",
        "nvidia/nemotron-3-nano-it",
        "nvidia/nemotron-3-super-it",
        "nvidia/nemotron-3-ultra-it",
    ]

    assert match_alias_to_model("fast", catalog, alias_cfg) == "nvidia/nemotron-3-nano-it"
    assert match_alias_to_model("mid", catalog, alias_cfg) == "nvidia/nemotron-3-super-it"
    assert match_alias_to_model("deep", catalog, alias_cfg) == "nvidia/nemotron-3-ultra-it"


def test_model_alias_resolution_raises_when_unresolvable() -> None:
    """If no live catalog model matches alias preferences, ModelResolutionError is raised."""
    alias_cfg = {
        "deep": {"preferred_substrings": ["nemotron-ultra", "ultra"]},
    }
    catalog = ["openai/gpt-4o-mini", "meta-llama/Llama-3-8b"]

    with pytest.raises(ModelResolutionError):
        match_alias_to_model("deep", catalog, alias_cfg)


def test_deterministic_cache_key() -> None:
    """Cache keys are deterministic and sensitive to arguments."""
    k1 = make_cache_key("model-1", [{"role": "user", "content": "hi"}], {"temp": 0.0})
    k2 = make_cache_key("model-1", [{"role": "user", "content": "hi"}], {"temp": 0.0})
    k3 = make_cache_key("model-1", [{"role": "user", "content": "hello"}], {"temp": 0.0})

    assert k1 == k2
    assert k1 != k3


def test_pending_model_pricing_raises() -> None:
    """When a model's price is blank/null/pending, get_pricing raises ModelResolutionError."""
    from backend.app.llm.registry import ModelRegistry

    registry = ModelRegistry()
    registry.aliases_cfg = {
        "fast": {"price_per_1m_input_usd": None, "price_per_1m_output_usd": None}
    }
    with pytest.raises(ModelResolutionError):
        registry.get_pricing("fast")
