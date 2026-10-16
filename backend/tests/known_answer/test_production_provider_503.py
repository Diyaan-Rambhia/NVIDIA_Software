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
