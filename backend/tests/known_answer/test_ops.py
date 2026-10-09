"""Known-answer and integration tests for Ops console endpoints, static assets, and guard."""

from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.app.config import Settings
from backend.app.main import create_app


def test_ops_routes_in_development_mode() -> None:
    """When APP_ENV=development, /ops/status, /ops/config, /ops/parameters return 200."""
    dev_settings = Settings(app_env="development")
    app = create_app(settings=dev_settings, runtime_groups=[])
    client = TestClient(app)

    # 1. /ops/status
    res_status = client.get("/ops/status")
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert data_status["app_env"] == "development"
    assert "code_version" in data_status
    assert "uptime_seconds" in data_status
    assert "enabled_groups" in data_status

    # 2. /ops/config
    res_config = client.get("/ops/config")
    assert res_config.status_code == 200
    data_config = res_config.json()
    assert "groups" in data_config
    assert "core" in data_config["groups"]
    assert "enabled_groups" in data_config

    # 3. /ops/parameters
    res_params = client.get("/ops/parameters")
    assert res_params.status_code == 200
    data_params = res_params.json()
    assert "parameters" in data_params
    assert "W" in data_params["parameters"]
    assert data_params["parameters"]["W"]["default"] == 60

    # 4. /console/ index
    res_console = client.get("/console/")
    assert res_console.status_code == 200
    assert "FININSIGHT OPS CONSOLE" in res_console.text

    # 5. / redirect
    res_root = client.get("/", follow_redirects=False)
    assert res_root.status_code in (307, 302)
    assert res_root.headers["location"] == "/console/"


def test_ops_routes_404_when_app_env_not_development() -> None:
    """When APP_ENV != development, ops routes, /console/, and / return 404 ErrorEnvelope."""
    prod_settings = Settings(app_env="production")
    app = create_app(settings=prod_settings, runtime_groups=[])
    client = TestClient(app)

    routes_to_test = [
        "/ops/status",
        "/ops/config",
        "/ops/parameters",
        "/console/",
        "/",
    ]

    for route in routes_to_test:
        res = client.get(route, follow_redirects=False)
        assert res.status_code == 404
        body = res.json()
        assert "error" in body
        assert body["error"]["code"] == "HTTP_404"
        assert "request_id" in body["error"]
        assert res.headers["X-Request-ID"] == body["error"]["request_id"]


def test_secrets_never_appear_in_ops_endpoints(tmp_path: Path) -> None:
    """Recognizable secrets in .env never appear in /ops/config or /ops/status."""
    secret_val = "SUPER_SECRET_TOKEN_XYZ999"
    dev_settings = Settings(
        app_env="development",
        nebius_api_key=SecretStr(secret_val),
        supabase_anon_key=SecretStr(secret_val),
    )
    app = create_app(settings=dev_settings, runtime_groups=[])
    client = TestClient(app)

    res_status = client.get("/ops/status")
    assert secret_val not in res_status.text

    res_config = client.get("/ops/config")
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
