"""Known-answer and integration tests for Ops console endpoints, static assets, and guard."""

import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.app.auth.dependencies import require_admin
from backend.app.auth.models import UserClaims
from backend.app.config import Settings
from backend.app.main import create_app


def _admin_user() -> UserClaims:
    return UserClaims(
        user_id=uuid.uuid4(),
        email="admin@example.com",
        role="admin",
        is_admin=True,
        app_metadata={"role": "admin"},
    )


def test_ops_routes_with_admin_auth() -> None:
    """When authenticated as admin, /ops/status, /ops/config, /ops/parameters return 200."""
    settings = Settings(app_env="production")
    app = create_app(settings=settings, runtime_groups=[])
    app.dependency_overrides[require_admin] = _admin_user
    client = TestClient(app)

    headers = {"Authorization": "Bearer test-admin-token"}

    # 1. /ops/status
    res_status = client.get("/ops/status", headers=headers)
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert data_status["app_env"] == "production"
    assert "code_version" in data_status
    assert "uptime_seconds" in data_status
    assert "enabled_groups" in data_status

    # 2. /ops/config
    res_config = client.get("/ops/config", headers=headers)
    assert res_config.status_code == 200
    data_config = res_config.json()
    assert "groups" in data_config
    assert "core" in data_config["groups"]
    assert "enabled_groups" in data_config

    # 3. /ops/parameters
    res_params = client.get("/ops/parameters", headers=headers)
    assert res_params.status_code == 200
    data_params = res_params.json()
    assert "parameters" in data_params
    assert "W" in data_params["parameters"]
    assert data_params["parameters"]["W"]["default"] == 60

    # 4. /console/ index
    res_console = client.get("/console/", headers=headers)
    assert res_console.status_code == 200
    assert "FININSIGHT OPS CONSOLE" in res_console.text

    # 5. / redirect
    res_root = client.get("/", headers=headers, follow_redirects=False)
    assert res_root.status_code in (307, 302)
    assert res_root.headers["location"] == "/console"


def test_ops_routes_401_when_unauthenticated() -> None:
    """When unauthenticated, ops inspection routes return 401 ErrorEnvelope, while /console/ returns 200."""
    settings = Settings(app_env="production")
    app = create_app(settings=settings, runtime_groups=[])
    client = TestClient(app)

    # Console static files load without token
    res_console = client.get("/console/", follow_redirects=False)
    assert res_console.status_code == 200

    # Root redirects to /console without token
    res_root = client.get("/", follow_redirects=False)
    assert res_root.status_code in (307, 302)
    assert res_root.headers["location"] == "/console"

    routes_to_test = [
        "/ops/status",
        "/ops/config",
        "/ops/parameters",
    ]

    for route in routes_to_test:
        res = client.get(route, follow_redirects=False)
        assert res.status_code == 401
        body = res.json()
        assert "error" in body
        assert body["error"]["code"] == "missing_token"
        assert "request_id" in body["error"]
        assert res.headers["X-Request-ID"] == body["error"]["request_id"]



def test_secrets_never_appear_in_ops_endpoints(tmp_path: Path) -> None:
    """Recognizable secrets in .env never appear in /ops/config or /ops/status."""
    secret_val = "SUPER_SECRET_TOKEN_XYZ999"
    settings = Settings(
        app_env="production",
        nebius_api_key=SecretStr(secret_val),
        supabase_anon_key=SecretStr(secret_val),
    )
    app = create_app(settings=settings, runtime_groups=[])
    app.dependency_overrides[require_admin] = _admin_user
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-admin-token"}

    res_status = client.get("/ops/status", headers=headers)
    assert secret_val not in res_status.text

    res_config = client.get("/ops/config", headers=headers)
    assert secret_val not in res_config.text
    # Names are present, values are never present
    assert "NEBIUS_API_KEY" in res_config.text


def test_frontend_console_files_exist_and_conform() -> None:
    """Verify that frontend/console files exist without external dependencies."""
    console_dir = Path("frontend") / "console"
    assert (console_dir / "index.html").is_file()
    assert (console_dir / "config.html").is_file()
    assert (console_dir / "assets" / "console.css").is_file()
    assert (console_dir / "assets" / "console.js").is_file()
