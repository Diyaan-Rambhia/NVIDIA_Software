"""Tests for nullable cost in llm_ledger, AgentStep contract, and orchestrator response."""

import uuid
from typing import Any

import pytest

from backend.app.agent.orchestrator import run_agent_loop
from backend.app.auth.models import UserClaims
from backend.app.config.env import load_settings
from backend.app.config.loader import load_all_config
from backend.app.contracts.agent import AgentStep
from backend.app.db.connection import get_connection
from backend.app.llm.ledger import record_llm_call


def test_ledger_row_null_cost_written_and_read_back() -> None:
    """A ledger row with cost = null is written to public.llm_ledger and read back."""
    settings = load_settings()
    conn = get_connection(settings, autocommit=True)
    test_user_id = None
    test_route = "/test/agent/null_cost"
    try:
        ledger_id = record_llm_call(
            conn=conn,
            user_id=test_user_id,
            route=test_route,
            alias="fast",
            model_id="test-null-cost-model",
            input_tokens=100,
            output_tokens=50,
            est_cost_usd=None,
            cache_hit=False,
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT est_cost_usd, input_tokens, output_tokens FROM public.llm_ledger WHERE id = %s;",
                (ledger_id,),
            )
            row = cur.fetchone()
            assert row is not None, "Ledger row should be found in database"
            assert row[0] is None, f"Expected est_cost_usd to be None, got {row[0]}"
            assert row[1] == 100
            assert row[2] == 50
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.llm_ledger WHERE route = %s;", (test_route,))
        conn.close()


def test_agent_step_with_cost_null_validates() -> None:
    """An AgentStep with cost null validates under StrictContractModel."""
    step = AgentStep(
        step_number=1,
        tool_name="f2_filings_lookup",
        input_summary="lookup(company=TCS, period=Q1 FY25)",
        output_summary="Success: verified 3 metrics",
        status="success",
        est_cost_usd=None,
        duration_ms=45.2,
    )
    assert step.est_cost_usd is None
    dumped = step.model_dump()
    assert dumped["est_cost_usd"] is None
    restored = AgentStep.model_validate(dumped)
    assert restored.est_cost_usd is None


def test_agent_loop_with_test_provider_helper_finishes_with_unknown_cost() -> None:
    """The agent loop with a test provider helper without tier price returns cost 'unknown'."""
    settings = load_settings()
    all_config = load_all_config()
    conn = get_connection(settings, autocommit=True)

    with conn.cursor() as cur:
        cur.execute("SELECT id, email FROM auth.users LIMIT 1;")
        user_row = cur.fetchone()
        real_user_id = user_row[0] if user_row else uuid.uuid4()
        real_email = user_row[1] if user_row else "judge@example.com"

    user = UserClaims(
        user_id=real_user_id,
        email=real_email,
        role="judge",
        plan="judge_all",
        segment="internal",
        is_admin=True,
    )

    # Provider with None pricing to simulate unset price tier
    class UnsetPriceTestProvider:
        def __init__(self) -> None:
            self.is_placeholder = False

            class DummyRegistry:
                def get_pricing(self, alias: str) -> tuple[float, float] | None:
                    return None

            self.registry = DummyRegistry()

        def complete(self, alias: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
            return {
                "id": "chatcmpl-test-unset-price",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Analysis for query: TCS review.\nCost: unknown (pricing unset for tier).\nDeterministic audit completed.",
                        }
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 40},
            }

    provider = UnsetPriceTestProvider()

    try:
        res = run_agent_loop(
            query="Analyze market contagion absorption ratio",
            user=user,
            settings=settings,
            all_config=all_config,
            conn=conn,
            model_tier="balanced",
            provider=provider,
        )
        assert res.total_cost_usd is None
        assert res.cost is None
        assert "unknown" in res.answer.lower()
    finally:
        conn.close()
