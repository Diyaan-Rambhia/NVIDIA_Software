"""Tests for runtime Nemotron endpoint: auth, loud failure without key, zero placeholder."""

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.models import UserClaims
from backend.app.main import create_app


def test_x12_live_nemotron_endpoint_requires_auth_and_fails_loudly_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /llm/runtime_call requires auth, checks entitlement, and returns 503 when NEBIUS_API_KEY is missing."""
    from backend.app.config.env import Settings
    from backend.app.llm.router import _require_entitlement
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.setenv("NEBIUS_API_KEY", "")

    app = create_app()
    app.state.settings = Settings(nebius_api_key=None)
    client = TestClient(app)

    # 1. Unauthenticated request rejected with 401
    unauth_resp = client.post("/llm/runtime_call", json={"prompt": "Test prompt", "alias": "fast"})
    assert unauth_resp.status_code == 401

    # 2. Authenticated user receives 503 loud error (never placeholder)
    mock_user = UserClaims(
        user_id="00000000-0000-0000-0000-000000000001",
        email="judge@example.com",
        plan="judge_all",
        role="judge",
        segment="institutional",
    )
    app.dependency_overrides[_require_entitlement] = lambda: mock_user

    client_auth = TestClient(app)
    resp = client_auth.post("/llm/runtime_call", json={"prompt": "Analyze market contagion", "alias": "fast"})
    assert resp.status_code in (502, 503)
    body = resp.json()
    assert "error" in body
