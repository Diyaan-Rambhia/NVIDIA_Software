"""Tests ensuring /agent/ask and /llm/runtime_call return 503 ErrorEnvelope in production without provider."""

from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import UserClaims
from backend.app.config.env import Settings
from backend.app.contracts.common import ErrorEnvelope
from backend.app.llm.router import _require_entitlement
from backend.app.main import create_app


@pytest.fixture
def test_user() -> UserClaims:
    return UserClaims(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        email="judge@example.com",
        plan="judge_all",
        role="judge",
        segment="institutional",
    )


def test_agent_ask_production_no_provider_returns_503_error_envelope(
    tmp_path: Path, test_user: UserClaims
) -> None:
    """When no real provider is configured in production, /agent/ask returns 503 with ErrorEnvelope."""
    prod_env = tmp_path / "prod.env"
    prod_env.write_text("APP_ENV=production\n", encoding="utf-8")
    prod_settings = Settings(_env_file=prod_env)

    app = create_app(settings=prod_settings, runtime_groups=[])
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app)

    resp = client.post("/agent/ask", json={"query": "Analyze contagion"})
    assert resp.status_code == 503, f"Expected 503 but got {resp.status_code}: {resp.text}"

    data = resp.json()
    envelope = ErrorEnvelope.model_validate(data)
    assert envelope.error.code == "provider_not_configured"
    assert "production" in envelope.error.message.lower()
    assert resp.status_code != 500


def test_runtime_nemotron_production_no_provider_returns_503_error_envelope(
    tmp_path: Path, test_user: UserClaims, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When no real provider is configured in production, /llm/runtime_call returns 503 with ErrorEnvelope."""
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    prod_env = tmp_path / "prod.env"
    prod_env.write_text("APP_ENV=production\n", encoding="utf-8")
    prod_settings = Settings(_env_file=prod_env)

    app = create_app(settings=prod_settings, runtime_groups=[])
    app.dependency_overrides[_require_entitlement] = lambda: test_user
    client = TestClient(app)

    resp = client.post(
        "/llm/runtime_call",
        json={"prompt": "Analyze market contagion", "alias": "fast"},
    )
    assert resp.status_code == 503, f"Expected 503 but got {resp.status_code}: {resp.text}"

    data = resp.json()
    envelope = ErrorEnvelope.model_validate(data)
    assert envelope.error.code in ("provider_not_configured", "nebius_key_missing")
    assert "NEBIUS_API_KEY is not configured" in envelope.error.message
    assert resp.status_code != 500


def test_backend_app_has_no_placeholder_or_test_imports() -> None:
    """Scan backend/app for any placeholder or backend.tests imports."""
    import ast

    backend_app_dir = Path("backend") / "app"
    forbidden_modules = {"placeholder", "backend.tests"}

    violations = []
    for py_file in backend_app_dir.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception as exc:
            violations.append(f"{py_file}: failed to parse AST: {exc}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name == mod or alias.name.startswith(f"{mod}.") for mod in forbidden_modules):
                        violations.append(f"{py_file}:{node.lineno} imports '{alias.name}'")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    if any(node.module == mod or node.module.startswith(f"{mod}.") for mod in forbidden_modules):
                        violations.append(f"{py_file}:{node.lineno} imports from '{node.module}'")
                for alias in node.names:
                    if alias.name in ("PlaceholderProvider", "placeholder"):
                        violations.append(f"{py_file}:{node.lineno} imports name '{alias.name}'")

    assert not violations, f"Forbidden placeholder/tests imports found in backend/app:\n" + "\n".join(violations)


def test_agent_ask_unset_price_lets_call_through_and_cost_unknown(
    tmp_path: Path, test_user: UserClaims, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unset price field lets a call through with real provider client, cost=null, and reply says unknown."""
    from unittest.mock import patch, MagicMock
    from backend.app.llm.client import LLMClient

    monkeypatch.setenv("NEBIUS_API_KEY", "dummy-test-key-without-network")
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app)

    captured_provider = []

    def mock_run_agent_loop(**kwargs):
        provider = kwargs.get("provider")
        captured_provider.append(provider)
        from backend.app.contracts.agent import AgentAskResponse, AgentStep
        return AgentAskResponse(
            query=kwargs.get("query"),
            answer="Analysis completed. Cost: unknown (pricing unset for tier).",
            steps=[
                AgentStep(
                    step_number=1,
                    tool_name="f1_contagion",
                    input_summary="f1_contagion()",
                    output_summary="Success: verified 3 metrics",
                    status="success",
                    est_cost_usd=None,
                    duration_ms=10.5,
                )
            ],
            total_cost_usd=None,
            cost=None,
            duration_ms=25.0,
            model_tier="balanced",
            is_placeholder=False,
        )

    with patch("backend.app.llm.registry.ModelRegistry.initialize"), \
         patch("backend.app.agent.router.run_agent_loop", side_effect=mock_run_agent_loop):
        resp = client.post("/agent/ask", json={"query": "What is contagion risk?"})
        assert resp.status_code == 200
        data = resp.json()
        # Provider client class is LLMClient
        assert len(captured_provider) == 1
        assert isinstance(captured_provider[0], LLMClient)
        # Cost is null
        assert data["total_cost_usd"] is None
        assert data["cost"] is None
        # Reply says unknown
        assert "unknown" in data["answer"].lower()


def test_agent_ask_token_limit_gives_429(
    tmp_path: Path, test_user: UserClaims, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When pricing is unset and token limits are exceeded, request fails with 429 and reset time."""
    from unittest.mock import patch
    from backend.app.llm.exceptions import TokenLimitExceededError

    monkeypatch.setenv("NEBIUS_API_KEY", "dummy-test-key-without-network")
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app)

    with patch("backend.app.llm.registry.ModelRegistry.initialize"), \
         patch("backend.app.agent.router.run_agent_loop", side_effect=TokenLimitExceededError("Daily token limit exceeded", reset_time="2026-10-25T00:00:00+00:00")):
        resp = client.post("/agent/ask", json={"query": "What is contagion risk?"})
        assert resp.status_code == 429
        data = resp.json()
        assert data["error"]["code"] in ("quota_exceeded", "HTTP_429")
        assert data["error"]["reset_time"] is not None
        assert "X-Reset-Time" in resp.headers


def test_agent_ask_set_price_gives_usd_cost(
    tmp_path: Path, test_user: UserClaims, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When price is configured, total_cost_usd is computed and returned as a positive USD cost."""
    from unittest.mock import patch

    monkeypatch.setenv("NEBIUS_API_KEY", "dummy-test-key-without-network")
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app)

    def mock_run_agent_loop(**kwargs):
        from backend.app.contracts.agent import AgentAskResponse, AgentStep
        return AgentAskResponse(
            query=kwargs.get("query"),
            answer="Analysis completed with configured pricing.",
            steps=[
                AgentStep(
                    step_number=1,
                    tool_name="f1_contagion",
                    input_summary="f1_contagion()",
                    output_summary="Success: verified 3 metrics",
                    status="success",
                    est_cost_usd=0.0003,
                    duration_ms=10.5,
                )
            ],
            total_cost_usd=0.0003,
            cost=0.0003,
            duration_ms=25.0,
            model_tier="balanced",
            is_placeholder=False,
        )

    with patch("backend.app.llm.registry.ModelRegistry.initialize"), \
         patch("backend.app.agent.router.run_agent_loop", side_effect=mock_run_agent_loop):
        resp = client.post("/agent/ask", json={"query": "What is contagion risk?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost_usd"] == 0.0003
        assert data["cost"] == 0.0003
        assert isinstance(data["total_cost_usd"], float)



def test_agent_ask_provider_error_returns_502(
    tmp_path: Path, test_user: UserClaims, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the provider fails, /agent/ask returns 502 with upstream status in every environment (no 500 AGENT_ERROR)."""
    from unittest.mock import patch
    from backend.app.llm.exceptions import LLMUpstreamError

    monkeypatch.setenv("NEBIUS_API_KEY", "dummy-test-key-without-network")
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app)

    with patch("backend.app.agent.router.run_agent_loop") as mock_loop:
        mock_loop.side_effect = LLMUpstreamError(
            status_code=502,
            message="Upstream Nebius LLM gateway failed",
        )
        resp = client.post("/agent/ask", json={"query": "Explain systemic risk"})
        assert resp.status_code == 502
        data = resp.json()
        assert data["error"]["code"] in ("upstream_llm_error", "UPSTREAM_HTTP_502", "PROVIDER_ERROR")
        assert resp.status_code != 500

