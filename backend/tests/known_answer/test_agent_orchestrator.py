"""Tests for multi-step agent orchestrator loop, tool registry, and guards."""

import json
import time
import uuid
from typing import Any
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.agent.orchestrator import run_agent_loop
from backend.app.agent.tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    get_available_tools,
    tool_f1_contagion,
    tool_f2_filings,
    tool_f3_portfolio,
)
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import UserClaims
from backend.app.config.env import Settings
from backend.app.config.loader import load_all_config
from backend.app.contracts.agent import AgentAskRequest, AgentAskResponse, AgentStep
from backend.app.llm.exceptions import (
    BudgetExceededError,
    FinancialAdviceError,
    LLMTimeoutError,
    ProviderNotConfiguredError,
)
from backend.app.main import create_app
from backend.tests.helpers.placeholder import PLACEHOLDER_MARKER, PlaceholderProvider


@pytest.fixture
def judge_user() -> UserClaims:
    return UserClaims(
        user_id=uuid.uuid4(),
        email="judge@example.com",
        plan="judge_all",
        role="user",
        segment="internal",
    )


@pytest.fixture
def retail_user() -> UserClaims:
    return UserClaims(
        user_id=uuid.uuid4(),
        email="retail@example.com",
        plan="retail_free",
        role="user",
        segment="retail",
    )


@pytest.fixture
def institutional_user() -> UserClaims:
    return UserClaims(
        user_id=uuid.uuid4(),
        email="inst@example.com",
        plan="institutional_free",
        role="user",
        segment="institutional",
    )


@pytest.fixture
def dev_settings(tmp_path: Path) -> Settings:
    env_file = tmp_path / "dev.env"
    env_file.write_text("APP_ENV=development\n", encoding="utf-8")
    return Settings(_env_file=env_file)


class SmartTestProvider:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings
        self.call_count = 0
        self.is_placeholder = True

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
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.call_count += 1
        last_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_msg = m.get("content", "")
                break

        if tools and self.call_count == 1:
            tool_calls = []
            q_low = last_msg.lower()
            if any(k in q_low for k in ("contagion", "absorption", "correlation", "market", "systemic", "risk")):
                tool_calls.append({
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "market_scan", "arguments": "{}"},
                })
            if any(k in q_low for k in ("filing", "xbrl", "infy", "revenue", "discrepanc")):
                tool_calls.append({
                    "id": "call_2",
                    "type": "function",
                    "function": {"name": "filings_check", "arguments": json.dumps({"company": "INFY", "period": "Q3 FY25"})},
                })
            if not tool_calls:
                tool_calls.append({
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "market_scan", "arguments": "{}"},
                })

            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls,
                    }
                }],
                "usage": {"prompt_tokens": 150, "completion_tokens": 50},
            }

        obs_snippets = []
        for line in last_msg.splitlines():
            line_str = line.strip()
            if any(k in line_str for k in ("was denied", "verified findings", "Reference data observed")):
                obs_snippets.append(line_str)
        obs_str = (" " + " ".join(obs_snippets)) if obs_snippets else ""

        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": f"{PLACEHOLDER_MARKER}. Quantitative audit completed from computed evidence.{obs_str} Educational and research analytics only. No investment advice.",
                    "tool_calls": None,
                }
            }],
            "usage": {"prompt_tokens": 150, "completion_tokens": 50},
        }


@pytest.fixture
def test_provider(dev_settings: Settings) -> Any:
    return SmartTestProvider(settings=dev_settings)


def test_tool_definitions_and_schema_registry() -> None:
    """Tool registry exposes recognized tools with valid schemas."""
    tools = get_available_tools()
    assert len(tools) >= 3
    tool_names = [t["name"] for t in tools]
    assert "market_scan" in tool_names
    assert "filings_check" in tool_names
    assert "market_news" in tool_names


def test_tool_access_per_segment_and_plan(
    judge_user: UserClaims,
    retail_user: UserClaims,
    institutional_user: UserClaims,
    dev_settings: Settings,
) -> None:
    """Entitlement check in tool: retail denied, institutional locked, judge allowed."""
    all_cfg = load_all_config()

    # 1. Judge has full access to all features
    res_judge = execute_tool("f1_contagion", judge_user, {}, dev_settings, all_cfg)
    assert res_judge["status"] == "success"
    assert "absorption_ratio" in res_judge["data"]

    # 2. Retail is denied on F1 Contagion (403)
    res_retail = execute_tool("f1_contagion", retail_user, {}, dev_settings, all_cfg)
    assert res_retail["status"] == "denied"
    assert res_retail["status_code"] == 403

    # 3. Institutional free is locked on F1 Contagion with upgrade targets (402)
    res_inst = execute_tool("f1_contagion", institutional_user, {}, dev_settings, all_cfg)
    assert res_inst["status"] == "denied"
    assert res_inst["status_code"] == 402
    assert "institutional_paid" in res_inst["upgrade_targets"]

    # 4. Unknown tool returns error status
    res_unknown = execute_tool("nonexistent_tool", judge_user, {}, dev_settings, all_cfg)
    assert res_unknown["status"] == "error"


def test_agent_loop_execution_and_step_recording(
    judge_user: UserClaims, dev_settings: Settings, test_provider: PlaceholderProvider
) -> None:
    """Agent orchestrator executes planned steps, computes cost, and returns AgentAskResponse."""
    all_cfg = load_all_config()
    query = "Analyze market contagion and check quarterly filings"

    resp = run_agent_loop(
        query=query,
        user=judge_user,
        settings=dev_settings,
        all_config=all_cfg,
        provider=test_provider,
    )

    assert isinstance(resp, AgentAskResponse)
    assert resp.query == query
    assert len(resp.steps) >= 2
    for step in resp.steps:
        assert isinstance(step, AgentStep)
        assert step.step_number >= 1
        assert step.status == "success"
        assert step.duration_ms >= 0.0
        assert step.est_cost_usd >= 0.0

    assert resp.total_cost_usd >= 0.0
    assert resp.duration_ms > 0.0
    assert resp.is_placeholder is True
    assert PLACEHOLDER_MARKER in resp.answer
    assert "Educational and research review only" in resp.disclaimer


def test_agent_loop_denied_tool_handled_without_crash(
    retail_user: UserClaims, dev_settings: Settings, test_provider: PlaceholderProvider
) -> None:
    """When a tool is denied, step is recorded as denied and loop finishes cleanly."""
    all_cfg = load_all_config()
    query = "Check market contagion absorption ratio"

    resp = run_agent_loop(
        query=query,
        user=retail_user,
        settings=dev_settings,
        all_config=all_cfg,
        provider=test_provider,
    )

    assert len(resp.steps) == 1
    assert resp.steps[0].tool_name in ("f1_contagion", "market_scan")
    assert resp.steps[0].status == "denied"
    assert "was denied" in resp.answer


def test_agent_loop_step_limit_enforced(
    judge_user: UserClaims, dev_settings: Settings, test_provider: PlaceholderProvider
) -> None:
    """Loop exceeding configured or overridden step limit raises RuntimeError."""
    all_cfg = load_all_config()
    query = "Comprehensive multi-domain review of systemic risk and filings"

    with pytest.raises(RuntimeError, match="maximum step limit"):
        run_agent_loop(
            query=query,
            user=judge_user,
            settings=dev_settings,
            all_config=all_cfg,
            max_steps_override=1,
            provider=test_provider,
        )


def test_agent_loop_budget_guard_enforced(
    judge_user: UserClaims, dev_settings: Settings, test_provider: PlaceholderProvider
) -> None:
    """Projected step cost exceeding budget limit raises BudgetExceededError."""
    all_cfg = load_all_config()
    query = "Analyze contagion risk"

    with pytest.raises(BudgetExceededError, match="per-run budget"):
        run_agent_loop(
            query=query,
            user=judge_user,
            settings=dev_settings,
            all_config=all_cfg,
            budget_usd_override=0.0001,
            provider=test_provider,
        )


def test_agent_loop_timeout_guard_enforced(
    judge_user: UserClaims, dev_settings: Settings, test_provider: PlaceholderProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Loop exceeding timeout limit raises LLMTimeoutError."""
    all_cfg = load_all_config()
    query = "Analyze filings for INFY"

    # Advance time after start to trigger timeout
    orig_monotonic = time.monotonic
    call_count = 0

    def mock_monotonic() -> float:
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            return orig_monotonic() + 1000.0
        return orig_monotonic()

    monkeypatch.setattr(time, "monotonic", mock_monotonic)

    with pytest.raises(LLMTimeoutError, match="timeout limit"):
        run_agent_loop(
            query=query,
            user=judge_user,
            settings=dev_settings,
            all_config=all_cfg,
            provider=test_provider,
        )


def test_agent_loop_advice_guard_refusal(
    judge_user: UserClaims, dev_settings: Settings, test_provider: PlaceholderProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Model output containing prohibited financial advice is refused loudly."""
    all_cfg = load_all_config()
    query = "Analyze trade log"

    # Inject prohibited phrase into assert_no_financial_advice target
    with monkeypatch.context() as mp:
        mp.setattr(
            "backend.app.agent.orchestrator.assert_no_financial_advice",
            MagicMock(side_effect=FinancialAdviceError("Prohibited financial advice detected: 'we advise to buy'")),
        )
        with pytest.raises(FinancialAdviceError, match="Prohibited financial advice detected"):
            run_agent_loop(
                query=query,
                user=judge_user,
                settings=dev_settings,
                all_config=all_cfg,
                provider=test_provider,
            )


def test_agent_loop_refuses_in_production(tmp_path: Path, judge_user: UserClaims) -> None:
    """Agent loop strictly refuses execution under APP_ENV=production without configured provider."""
    prod_env = tmp_path / "prod.env"
    prod_env.write_text("APP_ENV=production\n", encoding="utf-8")
    prod_settings = Settings(_env_file=prod_env)
    all_cfg = load_all_config()

    with pytest.raises((RuntimeError, ProviderNotConfiguredError)):
        run_agent_loop(
            query="Analyze contagion",
            user=judge_user,
            settings=prod_settings,
            all_config=all_cfg,
        )


def test_agent_loop_records_to_ledger_when_conn_provided(
    judge_user: UserClaims, dev_settings: Settings, test_provider: PlaceholderProvider
) -> None:
    """When a db connection is present, each executed step records to the ledger."""
    all_cfg = load_all_config()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    resp = run_agent_loop(
        query="Analyze contagion and correlation",
        user=judge_user,
        settings=dev_settings,
        all_config=all_cfg,
        conn=mock_conn,
        provider=test_provider,
    )

    assert resp.is_placeholder is True
    assert mock_cur.execute.called
    assert "INSERT INTO public.llm_ledger" in mock_cur.execute.call_args[0][0]


def test_agent_ask_api_route(
    dev_settings: Settings, judge_user: UserClaims, test_provider: PlaceholderProvider
) -> None:
    """POST /agent/ask returns 200 with AgentAskResponse for authenticated user, 401 without."""
    app = create_app(settings=dev_settings, runtime_groups=[])
    app.state.llm_provider = test_provider
    client = TestClient(app)

    # 1. Unauthenticated request gives 401
    resp_unauth = client.post("/agent/ask", json={"query": "Analyze market contagion"})
    assert resp_unauth.status_code == 401

    # 2. Authenticated request gives 200 via dependency override
    app.dependency_overrides[get_current_user] = lambda: judge_user
    resp_auth = client.post(
        "/agent/ask",
        json={"query": "Analyze market contagion and check filings for INFY"},
    )
    assert resp_auth.status_code == 200
    data = resp_auth.json()
    assert data["query"] == "Analyze market contagion and check filings for INFY"
    assert len(data["steps"]) >= 2
    assert "answer" in data
    assert data["is_placeholder"] is True


def test_agent_ask_retail_denied_403_in_loop(
    dev_settings: Settings, retail_user: UserClaims, test_provider: PlaceholderProvider
) -> None:
    """demo_retail asks for Feature 1 through /agent/ask and gets 403 inside the tool loop."""
    app = create_app(settings=dev_settings, runtime_groups=[])
    app.state.llm_provider = test_provider
    app.dependency_overrides[get_current_user] = lambda: retail_user
    client = TestClient(app)

    resp = client.post(
        "/agent/ask",
        json={"query": "Analyze market contagion absorption ratio and correlation"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["steps"]) >= 1
    f1_step = [s for s in data["steps"] if s["tool_name"] in ("f1_contagion", "market_scan")][0]
    assert f1_step["status"] == "denied"
    assert "403" in f1_step["output_summary"] or "unavailable to segment 'retail'" in f1_step["output_summary"]
    assert "was denied" in data["answer"]


def test_agent_loop_quota_exceeded_429_in_loop(
    retail_user: UserClaims, dev_settings: Settings, test_provider: PlaceholderProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User at daily quota for a feature gets 429 inside the agent tool loop."""
    all_cfg = load_all_config()
    mock_conn = MagicMock()

    # Simulate quota reached
    monkeypatch.setattr(
        "backend.app.agent.tools.get_today_usage",
        lambda conn, user_id, feature: (all_cfg.plans.plans["retail_free"].features["feature2_filings"].quota_per_day or 9)
    )

    resp = run_agent_loop(
        query="Check quarterly filings discrepancies for INFY",
        user=retail_user,
        settings=dev_settings,
        all_config=all_cfg,
        conn=mock_conn,
        provider=test_provider,
    )
    assert len(resp.steps) >= 1
    f2_step = [s for s in resp.steps if s.tool_name in ("f2_filings", "filings_check")][0]
    assert f2_step.status == "denied"
    assert "429" in f2_step.output_summary or "quota" in f2_step.output_summary.lower()
    assert "was denied" in resp.answer


def test_agent_loop_invalid_tool_output_raises(
    judge_user: UserClaims, dev_settings: Settings, test_provider: PlaceholderProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid tool output raises a clear RuntimeError and returns no guessed answer."""
    all_cfg = load_all_config()

    from backend.app.agent import orchestrator
    monkeypatch.setattr(
        orchestrator,
        "execute_tool",
        lambda **kwargs: {"status": "error", "reason": "Corrupted tool response format"},
    )

    with pytest.raises(RuntimeError, match="Invalid tool output from '(f1_contagion|market_scan)': Corrupted tool response format"):
        run_agent_loop(
            query="Analyze contagion",
            user=judge_user,
            settings=dev_settings,
            all_config=all_cfg,
            provider=test_provider,
        )


def test_agent_ask_refuses_placeholder_in_production(
    tmp_path: Path, judge_user: UserClaims
) -> None:
    """In production /agent/ask refuses the placeholder and never falls back to it."""
    prod_env = tmp_path / "prod.env"
    prod_env.write_text("APP_ENV=production\n", encoding="utf-8")
    prod_settings = Settings(_env_file=prod_env)

    app = create_app(settings=prod_settings, runtime_groups=[])
    app.dependency_overrides[get_current_user] = lambda: judge_user
    client = TestClient(app)

    resp = client.post("/agent/ask", json={"query": "Analyze contagion"})
    assert resp.status_code == 503
    data = resp.json()
    assert data["error"]["code"] == "provider_not_configured"
    # Never returns placeholder answer
    assert "answer" not in data or PLACEHOLDER_MARKER not in str(data)


def test_agent_loop_ledger_holds_no_user_data_or_prompts(
    judge_user: UserClaims, dev_settings: Settings, test_provider: PlaceholderProvider
) -> None:
    """Ledger holds no user query text, no prompt contents, and no keys."""
    all_cfg = load_all_config()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    sensitive_query = "Secret user portfolio details and passwords 123456"
    resp = run_agent_loop(
        query=sensitive_query,
        user=judge_user,
        settings=dev_settings,
        all_config=all_cfg,
        conn=mock_conn,
        provider=test_provider,
    )

    assert resp.is_placeholder is True
    assert mock_cur.execute.called

    # Check all calls made to cursor.execute for ledger insertion
    for call in mock_cur.execute.call_args_list:
        query_sql, params = call[0]
        if "INSERT INTO public.llm_ledger" in query_sql:
            # params is (id, user_id, route, alias, model_id, input_tokens, output_tokens, est_cost_usd, cache_hit)
            for param in params:
                param_str = str(param)
                assert sensitive_query not in param_str, "Sensitive user query found in ledger parameters"
                assert "123456" not in param_str, "Sensitive query details found in ledger parameters"


