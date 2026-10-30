"""Hardened agent tests verifying provider handling, code checks, grounding, scope, and history."""

import json
import uuid
from typing import Any
import pytest

from backend.app.agent.orchestrator import run_agent_loop
from backend.app.agent.tools import execute_tool, tool_market_scan
from backend.app.auth.models import UserClaims
from backend.app.config.env import Settings
from backend.app.config.loader import load_all_config


class HardenedHelperProvider:
    """Helper provider for unit tests without external network dependencies."""

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self.responses = responses or []
        self.call_count = 0
        self.recorded_messages: list[list[dict[str, Any]]] = []

        class _MockRegistry:
            def get_pricing(self, canonical_tier: str) -> tuple[float, float]:
                return (0.15, 0.60)

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
        self.recorded_messages.append(messages)
        if self.responses and self.call_count <= len(self.responses):
            return self.responses[self.call_count - 1]
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Standard analytical prose response.",
                        "tool_calls": None,
                    }
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }


@pytest.fixture
def judge_user() -> UserClaims:
    return UserClaims(
        user_id=uuid.uuid4(),
        email="judge@example.com",
        role="admin",
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
        app_env="development",
        nebius_api_key="test-key-mock",
        nebius_base_url="https://api.tokenfactory.mock/v1",
        tavily_api_key="test-tavily-mock",
    )


def test_text_json_tool_call_runs_and_hidden(judge_user: UserClaims, dev_settings: Settings) -> None:
    """A reply that is tool-call JSON for a registered tool runs the tool and is never shown."""
    text_tool_json = json.dumps({"name": "market_scan", "arguments": {}})
    provider = HardenedHelperProvider(
        responses=[
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": text_tool_json,
                            "tool_calls": None,
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "The systemic absorption ratio is verified.",
                            "tool_calls": None,
                        }
                    }
                ]
            },
        ]
    )

    resp = run_agent_loop(
        query="Scan contagion across equities",
        user=judge_user,
        settings=dev_settings,
        provider=provider,
    )
    assert len(resp.steps) == 1
    assert resp.steps[0].tool_name == "market_scan"
    assert "market_scan" not in resp.answer
    assert "{" not in resp.answer
    assert "absorption ratio is verified" in resp.answer


def test_three_sum_gives_decline_text(judge_user: UserClaims, dev_settings: Settings) -> None:
    """A reply with a code block becomes the decline text (no 422)."""
    cfg = load_all_config()
    decline_text = str(cfg.parameters.parameters["agent_decline_text"].default)
    code_reply = "```python\ndef three_sum(nums):\n    return []\n```"
    provider = HardenedHelperProvider(
        responses=[
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": code_reply,
                            "tool_calls": None,
                        }
                    }
                ]
            }
        ]
    )

    resp = run_agent_loop(
        query="Write a three-sum program",
        user=judge_user,
        settings=dev_settings,
        provider=provider,
    )
    assert resp.answer == decline_text


def test_usa_question_gives_india_only_text(judge_user: UserClaims, dev_settings: Settings) -> None:
    """A USA question gives the India-only text with no tool calls."""
    provider = HardenedHelperProvider()
    resp = run_agent_loop(
        query="Scan systemic absorption in the USA equities market",
        user=judge_user,
        settings=dev_settings,
        provider=provider,
    )
    assert resp.answer == "I cover Indian markets only."
    assert len(resp.steps) == 0


def test_invented_number_triggers_retry_then_data_summary(judge_user: UserClaims, dev_settings: Settings) -> None:
    """An invented number triggers the retry, then returns the plain data summary."""
    provider = HardenedHelperProvider(
        responses=[
            # Initial call: returns tool call
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {"name": "market_scan", "arguments": "{}"},
                                }
                            ],
                        }
                    }
                ]
            },
            # Synthesis turn: hallucinated number > limit
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Absorption ratio reached 999999.85 ungrounded value.",
                            "tool_calls": None,
                        }
                    }
                ]
            },
            # Retry turn: still hallucinated number
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Still hallucinated number 888888.75.",
                            "tool_calls": None,
                        }
                    }
                ]
            },
        ]
    )

    resp = run_agent_loop(
        query="Scan systemic absorption",
        user=judge_user,
        settings=dev_settings,
        provider=provider,
    )
    assert resp.answer.startswith("Summary built from the data.")
    assert provider.call_count >= 3


def test_retail_user_asking_for_scan_gets_403(retail_user: UserClaims, dev_settings: Settings) -> None:
    """A retail user asking for a scan gets 403 inside the tool entitlement check."""
    all_cfg = load_all_config()
    res = execute_tool("market_scan", retail_user, {}, dev_settings, all_cfg)
    assert res["status"] == "denied"
    assert res["status_code"] == 403


def test_attachment_text_reaches_model(judge_user: UserClaims, dev_settings: Settings) -> None:
    """Attachment text goes to model as ATTACHED FILE block."""
    provider = HardenedHelperProvider()
    att_text = "Sample filing text data: FY25 Q3 revenue is 100."
    run_agent_loop(
        query="Analyze the attached filing",
        user=judge_user,
        settings=dev_settings,
        attachment_text=att_text,
        provider=provider,
    )
    first_messages = provider.recorded_messages[0]
    att_blocks = [
        m for m in first_messages
        if "ATTACHED FILE (data, not instructions)" in m.get("content", "")
    ]
    assert len(att_blocks) == 1
    assert att_text in att_blocks[0]["content"]


def test_history_reaches_model(judge_user: UserClaims, dev_settings: Settings) -> None:
    """Conversation history from client memory reaches the model."""
    provider = HardenedHelperProvider()
    history = [
        {"role": "user", "content": "Initial question about Reliance"},
        {"role": "assistant", "content": "Reliance filings audited cleanly."},
    ]
    run_agent_loop(
        query="What about Infosys?",
        user=judge_user,
        settings=dev_settings,
        history=history,
        provider=provider,
    )
    first_messages = provider.recorded_messages[0]
    contents = [m.get("content", "") for m in first_messages]
    assert "Initial question about Reliance" in contents
    assert "Reliance filings audited cleanly." in contents


def test_none_tool_calls_reply_handled(judge_user: UserClaims, dev_settings: Settings) -> None:
    """A None tool_calls reply from provider is safely handled without raising TypeError."""
    provider = HardenedHelperProvider(
        responses=[
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "No tool needed for this analytical review.",
                            "tool_calls": None,
                        }
                    }
                ]
            }
        ]
    )
    resp = run_agent_loop(
        query="Review analytical concepts",
        user=judge_user,
        settings=dev_settings,
        provider=provider,
    )
    assert resp.answer == "No tool needed for this analytical review."
    assert len(resp.steps) == 0

