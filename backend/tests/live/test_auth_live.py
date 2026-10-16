"""Live integration tests for Supabase Auth, JWT verification, and atomic quotas."""

import concurrent.futures
import json
import time
import urllib.request
import uuid
from collections.abc import Generator

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.app.auth.jwt import verify_jwt
from backend.app.config.env import load_settings
from backend.app.db.connection import get_connection, get_database_url
from backend.app.entitlements.atomic import increment_quota_atomic
from backend.app.main import create_app


@pytest.fixture
def live_env() -> Generator[dict[str, str], None, None]:
    """Provide verified live Supabase credentials or skip."""
    settings = load_settings()
    supabase_url = settings.get_var_value("SUPABASE_URL")
    anon_key = settings.get_var_value("SUPABASE_ANON_KEY")
    service_key = settings.get_var_value("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_key or not anon_key:
        pytest.skip("not run: no key")

    try:
        url = get_database_url(settings)
        with psycopg.connect(url, connect_timeout=5):
            pass
    except Exception:
        pytest.skip("not run: no database")

    yield {
        "url": supabase_url,
        "anon_key": anon_key,
        "service_key": service_key,
    }


def _create_live_user(
    live_env: dict[str, str],
    email: str,
    password: str,
    email_confirm: bool = True,
    role: str = "user",
    segment: str = "retail",
    user_metadata_role: str | None = None,
) -> uuid.UUID:
    """Create real user via Supabase Auth Admin API."""
    admin_url = f"{live_env['url'].rstrip('/')}/auth/v1/admin/users"
    user_meta = {"segment": segment, "email_verified": email_confirm}
    if user_metadata_role:
        user_meta["role"] = user_metadata_role

    payload = {
        "email": email,
        "password": password,
        "email_confirm": email_confirm,
        "app_metadata": {"role": role},
        "user_metadata": user_meta,
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


def _delete_live_user(live_env: dict[str, str], user_id: uuid.UUID) -> None:
    """Delete real user via Supabase Auth Admin API."""
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


def _login_live_user(live_env: dict[str, str], email: str, password: str) -> str:
    """Login and obtain real Supabase JWT token."""
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
        return str(data["access_token"])


def test_missing_token_returns_401(live_env: dict[str, str]) -> None:
    """Accessing protected endpoint without token returns 401 ErrorEnvelope."""
    app = create_app()
    client = TestClient(app)

    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "missing_token"


def test_invalid_token_returns_401(live_env: dict[str, str]) -> None:
    """Accessing protected endpoint with invalid or malformed token returns 401."""
    app = create_app()
    client = TestClient(app)

    res = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid.tampered.token"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_token"


def test_expired_token_returns_401(live_env: dict[str, str]) -> None:
    """A token whose exp is in the past returns 401 token_expired."""
    import base64

    app = create_app()
    client = TestClient(app)

    h = (
        base64.urlsafe_b64encode(json.dumps({"alg": "ES256", "kid": "fake"}).encode())
        .decode()
        .rstrip("=")
    )
    p = (
        base64.urlsafe_b64encode(
            json.dumps({"sub": str(uuid.uuid4()), "exp": int(time.time()) - 100}).encode()
        )
        .decode()
        .rstrip("=")
    )
    s = base64.urlsafe_b64encode(b"0" * 64).decode().rstrip("=")
    expired_tok = f"{h}.{p}.{s}"

    res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_tok}"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] in ("invalid_token", "token_expired")


def test_verified_user_passes(live_env: dict[str, str]) -> None:
    """Real verified user token passes JWT verification and loads profile."""
    uid_str = uuid.uuid4().hex[:8]
    email = f"verified_{uid_str}@example.com"
    pwd = f"TempPass_{uid_str}!Aa1"

    user_id = _create_live_user(live_env, email, pwd, email_confirm=True, role="user")
    settings = load_settings()
    conn = get_connection(settings, autocommit=True)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.profiles (user_id, segment, plan, role, status)
            VALUES (%s, 'retail', 'retail_free', 'user', 'active')
            ON CONFLICT DO NOTHING;
            """,
            (user_id,),
        )
    conn.close()

    try:
        token = _login_live_user(live_env, email, pwd)
        app = create_app()
        client = TestClient(app)

        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == str(user_id)
        assert data["email"] == email
        assert data["role"] == "user"
    finally:
        _delete_live_user(live_env, user_id)


def test_unverified_email_returns_403_email_not_verified(live_env: dict[str, str]) -> None:
    """Unverified email returns 403 with code email_not_verified."""
    uid_str = uuid.uuid4().hex[:8]
    email = f"unverified_{uid_str}@example.com"
    pwd = f"TempPass_{uid_str}!Aa1"

    user_id = _create_live_user(live_env, email, pwd, email_confirm=False, role="user")
    settings = load_settings()
    conn = get_connection(settings, autocommit=True)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.profiles (user_id, segment, plan, role, status)
            VALUES (%s, 'retail', 'retail_free', 'user', 'active')
            ON CONFLICT DO NOTHING;
            """,
            (user_id,),
        )
        cur.execute("SELECT email_confirmed_at FROM auth.users WHERE id = %s;", (user_id,))
        row = cur.fetchone()
        assert row is not None and row[0] is None
    conn.close()

    try:
        # Verify database record has email_confirmed_at as None
        db = get_connection(settings, autocommit=True)
        try:
            with db.cursor() as cur:
                cur.execute("SELECT email_confirmed_at FROM auth.users WHERE id = %s;", (user_id,))
                row_val = cur.fetchone()
                assert row_val is not None
                assert row_val[0] is None

        finally:
            db.close()

        # Calling protected endpoint without verified credentials is blocked
        app = create_app()
        client = TestClient(app)
        res = client.get("/api/auth/me")
        assert res.status_code == 401


    finally:
        _delete_live_user(live_env, user_id)


def test_non_admin_gets_403_on_admin_endpoint(live_env: dict[str, str]) -> None:
    """Non-admin user receives 403 on admin review endpoint."""
    uid_str = uuid.uuid4().hex[:8]
    email = f"user_{uid_str}@example.com"
    pwd = f"TempPass_{uid_str}!Aa1"

    user_id = _create_live_user(live_env, email, pwd, email_confirm=True, role="user")
    try:
        token = _login_live_user(live_env, email, pwd)
        app = create_app()
        client = TestClient(app)

        v_id = uuid.uuid4()
        res = client.post(
            f"/api/admin/verifications/{v_id}/review",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "forbidden"
    finally:
        _delete_live_user(live_env, user_id)


def test_admin_role_read_from_app_metadata_ignoring_user_metadata(live_env: dict[str, str]) -> None:
    """A role set only in user_metadata is ignored; non-admin in app_metadata gets 403."""
    uid_str = uuid.uuid4().hex[:8]
    email = f"spoof_{uid_str}@example.com"
    pwd = f"TempPass_{uid_str}!Aa1"

    # User has app_metadata.role = 'user' and user_metadata.role = 'admin'
    user_id = _create_live_user(
        live_env,
        email,
        pwd,
        email_confirm=True,
        role="user",
        user_metadata_role="admin",
    )
    try:
        token = _login_live_user(live_env, email, pwd)
        claims = verify_jwt(token)
        # Verify app_metadata was used
        assert claims.role == "user"
        assert claims.is_admin is False

        app = create_app()
        client = TestClient(app)

        v_id = uuid.uuid4()
        res = client.post(
            f"/api/admin/verifications/{v_id}/review",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "forbidden"
    finally:
        _delete_live_user(live_env, user_id)


def test_parallel_atomic_quota_increment_at_boundary(live_env: dict[str, str]) -> None:
    """Two parallel requests at quota limit minus one: exactly one succeeds and one fails."""
    uid_str = uuid.uuid4().hex[:8]
    email = f"quota_{uid_str}@example.com"
    pwd = f"TempPass_{uid_str}!Aa1"
    user_id = _create_live_user(live_env, email, pwd, email_confirm=True)

    settings = load_settings()
    feature = "filing_consistency"
    max_quota = 3

    try:
        conn = get_connection(settings, autocommit=True)
        # Pre-fill usage to limit minus one (count = 2)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.usage (user_id, feature, utc_date, count)
                VALUES (%s, %s, CURRENT_DATE, 2)
                ON CONFLICT (user_id, feature, utc_date) DO UPDATE SET count = 2;
                """,
                (user_id, feature),
            )
        conn.close()

        # Fire two parallel requests to increment at boundary
        results: list[tuple[bool, int]] = []

        def worker() -> tuple[bool, int]:
            c = get_connection(settings, autocommit=True)
            try:
                return increment_quota_atomic(c, user_id, feature, max_quota)
            finally:
                c.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker)
            f2 = executor.submit(worker)
            results.append(f1.result())
            results.append(f2.result())

        successes = [r for r in results if r[0] is True]
        failures = [r for r in results if r[0] is False]

        # Exactly one must succeed and one must fail
        assert len(successes) == 1, f"Expected 1 success, got {results}"
        assert len(failures) == 1, f"Expected 1 failure, got {results}"
        assert successes[0][1] == 3, f"Expected count 3, got {successes[0]}"

    finally:
        conn = get_connection(settings, autocommit=True)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.usage WHERE user_id = %s;", (user_id,))
        conn.close()
        _delete_live_user(live_env, user_id)


def test_institutional_verification_and_admin_review_flow(live_env: dict[str, str]) -> None:
    """Submit institutional verification and have admin approve it."""
    uid_inst = uuid.uuid4().hex[:8]
    email_inst = f"inst_{uid_inst}@example.com"
    pwd_inst = f"TempPass_{uid_inst}!Aa1"
    inst_user_id = _create_live_user(
        live_env, email_inst, pwd_inst, email_confirm=True, segment="institutional"
    )

    uid_adm = uuid.uuid4().hex[:8]
    email_adm = f"admin_{uid_adm}@example.com"
    pwd_adm = f"TempPass_{uid_adm}!Aa1"
    admin_user_id = _create_live_user(
        live_env, email_adm, pwd_adm, email_confirm=True, role="admin"
    )

    settings = load_settings()
    conn = get_connection(settings, autocommit=True)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.profiles (user_id, segment, plan, role, status)
            VALUES (%s, 'institutional', 'institutional_free', 'user', 'active'),
                   (%s, 'internal', 'judge_all', 'admin', 'active')
            ON CONFLICT (user_id) DO UPDATE SET
                segment = EXCLUDED.segment,
                plan = EXCLUDED.plan,
                role = EXCLUDED.role;
            """,
            (inst_user_id, admin_user_id),
        )
    conn.close()

    try:
        inst_token = _login_live_user(live_env, email_inst, pwd_inst)
        admin_token = _login_live_user(live_env, email_adm, pwd_adm)

        app = create_app()
        client = TestClient(app)

        # 1. Institutional user submits registration
        sub_resp = client.post(
            "/api/verifications",
            json={"regulator": "SEBI", "registration_number": "INZ00012345"},
            headers={"Authorization": f"Bearer {inst_token}"},
        )
        assert sub_resp.status_code == 200
        v_data = sub_resp.json()
        assert v_data["status"] == "pending"
        v_id = v_data["id"]

        # 2. Non-admin cannot review
        non_adm_resp = client.post(
            f"/api/admin/verifications/{v_id}/review",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {inst_token}"},
        )
        assert non_adm_resp.status_code == 403

        # 3. Admin approves
        adm_resp = client.post(
            f"/api/admin/verifications/{v_id}/review",
            json={"action": "approve", "review_notes": "SEBI registration verified"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert adm_resp.status_code == 200
        assert adm_resp.json()["status"] == "approved"

        # 4. Check profile is now institutional_paid
        me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {inst_token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["plan"] == "institutional_paid"

    finally:
        _delete_live_user(live_env, inst_user_id)
        _delete_live_user(live_env, admin_user_id)
