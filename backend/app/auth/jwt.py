"""JWT verification and decoding logic for Supabase Auth."""

import base64
import json
import logging
import time
import urllib.request
import uuid
from typing import Any
from urllib.error import URLError

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from backend.app.auth.exceptions import (
    AuthError,
    EmailNotVerifiedError,
    ExpiredTokenError,
    InvalidTokenError,
    MissingTokenError,
)
from backend.app.auth.models import UserClaims
from backend.app.config.env import Settings, load_settings

logger = logging.getLogger("backend.app.auth")

# In-memory cache for JWKS keys: kid -> EllipticCurvePublicKey
_JWKS_CACHE: dict[str, ec.EllipticCurvePublicKey] = {}


def _b64_decode(data: str) -> bytes:
    """Decode base64url string with required padding."""
    rem = len(data) % 4
    if rem > 0:
        data += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data.encode("ascii"))


def fetch_jwks_keys(
    supabase_url: str, anon_key: str | None = None
) -> dict[str, ec.EllipticCurvePublicKey]:
    """Fetch and parse ES256 public keys from the Supabase JWKS endpoint."""
    global _JWKS_CACHE
    if _JWKS_CACHE:
        return _JWKS_CACHE

    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    req = urllib.request.Request(jwks_url)
    if anon_key:
        req.add_header("apikey", anon_key)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AuthError(
            f"Failed to fetch JWKS keys: {exc.__class__.__name__}",
            code="jwks_fetch_failed",
            status_code=503,
        ) from exc

    key_map: dict[str, ec.EllipticCurvePublicKey] = {}
    for k in data.get("keys", []):
        if k.get("kty") == "EC" and k.get("crv") == "P-256" and "kid" in k:
            try:
                x_bytes = _b64_decode(k["x"])
                y_bytes = _b64_decode(k["y"])
                x_int = int.from_bytes(x_bytes, "big")
                y_int = int.from_bytes(y_bytes, "big")
                pub_num = ec.EllipticCurvePublicNumbers(x_int, y_int, ec.SECP256R1())
                key_map[k["kid"]] = pub_num.public_key()
            except Exception as exc:
                logger.warning("Failed to parse JWKS key %s: %s", k.get("kid"), exc)

    if not key_map:
        raise AuthError(
            "No valid EC public keys found in JWKS", code="no_jwks_keys", status_code=503
        )

    _JWKS_CACHE = key_map
    return _JWKS_CACHE


def verify_jwt(
    token: str | None,
    settings: Settings | None = None,
    db_conn: Any = None,
) -> UserClaims:
    """Verify Supabase JWT token and extract user claims.

    Rules:
    - Missing token -> 401 MissingTokenError
    - Invalid or expired token -> 401 InvalidTokenError / ExpiredTokenError
    - Unverified email -> 403 EmailNotVerifiedError (code: email_not_verified)
    - If verification field is absent from token or user record, raise
      (never treat absent as verified).
    - Role is read exclusively from app_metadata (never user_metadata).
    """

    if not token:
        raise MissingTokenError("Authentication token is required")

    parts = token.strip().split(".")
    if len(parts) != 3:
        raise InvalidTokenError("Malformed JWT structure")

    header_raw, payload_raw, sig_raw = parts

    try:
        header = json.loads(_b64_decode(header_raw).decode("utf-8"))
        claims = json.loads(_b64_decode(payload_raw).decode("utf-8"))
        signature_bytes = _b64_decode(sig_raw)
    except Exception as exc:
        raise InvalidTokenError(f"Failed to decode JWT payload: {exc}") from exc

    PINNED_ALGORITHM = "ES256"
    alg = header.get("alg")
    if alg != PINNED_ALGORITHM:
        raise InvalidTokenError(
            f"Unsupported or unexpected algorithm: '{alg}', expected '{PINNED_ALGORITHM}'"
        )

    kid = header.get("kid")

    if settings is None:
        settings = load_settings()

    supabase_url = settings.get_var_value("SUPABASE_URL")
    anon_key = settings.get_var_value("SUPABASE_ANON_KEY")

    if not supabase_url:
        raise AuthError("SUPABASE_URL is not configured", code="config_error", status_code=500)

    # Verify signature using pinned ES256 algorithm and JWKS public keys
    signing_input = f"{header_raw}.{payload_raw}".encode("ascii")

    keys = fetch_jwks_keys(supabase_url, anon_key)
    if not kid or kid not in keys:
        raise InvalidTokenError(f"Unknown or missing key ID (kid: {kid})")
    pub_key = keys[kid]

    if len(signature_bytes) != 64:
        raise InvalidTokenError("Invalid ES256 signature length")

    r = int.from_bytes(signature_bytes[:32], "big")
    s = int.from_bytes(signature_bytes[32:], "big")
    der_signature = encode_dss_signature(r, s)

    try:
        pub_key.verify(der_signature, signing_input, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise InvalidTokenError("Invalid token signature") from exc

    # Expiry verification
    now_ts = int(time.time())
    exp = claims.get("exp")
    if exp is None:
        raise InvalidTokenError("Missing 'exp' claim")
    if now_ts >= exp:
        raise ExpiredTokenError("Token has expired")

    # Extract user ID
    sub = claims.get("sub")
    if not sub:
        raise InvalidTokenError("Missing 'sub' subject claim")
    try:
        user_uuid = uuid.UUID(sub)
    except ValueError as exc:
        raise InvalidTokenError("Invalid subject UUID") from exc

    email = claims.get("email", "")

    # Role strictly from app_metadata only (never user_metadata)
    app_meta = claims.get("app_metadata")
    if not isinstance(app_meta, dict):
        app_meta = {}

    user_meta = claims.get("user_metadata")
    if not isinstance(user_meta, dict):
        user_meta = {}

    role = app_meta.get("role", "user")
    is_admin = role == "admin"

    # Email verification check:
    # Rule: valid token plus unverified email returns 403 with code email_not_verified.
    # If the verification field is absent from the token or user record, raise;
    # never treat absent as verified.
    email_verified: bool | None = None

    if "email_verified" in user_meta:
        val = user_meta["email_verified"]
        if isinstance(val, bool):
            email_verified = val
        elif isinstance(val, str):
            email_verified = val.lower() == "true"

    if email_verified is None and "email_confirmed_at" in claims:
        email_verified = claims["email_confirmed_at"] is not None

    # If verification field absent from token, check user record in database
    if email_verified is None:
        if db_conn is not None:
            with db_conn.cursor() as cur:
                cur.execute(
                    "SELECT email_confirmed_at FROM auth.users WHERE id = %s;", (user_uuid,)
                )
                row = cur.fetchone()
                if row is None:
                    raise AuthError(
                        "User record not found in auth.users",
                        code="user_not_found",
                        status_code=401,
                    )
                confirmed_at = row[0]
                email_verified = confirmed_at is not None
        else:
            # Cannot verify because field is absent from token and no db connection
            raise AuthError(
                "Email verification field is absent from token and user record; cannot verify",
                code="verification_field_absent",
                status_code=500,
            )

    if email_verified is False:
        raise EmailNotVerifiedError("Email verification is required before access")

    return UserClaims(
        user_id=user_uuid,
        email=email,
        role=role,
        is_admin=is_admin,
        app_metadata=app_meta,
        user_metadata=user_meta,
    )
