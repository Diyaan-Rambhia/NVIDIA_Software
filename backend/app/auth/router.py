"""Authentication and profile routes."""

import json
import logging
import urllib.request
from typing import Annotated
from urllib.error import HTTPError

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    SignUpRequest,
    SignUpResponse,
    UserClaims,
    UserProfileResponse,
)

from backend.app.config.env import load_settings
from backend.app.db.connection import get_connection

logger = logging.getLogger("backend.app.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=SignUpResponse)
def signup(payload: SignUpRequest, request: Request) -> SignUpResponse:
    """Create account via Supabase Auth and initialize public profile."""
    if not payload.tos_accepted:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "tos_required",
                "message": "Terms of Service and educational disclaimer must be accepted",
            },
        )

    settings = getattr(request.app.state, "settings", None) or load_settings()
    supabase_url = settings.get_var_value("SUPABASE_URL")
    service_key = settings.get_var_value("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_key:
        raise HTTPException(
            status_code=500,
            detail={"code": "config_error", "message": "Supabase credentials are not configured"},
        )

    # Determine default plan per segment
    default_plan = "retail_free" if payload.segment == "retail" else "institutional_free"

    # Create user in Supabase Auth via Admin API
    admin_signup_url = f"{supabase_url.rstrip('/')}/auth/v1/admin/users"
    user_payload = {
        "email": payload.email,
        "password": payload.password,
        "email_confirm": False,  # requires verification
        "app_metadata": {"role": "user"},
        "user_metadata": {"email_verified": False, "segment": payload.segment},
    }

    req = urllib.request.Request(
        admin_signup_url,
        data=json.dumps(user_payload).encode("utf-8"),
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            user_id_str = data.get("id")
    except HTTPError as exc:
        err_msg = exc.read().decode("utf-8")
        logger.warning("Supabase user creation failed (%s): %s", exc.code, err_msg)
        if exc.code == 422:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "user_already_exists",
                    "message": "User with this email already exists",
                },
            ) from exc
        raise HTTPException(
            status_code=exc.code,
            detail={
                "code": "auth_provider_error",
                "message": f"Auth provider rejected signup: {exc.code}",
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "auth_creation_failed", "message": str(exc)},
        ) from exc

    import uuid

    user_uuid = uuid.UUID(user_id_str)

    # Insert into public.profiles
    conn = get_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.profiles (
                    user_id, segment, plan, role, status, tos_accepted_version, tos_accepted_at
                ) VALUES (
                    %s, %s, %s, 'user', 'active', %s, now()
                ) ON CONFLICT (user_id) DO UPDATE SET
                    segment = EXCLUDED.segment,
                    plan = EXCLUDED.plan,
                    tos_accepted_version = EXCLUDED.tos_accepted_version;
                """,
                (user_uuid, payload.segment, default_plan, payload.tos_version),
            )
        conn.commit()
    finally:
        conn.close()

    return SignUpResponse(
        user_id=user_uuid,
        email=str(payload.email),
        segment=payload.segment,
        plan=default_plan,
        requires_email_verification=True,
        message=(
            "Account created successfully. Please verify your email before "
            "accessing analytical features."
        ),
    )


@router.get("/me", response_model=UserProfileResponse)
def get_me(
    user: Annotated[UserClaims, Depends(get_current_user)], request: Request
) -> UserProfileResponse:
    """Return profile details for authenticated user."""
    settings = getattr(request.app.state, "settings", None) or load_settings()
    conn = get_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT segment, plan, role, status, tos_accepted_version
                FROM public.profiles
                WHERE user_id = %s;
                """,
                (user.user_id,),
            )

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "code": "profile_not_found",
                        "message": "User profile not found in database",
                    },
                )
            segment, plan, role, status_val, tos_v = row
    finally:
        conn.close()

    return UserProfileResponse(
        user_id=user.user_id,
        email=user.email,
        segment=segment,
        plan=plan,
        role=role,
        status=status_val,
        tos_accepted_version=tos_v,
    )


def map_supabase_auth_error(status_code: int, raw_body: str) -> tuple[int, str, str]:
    """Map Supabase Auth error HTTP status and response body to (http_status, error_code, error_message).

    Guarantees distinct, user-informative messages for:
    - Wrong credentials (invalid_credentials)
    - Unconfirmed email (email_not_confirmed)
    - Paused project / maintenance (project_paused)
    - Other upstream errors
    """
    body_lower = raw_body.lower() if raw_body else ""
    code = "auth_error"
    message = f"Authentication failed (HTTP {status_code})"

    if (
        status_code in (502, 503, 504)
        or ("project" in body_lower and "paused" in body_lower)
        or "service unavailable" in body_lower
    ):
        return 503, "project_paused", "Database project is paused or undergoing maintenance. Please try again later."

    try:
        err_json = json.loads(raw_body)
    except Exception:
        err_json = {}

    supa_err = str(err_json.get("error", "")).lower()
    supa_desc = str(err_json.get("error_description", "") or err_json.get("msg", "")).lower()
    supa_code = str(err_json.get("error_code", "") or err_json.get("code", "")).lower()

    if supa_code == "email_not_confirmed" or "email not confirmed" in supa_desc or "email not confirmed" in body_lower:
        return 400, "email_not_confirmed", "Email address is not confirmed. Please check your inbox and verify your email before logging in."

    if (
        supa_code == "invalid_credentials"
        or "invalid login credentials" in supa_desc
        or supa_err == "invalid_grant"
        or "invalid" in supa_desc
    ):
        return 401, "invalid_credentials", "Invalid email or password. Please verify your credentials."

    if err_json.get("error_description"):
        return status_code, supa_code or "auth_error", str(err_json["error_description"])
    if err_json.get("msg"):
        return status_code, supa_code or "auth_error", str(err_json["msg"])

    return status_code, code, message


@router.post("/token", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request) -> LoginResponse:
    """Exchange email and password for Supabase access token."""
    settings = getattr(request.app.state, "settings", None) or load_settings()
    supabase_url = settings.get_var_value("SUPABASE_URL")
    anon_key = (
        settings.get_var_value("SUPABASE_ANON_KEY")
        or settings.get_var_value("SUPABASE_SERVICE_ROLE_KEY")
    )

    if not supabase_url or not anon_key:
        raise HTTPException(
            status_code=500,
            detail={"code": "config_error", "message": "Supabase credentials are not configured"},
        )

    import uuid

    token_url = f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password"
    auth_payload = {
        "email": str(payload.email),
        "password": payload.password,
    }
    req = urllib.request.Request(
        token_url,
        data=json.dumps(auth_payload).encode("utf-8"),
        headers={
            "apikey": anon_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return LoginResponse(
                access_token=data["access_token"],
                token_type=data.get("token_type", "bearer"),
                user_id=uuid.UUID(data["user"]["id"]),
                refresh_token=data.get("refresh_token"),
            )
    except HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        logger.warning("Supabase login failed (%s): %s", exc.code, raw_body)
        status_code, err_code, err_message = map_supabase_auth_error(exc.code, raw_body)
        raise HTTPException(
            status_code=status_code,
            detail={"code": err_code, "message": err_message},
        ) from exc
    except urllib.error.URLError as exc:
        logger.error("Supabase network failure during login: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "network_failure",
                "message": "Network failure connecting to authentication server. Please check your connection.",
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "auth_error", "message": str(exc)},
        ) from exc


@router.post("/refresh", response_model=RefreshResponse)
def refresh_token_endpoint(payload: RefreshRequest, request: Request) -> RefreshResponse:
    """Exchange Supabase refresh token for fresh access token and refresh token."""
    settings = getattr(request.app.state, "settings", None) or load_settings()
    supabase_url = settings.get_var_value("SUPABASE_URL")
    anon_key = (
        settings.get_var_value("SUPABASE_ANON_KEY")
        or settings.get_var_value("SUPABASE_SERVICE_ROLE_KEY")
    )

    if not supabase_url or not anon_key:
        raise HTTPException(
            status_code=500,
            detail={"code": "config_error", "message": "Supabase credentials are not configured"},
        )

    import uuid

    refresh_url = f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=refresh_token"
    auth_payload = {
        "refresh_token": payload.refresh_token,
    }
    req = urllib.request.Request(
        refresh_url,
        data=json.dumps(auth_payload).encode("utf-8"),
        headers={
            "apikey": anon_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            user_id_str = data.get("user", {}).get("id")
            if not user_id_str:
                raise ValueError("Missing user id in refresh response")
            return RefreshResponse(
                access_token=data["access_token"],
                token_type=data.get("token_type", "bearer"),
                refresh_token=data.get("refresh_token"),
                user_id=uuid.UUID(user_id_str),
            )
    except HTTPError as exc:
        # Any bad/expired refresh token returns 401 per specification; never log token
        logger.warning("Supabase token refresh failed with HTTP %s", exc.code)
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_refresh_token", "message": "Invalid or expired refresh token"},
        ) from exc
    except urllib.error.URLError as exc:
        logger.error("Supabase network failure during token refresh: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "network_failure",
                "message": "Network failure connecting to authentication server. Please check your connection.",
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "auth_error", "message": str(exc)},
        ) from exc



