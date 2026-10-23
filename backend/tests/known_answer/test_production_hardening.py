"""Known-answer tests for production hardening: docs/OpenAPI disabling, placeholder refusal, CORS, and schema drift."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.config.env import Settings
from backend.app.config.loader import load_all_config
from backend.app.main import create_app
from backend.tests.helpers.placeholder import PlaceholderProvider


def test_production_docs_and_openapi_disabled() -> None:
    """In production mode, /docs, /redoc, and /openapi.json are disabled (return 404)."""
    app = create_app(settings=Settings(app_env="production"), runtime_groups=[])
    client = TestClient(app)

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_development_docs_and_openapi_enabled() -> None:
    """In development mode, /docs and /openapi.json are available."""
    app = create_app(settings=Settings(app_env="development"), runtime_groups=[])
    client = TestClient(app)

    assert client.get("/docs").status_code == 200
    res = client.get("/openapi.json")
    assert res.status_code == 200
    assert "openapi" in res.json()


def test_openapi_schema_drift() -> None:
    """Committed OpenAPI schema in docs/openapi.json must match freshly generated schema."""
    openapi_file = Path("docs") / "openapi.json"
    assert openapi_file.is_file(), "docs/openapi.json must exist"

    app = create_app(settings=Settings(app_env="development"), runtime_groups=[])
    fresh_schema = app.openapi()
    committed_schema = json.loads(openapi_file.read_text(encoding="utf-8"))

    assert fresh_schema == committed_schema, "OpenAPI schema drift detected; run scripts/export_openapi_schema.py"


def test_placeholder_refused_in_production() -> None:
    """Placeholder LLM provider must refuse initialization under production environment."""
    with pytest.raises(RuntimeError, match="strictly forbidden in 'production' environment"):
        PlaceholderProvider(settings=Settings(app_env="production"))


def test_cors_origins_from_config_no_wildcard_default() -> None:
    """CORS origins come from parameters config with no default of '*'."""
    all_cfg = load_all_config()
    cors_param = all_cfg.parameters.parameters.get("cors_origins")
    assert cors_param is not None, "cors_origins must be defined in parameters.yaml"
    assert cors_param.default != "*", "CORS origins must never default to '*'"

    app = create_app(settings=Settings(app_env="production"), runtime_groups=[])
    client = TestClient(app)

    # 1. Disallowed origin receives no Access-Control-Allow-Origin header
    res_disallowed = client.options(
        "/health",
        headers={
            "Origin": "http://evil-origin.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_disallowed.headers.get("access-control-allow-origin") != "http://evil-origin.example.com"
    assert res_disallowed.headers.get("access-control-allow-origin") != "*"

    # 2. Configured allowed origin receives matching Access-Control-Allow-Origin header
    res_allowed = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_allowed.headers.get("access-control-allow-origin") == "http://localhost:8000"
