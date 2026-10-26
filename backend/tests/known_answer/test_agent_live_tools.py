"""Tests for live agent tools, model tool calling, and failure handling."""

import json
import uuid
import pytest
from typing import Any

from backend.app.agent.orchestrator import run_agent_loop
from backend.app.auth.models import UserClaims
from backend.app.config.env import Settings
from backend.app.config.loader import load_all_config
from backend.app.contracts.agent import AgentAskResponse
from backend.app.llm.exceptions import ModelToolCallFailedError


class MockToolCallProvider:
    """Helper provider that simulates model tool calling and response synthesis."""

    def __init__(self, tool_to_call: str, tool_args: dict[str, Any], final_answer: str | None = None) -> None:
        self.tool_to_call = tool_to_call
        self.tool_args = tool_args
        self.final_answer = final_answer
        self.call_count = 0
        self.is_placeholder = False

        class _MockRegistry:
            def get_pricing(self, canonical_tier: str) -> tuple[float, float]:
                return (0.15, 0.60)
            def initialize(self) -> None:
                pass

        self.registry = _MockRegistry()

    def complete(
        self,
        alias: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        user_id: uuid.UUID | None = None,
        route: str = "direct",
        temperature: float = 0.0,
        conn: Any = None,
    ) -> dict[str, Any]:
        self.call_count += 1
        if self.call_count == 1:
            # Return function tool call
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": f"call_{self.call_count}",
                                    "type": "function",
                                    "function": {
                                        "name": self.tool_to_call,
                                        "arguments": json.dumps(self.tool_args),
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 30},
            }
        else:
            # Final synthesis completion
            answer = self.final_answer or "Analytical review completed successfully."
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": answer,
                        }
                    }
                ],
                "usage": {"prompt_tokens": 150, "completion_tokens": 50},
            }


class FailingToolCallProvider:
    """Helper provider that never returns a tool call, attempting to answer from memory."""

    def __init__(self) -> None:
        self.call_count = 0
        self.is_placeholder = False

        class _MockRegistry:
            def get_pricing(self, canonical_tier: str) -> tuple[float, float]:
                return (0.15, 0.60)
            def initialize(self) -> None:
                pass

        self.registry = _MockRegistry()

    def complete(
        self,
        alias: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        user_id: uuid.UUID | None = None,
        route: str = "direct",
        temperature: float = 0.0,
        conn: Any = None,
    ) -> dict[str, Any]:
        self.call_count += 1
        # Model returns answer from memory without any tool calls
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "From my internal knowledge, the company reported good revenue.",
                    }
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 30},
        }


@pytest.fixture
def judge_user() -> UserClaims:
    return UserClaims(
        user_id=uuid.uuid4(),
        email="judge@example.com",
        role="user",
        segment="internal",
        plan="judge_all",
    )


@pytest.fixture
def retail_user() -> UserClaims:
    return UserClaims(
        user_id=uuid.uuid4(),
        email="retail@example.com",
        role="user",
        segment="retail",
        plan="retail_free",
    )


@pytest.fixture
def dev_settings() -> Settings:
    return Settings(
        values={
            "APP_ENV": "development",
            "NEBIUS_API_KEY": "test-key",
            "NEBIUS_BASE_URL": "https://api.tokenfactory.ai/v1",
            "DATABASE_URL": "",
        }
    )



def test_filings_question_makes_loop_call_filings_check(
    judge_user: UserClaims, dev_settings: Settings
) -> None:
    """A question that needs filings makes the loop call filings_check with company and period."""
    all_cfg = load_all_config()
    provider = MockToolCallProvider(
        tool_to_call="filings_check",
        tool_args={"company": "Rajesh Exports", "period": "Q3 FY25"},
        final_answer="Rajesh Exports Q3 FY25 financial check completed.",
    )

    resp = run_agent_loop(
        query="What did Rajesh Exports report in Q3 FY25 filings?",
        user=judge_user,
        settings=dev_settings,
        all_config=all_cfg,
        provider=provider,
    )

    assert isinstance(resp, AgentAskResponse)
    assert len(resp.steps) >= 1
    step = resp.steps[0]
    assert step.tool_name == "filings_check"
    assert "Rajesh Exports" in step.input_summary
    assert "Q3 FY25" in step.input_summary
    assert provider.call_count >= 2


def test_retail_user_market_scan_gets_403_inside_loop(
    retail_user: UserClaims, dev_settings: Settings
) -> None:
    """A retail user asking for market_scan gets 403 inside the tool loop."""
    all_cfg = load_all_config()
    provider = MockToolCallProvider(
        tool_to_call="market_scan",
        tool_args={},
        final_answer="Market scan was requested but access is denied on this plan.",
    )

    resp = run_agent_loop(
        query="Run market contagion scan across benchmark equities",
        user=retail_user,
        settings=dev_settings,
        all_config=all_cfg,
        provider=provider,
    )

    assert len(resp.steps) >= 1
    step = resp.steps[0]
    assert step.tool_name == "market_scan"
    assert step.status == "denied"
    assert "403" in step.output_summary or "denied" in step.output_summary.lower()


def test_financial_company_returns_unsupported_message_in_answer(
    judge_user: UserClaims, dev_settings: Settings
) -> None:
    """A financial company returns the unsupported message in the answer."""
    all_cfg = load_all_config()
    provider = MockToolCallProvider(
        tool_to_call="filings_check",
        tool_args={"company": "HDFC Bank", "period": "Q1 FY27"},
        final_answer="HDFC Bank filings evaluation: financial companies are not covered by the filings consistency audit.",
    )

    resp = run_agent_loop(
        query="Check filings for HDFC Bank",
        user=judge_user,
        settings=dev_settings,
        all_config=all_cfg,
        provider=provider,
    )

    assert len(resp.steps) >= 1
    step = resp.steps[0]
    assert "financial companies are not covered" in step.output_summary or "unsupported" in step.output_summary.lower()
    assert "financial companies are not covered" in resp.answer.lower()


def test_model_returns_no_tool_call_fails_with_502(
    judge_user: UserClaims, dev_settings: Settings
) -> None:
    """If the model returns no valid tool call after retry limit, return 502 MODEL_TOOL_CALL_FAILED."""
    all_cfg = load_all_config()
    provider = FailingToolCallProvider()

    with pytest.raises(ModelToolCallFailedError) as exc_info:
        run_agent_loop(
            query="What are the reported revenues and filing discrepancies for INFY?",
            user=judge_user,
            settings=dev_settings,
            all_config=all_cfg,
            model_tier="balanced",
            provider=provider,
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "MODEL_TOOL_CALL_FAILED"
    assert exc_info.value.tier == "balanced"
