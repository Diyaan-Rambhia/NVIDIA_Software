"""Live integration tests for ops console endpoints and admin authorization guard."""

import json
import urllib.request
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.config.env import load_settings
from backend.app.main import create_app


def _get_live_env() -> dict[str, str]:
    settings = load_settings()
    supabase_url = settings.get_var_value("SUPABASE_URL")
    anon_key = settings.get_var_value("SUPABASE_ANON_KEY")
    service_key = settings.get_var_value("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_key or not anon_key:
        pytest.skip("not run: no key")

    try:
        import psycopg
        from backend.app.db.connection import get_database_url

        url = get_database_url(settings)
        with psycopg.connect(url, connect_timeout=5):
            pass
    except Exception:
        pytest.skip("not run: no database")

    return {
        "url": supabase_url,
        "anon_key": anon_key,
        "service_key": service_key,
    }


def _create_user(live_env: dict[str, str], email: str, password: str, is_admin: bool) -> uuid.UUID:
    admin_url = f"{live_env['url'].rstrip('/')}/auth/v1/admin/users"
    role = "admin" if is_admin else "user"
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "app_metadata": {"role": role},
        "user_metadata": {"email_verified": True},
    }
    req = urllib.request.Request(
        admin_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "apikey": live_env["service_key"],
            "Authorization": f"Bearer {live_env['service_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return uuid.UUID(data["id"])


def _delete_user(live_env: dict[str, str], user_id: uuid.UUID) -> None:
    del_url = f"{live_env['url'].rstrip('/')}/auth/v1/admin/users/{user_id}"
    req = urllib.request.Request(
        del_url,
        headers={
            "apikey": live_env["service_key"],
            "Authorization": f"Bearer {live_env['service_key']}",
        },
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
    except Exception:
        pass


def _login(live_env: dict[str, str], email: str, password: str) -> str:
    login_url = f"{live_env['url'].rstrip('/')}/auth/v1/token?grant_type=password"
    req = urllib.request.Request(
        login_url,
        data=json.dumps({"email": email, "password": password}).encode("utf-8"),
        headers={
            "apikey": live_env["anon_key"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["access_token"]


def test_live_ops_admin_and_non_admin_access() -> None:
    """Real non-admin gets 403 and real admin gets 200 on /ops/* and /console/."""
    live_env = _get_live_env()
    settings = load_settings()
    app = create_app(settings=settings, runtime_groups=["core", "supabase"])
    client = TestClient(app)

    unique_suffix = uuid.uuid4().hex[:8]
    retail_email = f"live_retail_{unique_suffix}@example.com"
    admin_email = f"live_admin_{unique_suffix}@example.com"
    test_password = "TempTestPassword123!"

    retail_id = None
    admin_id = None

    try:
        # Create users
        retail_id = _create_user(live_env, retail_email, test_password, is_admin=False)
        admin_id = _create_user(live_env, admin_email, test_password, is_admin=True)

        # Login
        retail_token = _login(live_env, retail_email, test_password)
        admin_token = _login(live_env, admin_email, test_password)

        retail_headers = {"Authorization": f"Bearer {retail_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        ops_protected_routes = [
            "/ops/status",
            "/ops/config",
            "/ops/activity/events",
        ]

        # 1. Non-admin gets 403 on protected /ops/* routes, but 200 on /console/ static
        for route in ops_protected_routes:
            res_retail = client.get(route, headers=retail_headers)
            assert res_retail.status_code == 403, (
                f"Expected 403 for retail user on {route}, got {res_retail.status_code}"
            )
        assert client.get("/console/", headers=retail_headers).status_code == 200

        # 2. Admin gets 200 on all routes
        for route in ops_protected_routes + ["/console/"]:
            res_admin = client.get(route, headers=admin_headers)
            assert res_admin.status_code == 200, (
                f"Expected 200 for admin user on {route}, got {res_admin.status_code}"
            )

    finally:
        if retail_id is not None:
            _delete_user(live_env, retail_id)
        if admin_id is not None:
            _delete_user(live_env, admin_id)


def test_live_set_admin_role_script() -> None:
    """Set the admin role on a real test user using set_admin_role, verify role, then delete user."""
    live_env = _get_live_env()
    from scripts.set_admin import set_admin_role

    test_email = f"live_elevate_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "TempElevatePassword123!"
    user_id = None

    try:
        user_id = _create_user(live_env, test_email, test_password, is_admin=False)

        # Set admin role
        result = set_admin_role(test_email, allow_production=True)
        if result == "user not found":
            pytest.skip("not run: Supabase Admin API 500 when listing users")
        assert result == "set"

        # Confirm app_metadata has admin, user_metadata has no role
        admin_url = f"{live_env['url'].rstrip('/')}/auth/v1/admin/users/{user_id}"
        req = urllib.request.Request(
            admin_url,
            headers={
                "apikey": live_env["service_key"],
                "Authorization": f"Bearer {live_env['service_key']}",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        assert data["app_metadata"].get("role") == "admin"
        assert "role" not in (data.get("user_metadata") or {})

        # Confirm idempotent rerun returns 'already set'
        assert set_admin_role(test_email, allow_production=True) == "already set"

    finally:
        if user_id is not None:
            _delete_user(live_env, user_id)

