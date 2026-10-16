"""Unit tests for authentication, pinned ES256 JWT verification, and atomic quotas."""

import base64
import json
import time
import uuid
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from fastapi.testclient import TestClient

from backend.app.auth.exceptions import (
    AuthError,
    EmailNotVerifiedError,
    InvalidTokenError,
    MissingTokenError,
)
from backend.app.auth.jwt import verify_jwt
from backend.app.auth.models import UserClaims
from backend.app.config.env import Settings
from backend.app.main import create_app

# Test key pair for unit tests
_TEST_PRIV = ec.generate_private_key(ec.SECP256R1())
_TEST_PUB = _TEST_PRIV.public_key()
_TEST_KID = "test-key-id-001"


def _make_jwt(claims: dict, alg: str = "ES256", kid: str | None = _TEST_KID) -> str:
    header: dict[str, str] = {"alg": alg, "typ": "JWT"}
    if kid:
        header["kid"] = kid

    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")

    if alg == "ES256":
        der_sig = _TEST_PRIV.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der_sig)
        raw_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        s_b64 = base64.urlsafe_b64encode(raw_sig).decode().rstrip("=")
    elif alg == "none":
        s_b64 = ""
    else:
        # e.g. HS256 dummy signature
        s_b64 = base64.urlsafe_b64encode(b"0" * 32).decode().rstrip("=")

    return f"{h_b64}.{p_b64}.{s_b64}"


@pytest.fixture(autouse=True)
def mock_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock JWKS keys for unit testing."""
    monkeypatch.setattr(
        "backend.app.auth.jwt.fetch_jwks_keys",
        lambda *args, **kwargs: {_TEST_KID: _TEST_PUB},
    )


def test_missing_token_raises_missing_token_error() -> None:
    """Missing token raises MissingTokenError."""
    with pytest.raises(MissingTokenError):
        verify_jwt(None)
    with pytest.raises(MissingTokenError):
        verify_jwt("")


def test_malformed_token_raises_invalid_token_error() -> None:
    """Malformed token structure raises InvalidTokenError."""
    with pytest.raises(InvalidTokenError):
        verify_jwt("not.a.valid.jwt.token")
    with pytest.raises(InvalidTokenError):
        verify_jwt("single_part_token")


def test_jwt_alg_none_rejected() -> None:
    """Algorithm 'none' is rejected."""
    claims = {"sub": str(uuid.uuid4()), "exp": int(time.time()) + 3600}
    token = _make_jwt(claims, alg="none", kid=None)
    with pytest.raises(InvalidTokenError) as exc_info:
        verify_jwt(token)
    assert "expected 'ES256'" in str(exc_info.value)


def test_jwt_wrong_algorithm_rejected() -> None:
    """Unexpected algorithms (e.g. RS256) are rejected."""
    claims = {"sub": str(uuid.uuid4()), "exp": int(time.time()) + 3600}
    token = _make_jwt(claims, alg="RS256", kid=_TEST_KID)
    with pytest.raises(InvalidTokenError) as exc_info:
        verify_jwt(token)
    assert "expected 'ES256'" in str(exc_info.value)


def test_jwt_hs256_presented_to_es256_setup_rejected() -> None:
    """HS256 tokens presented to pinned ES256 setup are rejected."""
    claims = {"sub": str(uuid.uuid4()), "exp": int(time.time()) + 3600}
    token = _make_jwt(claims, alg="HS256", kid=_TEST_KID)
    with pytest.raises(InvalidTokenError) as exc_info:
        verify_jwt(token)
    assert "expected 'ES256'" in str(exc_info.value)


def test_jwks_fetch_failure_raises_and_never_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWKS fetch failure raises AuthError and never falls back."""
    monkeypatch.setattr(
        "backend.app.auth.jwt.fetch_jwks_keys",
        MagicMock(
            side_effect=AuthError("JWKS unreachable", code="jwks_fetch_failed", status_code=503)
        ),
    )
    claims = {"sub": str(uuid.uuid4()), "exp": int(time.time()) + 3600}
    token = _make_jwt(claims, alg="ES256", kid=_TEST_KID)
    with pytest.raises(AuthError) as exc_info:
        verify_jwt(token)
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "jwks_fetch_failed"


def test_unverified_email_raises_email_not_verified_error() -> None:
    """Valid token payload with unverified email raises EmailNotVerifiedError."""
    settings = MagicMock(spec=Settings)
    settings.get_var_value.side_effect = lambda k: (
        "https://example.supabase.co" if k == "SUPABASE_URL" else "test"
    )

    claims = {
        "sub": str(uuid.uuid4()),
        "email": "unverified@example.com",
        "exp": int(time.time()) + 3600,
        "app_metadata": {"role": "user"},
        "user_metadata": {"email_verified": False},
    }
    token = _make_jwt(claims)

    with pytest.raises(EmailNotVerifiedError) as exc_info:
        verify_jwt(token, settings=settings)
    assert exc_info.value.code == "email_not_verified"
    assert exc_info.value.status_code == 403


def test_absent_verification_field_raises_error() -> None:
    """When email verification field is absent and no db record exists, raise AuthError."""
    settings = MagicMock(spec=Settings)
    settings.get_var_value.side_effect = lambda k: (
        "https://example.supabase.co" if k == "SUPABASE_URL" else "test"
    )

    claims = {
        "sub": str(uuid.uuid4()),
        "email": "user@example.com",
        "exp": int(time.time()) + 3600,
        "app_metadata": {"role": "user"},
        "user_metadata": {},
    }
    token = _make_jwt(claims)

    with pytest.raises(AuthError) as exc_info:
        verify_jwt(token, settings=settings, db_conn=None)
    assert exc_info.value.code == "verification_field_absent"


def test_admin_role_read_from_app_metadata_only() -> None:
    """Role must be extracted exclusively from app_metadata, ignoring user_metadata."""
    settings = MagicMock(spec=Settings)
    settings.get_var_value.side_effect = lambda k: (
        "https://example.supabase.co" if k == "SUPABASE_URL" else "test"
    )

    claims = {
        "sub": str(uuid.uuid4()),
        "email": "hacker@example.com",
        "exp": int(time.time()) + 3600,
        "app_metadata": {"role": "user"},
        "user_metadata": {"role": "admin", "email_verified": True},
    }
    token = _make_jwt(claims)

    res = verify_jwt(token, settings=settings)
    assert res.role == "user"
    assert res.is_admin is False


def test_api_auth_missing_token_returns_401_error_envelope() -> None:
    """Accessing protected endpoint without token returns 401 ErrorEnvelope."""
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "missing_token"


def test_api_admin_non_admin_returns_403() -> None:
    """Non-admin authenticated user receives 403 on admin review endpoint."""
    app = create_app()
    from backend.app.auth.dependencies import get_current_user

    dummy_user = UserClaims(
        user_id=uuid.uuid4(),
        email="regular@example.com",
        role="user",
        is_admin=False,
    )
    app.dependency_overrides[get_current_user] = lambda: dummy_user

    client = TestClient(app)
    v_id = uuid.uuid4()
    resp = client.post(
        f"/api/admin/verifications/{v_id}/review",
        json={"action": "approve"},
        headers={"Authorization": "Bearer dummy_token"},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == "forbidden"


def test_map_supabase_auth_error_mappings() -> None:
    """map_supabase_auth_error maps wrong credentials, unconfirmed email, and paused project to distinct errors."""
    from backend.app.auth.router import map_supabase_auth_error

    # 1. Wrong credentials
    s1, c1, m1 = map_supabase_auth_error(
        400, json.dumps({"error": "invalid_grant", "error_description": "Invalid login credentials"})
    )
    assert s1 == 401
    assert c1 == "invalid_credentials"
    assert "Invalid email or password" in m1

    # 2. Unconfirmed email
    s2, c2, m2 = map_supabase_auth_error(
        400, json.dumps({"error": "invalid_grant", "error_description": "Email not confirmed"})
    )
    assert s2 == 400
    assert c2 == "email_not_confirmed"
    assert "not confirmed" in m2

    # 3. Paused project (503 or body text)
    s3, c3, m3 = map_supabase_auth_error(503, "upstream connect error or disconnect/reset before headers. reset reason: connection termination")
    assert s3 == 503
    assert c3 == "project_paused"
    assert "paused" in m3

    s4, c4, m4 = map_supabase_auth_error(200, json.dumps({"message": "Project is paused"}))
    assert s4 == 503
    assert c4 == "project_paused"
    assert "paused" in m4

    # 4. Ensure each error produces a distinct message
    messages = {m1, m2, m3}
    assert len(messages) == 3


def test_api_auth_token_network_failure_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """Network failure during Supabase login returns HTTP 503 with network_failure code."""
    import urllib.error
    from backend.app.config.env import Settings

    def mock_urlopen(*args, **kwargs):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    app = create_app(
        settings=Settings(app_env="production", supabase_url="https://mock.supabase.co", supabase_anon_key="mock-key"),
        runtime_groups=[],
    )
    client = TestClient(app)

    resp = client.post("/api/auth/token", json={"email": "judge@fininsight.local", "password": "anypassword123"})
    assert resp.status_code == 503
    data = resp.json()
    err_obj = data.get("error") or data.get("detail")
    assert err_obj["code"] == "network_failure"
    assert "Network failure" in err_obj["message"]

