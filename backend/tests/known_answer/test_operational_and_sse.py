"""Known-answer tests for operational routes (/api/admin/verifications, /llm/tiers) and agent SSE."""

import json
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user, require_admin
from backend.app.auth.models import UserClaims
from backend.app.main import create_app
from backend.tests.helpers.placeholder import PlaceholderProvider


@pytest.fixture
def admin_user() -> UserClaims:
    return UserClaims(
        user_id=uuid.uuid4(),
        email="admin@example.com",
        plan="judge_all",
        role="admin",
        segment="internal",
    )


@pytest.fixture
def standard_user() -> UserClaims:
    return UserClaims(
        user_id=uuid.uuid4(),
        email="user@example.com",
        plan="retail_free",
        role="user",
        segment="retail",
    )


def test_admin_verifications_unauthorized(standard_user: UserClaims):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: standard_user

    client = TestClient(app)
    resp = client.get("/api/admin/verifications")
    # Non-admin user must receive 403 Forbidden
    assert resp.status_code == 403


def test_admin_verifications_mocked_db(admin_user: UserClaims, monkeypatch):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[require_admin] = lambda: admin_user

    mock_row = (
        uuid.uuid4(),
        uuid.uuid4(),
        "SEBI",
        "INZ000123456",
        "pending",
        None,
    )

    class MockCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def execute(self, query, params=None):
            pass

        def fetchall(self):
            return [mock_row]

    class MockConnection:
        def cursor(self):
            return MockCursor()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr("backend.app.admin.router.get_connection", lambda _: MockConnection())

    client = TestClient(app)
    resp = client.get("/api/admin/verifications")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["regulator"] == "SEBI"
    assert data[0]["registration_number"] == "INZ000123456"
    assert data[0]["status"] == "pending"


def test_llm_tiers_endpoint(admin_user: UserClaims):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: admin_user

    client = TestClient(app)
    resp = client.get("/llm/tiers")
    assert resp.status_code == 200
    data = resp.json()
    assert "tiers" in data
    tiers = data["tiers"]
    assert "fast" in tiers
    assert "balanced" in tiers
    assert "deep" in tiers


def test_agent_sse_streaming(admin_user: UserClaims):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.state.llm_provider = PlaceholderProvider()

    client = TestClient(app)
    resp = client.post(
        "/agent/ask/stream",
        json={
            "query": "Assess contagion and system absorption across equities",
            "model_tier": "balanced",
        },
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    lines = resp.text.split("\n\n")
    events = [line.replace("data: ", "").strip() for line in lines if line.startswith("data: ")]
    assert len(events) >= 1

    parsed_events = [json.loads(e) for e in events]
    event_types = [e.get("type") for e in parsed_events]
    assert "done" in event_types
