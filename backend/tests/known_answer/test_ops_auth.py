"""Known-answer and security tests for ops routes, console access, and admin guard."""

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user, require_admin
from backend.app.auth.models import UserClaims
from backend.app.config import Settings
from backend.app.main import create_app

OPS_PROTECTED_ROUTES = [
    "/ops/status",
    "/ops/config",
    "/ops/parameters",
    "/ops/activity/events",
    "/ops/activity/llm",
]


@pytest.fixture
def non_admin_user() -> UserClaims:
    import uuid

    return UserClaims(
        user_id=uuid.uuid4(),
        email="retail@example.com",
        role="user",
        is_admin=False,
        app_metadata={"role": "user"},
    )


@pytest.fixture
def admin_user() -> UserClaims:
    import uuid

    return UserClaims(
        user_id=uuid.uuid4(),
        email="admin@example.com",
        role="admin",
        is_admin=True,
        app_metadata={"role": "admin"},
    )


def test_no_token_returns_401_on_all_ops_routes() -> None:
    """Missing authorization token returns HTTP 401 on /ops/* inspection routes."""
    app = create_app(settings=Settings(app_env="production"), runtime_groups=[])
    client = TestClient(app)

    for route in OPS_PROTECTED_ROUTES:
        res = client.get(route, follow_redirects=False)
        assert res.status_code == 401, f"Route {route} expected 401, got {res.status_code}"
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "missing_token"
        assert "request_id" in data["error"]


def test_console_static_routes_return_200_without_token() -> None:
    """Static ops console pages load without bearer token so login form can display."""
    app = create_app(settings=Settings(app_env="production"), runtime_groups=[])
    client = TestClient(app)

    # 1. /console/
    res_slash = client.get("/console/", follow_redirects=False)
    assert res_slash.status_code == 200
    assert "FININSIGHT OPS CONSOLE" in res_slash.text

    # 2. /console
    res_bare = client.get("/console", follow_redirects=False)
    assert res_bare.status_code == 200
    assert "FININSIGHT OPS CONSOLE" in res_bare.text

    # 3. /console/index.html
    res_index = client.get("/console/index.html", follow_redirects=False)
    assert res_index.status_code == 200

    # 4. /console/config.html
    res_cfg = client.get("/console/config.html", follow_redirects=False)
    assert res_cfg.status_code == 200
    assert "ENVIRONMENT VARIABLES REGISTRY" in res_cfg.text

    # 5. Root / redirects unauthenticated browser directly to /app
    res_root = client.get("/", follow_redirects=False)
    assert res_root.status_code in (307, 302)
    assert res_root.headers["location"] == "/app"


def test_ops_status_auth_matrix(
    non_admin_user: UserClaims,
    admin_user: UserClaims,
) -> None:
    """Verify /ops/status returns 401 without token, 403 for non-admin, and 200 for admin."""
    app = create_app(settings=Settings(app_env="production"), runtime_groups=[])

    # 1. No token -> 401
    client_anon = TestClient(app)
    res_anon = client_anon.get("/ops/status")
    assert res_anon.status_code == 401
    assert res_anon.json()["error"]["code"] == "missing_token"

    # 2. Non-admin -> 403
    app_non_admin = create_app(settings=Settings(app_env="production"), runtime_groups=[])
    app_non_admin.dependency_overrides[get_current_user] = lambda: non_admin_user
    client_non_admin = TestClient(app_non_admin)
    res_non_admin = client_non_admin.get("/ops/status", headers={"Authorization": "Bearer test-user-token"})
    assert res_non_admin.status_code == 403
    assert res_non_admin.json()["error"]["code"] == "forbidden"

    # 3. Admin -> 200
    app_admin = create_app(settings=Settings(app_env="production"), runtime_groups=[])
    app_admin.dependency_overrides[require_admin] = lambda: admin_user
    client_admin = TestClient(app_admin)
    res_admin = client_admin.get("/ops/status", headers={"Authorization": "Bearer test-admin-token"})
    assert res_admin.status_code == 200
    assert "app_env" in res_admin.json()


def test_non_admin_token_returns_403_on_all_ops_routes(
    non_admin_user: UserClaims,
) -> None:
    """Authenticated non-admin user returns HTTP 403 on all /ops/* routes."""
    app = create_app(settings=Settings(app_env="production"), runtime_groups=[])
    app.dependency_overrides[get_current_user] = lambda: non_admin_user
    client = TestClient(app)

    headers = {"Authorization": "Bearer non-admin-token-probe"}
    for route in OPS_PROTECTED_ROUTES:
        res = client.get(route, headers=headers, follow_redirects=False)
        assert res.status_code == 403, f"Route {route} expected 403, got {res.status_code}"
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "forbidden"


def test_admin_token_returns_200_or_redirect_on_all_routes(
    admin_user: UserClaims,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Admin token grants 200 on ops endpoints, console pages, and redirect on root."""
    app = create_app(settings=Settings(app_env="production"), runtime_groups=[])
    app.dependency_overrides[require_admin] = lambda: admin_user

    # Mock database connection for activity endpoints
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_cursor.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value = mock_cursor
    monkeypatch.setattr("backend.app.ops.routes.get_connection", lambda s: mock_conn)

    client = TestClient(app)
    headers = {"Authorization": "Bearer valid-admin-token"}

    # 1. /ops/status
    res = client.get("/ops/status", headers=headers)
    assert res.status_code == 200
    assert "app_env" in res.json()

    # 2. /ops/config
    res = client.get("/ops/config", headers=headers)
    assert res.status_code == 200
    assert "groups" in res.json()

    # 3. /ops/parameters
    res = client.get("/ops/parameters", headers=headers)
    assert res.status_code == 200
    assert "parameters" in res.json()

    # 4. /ops/activity/events
    res = client.get("/ops/activity/events", headers=headers)
    assert res.status_code == 200
    assert res.json() == []

    # 5. /ops/activity/llm
    res = client.get("/ops/activity/llm", headers=headers)
    assert res.status_code == 200
    assert res.json() == []

    # 6. /console/ index
    res = client.get("/console/", headers=headers)
    assert res.status_code == 200
    assert "FININSIGHT OPS CONSOLE" in res.text

    # 7. /console bare path
    res = client.get("/console", headers=headers)
    assert res.status_code == 200
    assert "FININSIGHT OPS CONSOLE" in res.text

    # 8. /console/config.html
    res = client.get("/console/config.html", headers=headers)
    assert res.status_code == 200
    assert "ENVIRONMENT VARIABLES REGISTRY" in res.text

    # 9. / redirect to /app
    res = client.get("/", headers=headers, follow_redirects=False)
    assert res.status_code in (307, 302)
    assert res.headers["location"] == "/app"


def test_console_frontend_source_compliance() -> None:
    """Grep frontend/console directory verifying design rules, zero leakages, no keys/tokens/user data."""
    console_dir = Path("frontend") / "console"
    html_files = list(console_dir.glob("*.html"))
    js_files = list((console_dir / "assets").glob("*.js"))
    css_files = list((console_dir / "assets").glob("*.css"))
    all_files = html_files + js_files + css_files

    assert len(all_files) >= 4

    for f in all_files:
        content = f.read_text(encoding="utf-8")

        # No external URLs
        assert not re.search(r"https?://", content), f"External URL found in {f}"

        # No innerHTML with server data
        assert "innerHTML" not in content, f"innerHTML usage found in {f}"

        # No token in URL patterns (no token in query string or URL bar manipulation)
        assert "token=" not in content, f"Token in URL parameter found in {f}"
        assert "?access_token" not in content, f"Token parameter found in {f}"

        # No hardcoded API keys, JWTs or secrets
        assert "eyJ" not in content, f"JWT found in {f}"
        assert "sk-" not in content, f"Secret key found in {f}"
        assert not re.search(r"(?:api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]{10,}['\"]", content, re.I), f"Hardcoded credential found in {f}"


    # Check that "no rows" is handled in console.js
    js_content = (console_dir / "assets" / "console.js").read_text(encoding="utf-8")
    assert "no rows" in js_content


def test_frontend_element_ids_and_login_forms_exist() -> None:
    """Every element ID used in app.js and console.js exists in matching HTML, and login forms exist."""
    root = Path(__file__).resolve().parent.parent.parent.parent

    # 1. /app/ validation
    app_html = (root / "frontend" / "app" / "index.html").read_text(encoding="utf-8")
    app_js = (root / "frontend" / "app" / "app.js").read_text(encoding="utf-8")

    app_html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', app_html))
    app_js_ids = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', app_js))

    missing_app_ids = app_js_ids - app_html_ids
    assert not missing_app_ids, f"Missing IDs in frontend/app/index.html: {missing_app_ids}"
    assert "form-login" in app_html_ids
    assert "screen-login" in app_html_ids

    # 2. /console/ validation
    console_index_html = (root / "frontend" / "console" / "index.html").read_text(encoding="utf-8")
    console_config_html = (root / "frontend" / "console" / "config.html").read_text(encoding="utf-8")
    console_js = (root / "frontend" / "console" / "assets" / "console.js").read_text(encoding="utf-8")

    console_html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', console_index_html)) | set(
        re.findall(r'id=["\']([^"\']+)["\']', console_config_html)
    )
    console_js_ids = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', console_js))

    missing_console_ids = console_js_ids - console_html_ids
    assert not missing_console_ids, f"Missing IDs in console HTML files: {missing_console_ids}"
    assert "login-form" in console_html_ids
    assert "login-panel" in console_html_ids

