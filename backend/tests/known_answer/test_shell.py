"""Known-answer and integration tests for app shell, logging, error envelope, and probes."""

import io
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, SecretStr

from backend.app.config import ConfigError, Settings
from backend.app.logging import JSONLineFormatter
from backend.app.main import create_app
from backend.app.version import get_code_version


def test_code_version_fallback(tmp_path: Path) -> None:
    """get_code_version returns 'unknown' when .git is absent, and returns hash when present."""
    assert get_code_version(repo_root=tmp_path) == "unknown"

    # Construct mock .git
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    refs_dir = git_dir / "refs" / "heads"
    refs_dir.mkdir(parents=True)
    (refs_dir / "main").write_text("abcdef1234567890\n", encoding="utf-8")

    assert get_code_version(repo_root=tmp_path) == "abcdef1"


def test_health_endpoint() -> None:
    """GET /health returns 200 with status ok."""
    app = create_app(runtime_groups=[])
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers


def test_ready_endpoint_success() -> None:
    """GET /ready returns 200 and ready=True when enabled groups are satisfied."""
    app = create_app(runtime_groups=[])
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["checks"]["missing"] == []


def test_ready_endpoint_failure_when_missing_vars() -> None:
    """GET /ready returns 503 and lists missing variables when group is enabled without keys."""
    # When initializing with missing required keys for an enabled group,
    # create_app validates at startup. We test the startup failure:
    settings = Settings(_env_file=None)
    with pytest.raises(ConfigError) as exc:
        create_app(settings=settings, runtime_groups=["llm"])
    err = str(exc.value)
    assert "NEBIUS_API_KEY" in err
    assert "NEBIUS_BASE_URL" in err


def test_ready_dynamic_503_naming_missing_variables() -> None:
    """If runtime_groups is modified post-startup, /ready returns 503 with missing vars."""
    settings = Settings(_env_file=None)
    app = create_app(settings=settings, runtime_groups=[])
    client = TestClient(app)

    # Initially ready
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True

    # Enable llm group dynamically without keys
    app.state.runtime_groups = ["llm"]
    r2 = client.get("/ready")
    assert r2.status_code == 503
    body = r2.json()
    assert body["ready"] is False
    assert "NEBIUS_API_KEY" in body["checks"]["missing"]
    assert "NEBIUS_BASE_URL" in body["checks"]["missing"]


def test_request_id_middleware_echo_and_generation() -> None:
    """Valid X-Request-ID is echoed; invalid or missing X-Request-ID is generated."""
    app = create_app(runtime_groups=[])
    client = TestClient(app)

    # 1. Valid request ID
    custom_id = "req_test-12345678"
    resp1 = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp1.headers["X-Request-ID"] == custom_id

    # 2. Missing request ID -> generated hex (>= 8 chars)
    resp2 = client.get("/health")
    gen_id = resp2.headers["X-Request-ID"]
    assert len(gen_id) >= 8
    assert gen_id != custom_id

    # 3. Invalid request ID (too short: < 8 chars) -> newly generated
    resp3 = client.get("/health", headers={"X-Request-ID": "short"})
    assert resp3.headers["X-Request-ID"] != "short"
    assert len(resp3.headers["X-Request-ID"]) >= 8


def test_error_envelope_404_and_422() -> None:
    """404 and 422 errors return the standard ErrorEnvelope."""
    app = create_app(runtime_groups=[])

    class ItemPayload(BaseModel):
        count: int

    @app.post("/test-validation")
    def sample_endpoint(payload: ItemPayload) -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    # 404 test
    resp_404 = client.get("/non-existent-route")
    assert resp_404.status_code == 404
    body_404 = resp_404.json()
    assert "error" in body_404
    assert body_404["error"]["code"] == "HTTP_404"
    assert "request_id" in body_404["error"]
    assert resp_404.headers["X-Request-ID"] == body_404["error"]["request_id"]

    # 422 test
    resp_422 = client.post("/test-validation", json={"count": "not-an-int"})
    assert resp_422.status_code == 422
    body_422 = resp_422.json()
    assert "error" in body_422
    assert body_422["error"]["code"] == "VALIDATION_ERROR"
    assert "request_id" in body_422["error"]
    assert resp_422.headers["X-Request-ID"] == body_422["error"]["request_id"]


def test_unhandled_exception_returns_generic_500_with_no_leak() -> None:
    """500 error returns generic message without traceback or secret in body or logs."""
    secret_value = "very_secret_token_12345"
    settings = Settings(nebius_api_key=SecretStr(secret_value))
    app = create_app(settings=settings, runtime_groups=[])

    # Log capture stream
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONLineFormatter())
    from backend.app.config.env import SecretRedactionFilter

    handler.addFilter(SecretRedactionFilter.from_settings(settings))
    logging.getLogger().addHandler(handler)

    @app.get("/raise-error")
    def trigger_error() -> None:
        raise RuntimeError(f"Database failed with key {secret_value}")

    client = TestClient(app)
    response = client.get("/raise-error")

    assert response.status_code == 500
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert body["error"]["message"] == "Internal server error"
    # Ensure no traceback and no secret in the response body
    assert secret_value not in response.text
    assert "Traceback" not in response.text

    # Verify captured logs
    captured_logs = log_stream.getvalue()
    assert secret_value not in captured_logs
    assert "***" in captured_logs
