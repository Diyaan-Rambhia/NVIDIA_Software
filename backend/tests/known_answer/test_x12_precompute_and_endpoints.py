"""Tests for Batch X12: Precomputed demo endpoints, zero placeholder guarantee, and runtime Nemotron endpoint."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.models import UserClaims
from backend.app.features.f3_log.router import F3_DEMO_PATH, _require_f3
from backend.app.llm.placeholder import PLACEHOLDER_MARKER
from backend.app.main import create_app


@pytest.fixture
def test_client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_x12_precomputed_demo_files_contain_no_placeholder() -> None:
    """Zero placeholder template markers or placeholder text in precomputed demo JSON files."""
    base_dir = Path("demo_data") if Path("demo_data").is_dir() else Path("data")
    demo_files = [
        base_dir / "f1_scan_demo.json",
        base_dir / "f2_filings_demo.json",
        base_dir / "f3_review_demo.json",
    ]
    for path in demo_files:
        assert path.is_file(), f"{path} must exist"
        content = path.read_text(encoding="utf-8")
        assert PLACEHOLDER_MARKER not in content, f"{path} contains PLACEHOLDER_MARKER"
        assert "placeholder" not in content.lower(), f"{path} contains 'placeholder'"


def test_x12_f3_demo_endpoint_serves_precomputed_data() -> None:
    """GET /f3/demo returns precomputed Feature 3 review data with synthetic demo label."""
    assert F3_DEMO_PATH.is_file()
    app = create_app()

    # Override auth dependency to simulate authenticated user
    mock_user = UserClaims(
        user_id="00000000-0000-0000-0000-000000000001",
        email="judge@example.com",
        plan="judge_all",
        role="judge",
        segment="institutional",
    )
    app.dependency_overrides[_require_f3] = lambda: mock_user

    client = TestClient(app)
    resp = client.get("/f3/demo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_synthetic_demo"] is True
    assert data["synthetic_label"] == "SYNTHETIC DEMO LOG, not a real investor"
    assert "not generated: awaiting real model" in data["review_text"]
    assert PLACEHOLDER_MARKER not in data["review_text"]


def test_x12_live_nemotron_endpoint_requires_auth_and_fails_loudly_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /llm/runtime_call requires auth, checks entitlement, and returns 503 when NEBIUS_API_KEY is missing."""
    from backend.app.llm.router import _require_entitlement
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    app = create_app()
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
    assert resp.status_code == 503
    body = resp.json()
    assert "error" in body
    assert "nebius_key_missing" in body["error"]["message"] or "NEBIUS_API_KEY is not configured" in body["error"]["message"]

