"""FastAPI dependencies for user authentication and authorization."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from backend.app.auth.exceptions import (
    AuthError,
    EmailNotVerifiedError,
)
from backend.app.auth.jwt import verify_jwt
from backend.app.auth.models import UserClaims
from backend.app.config.env import load_settings
from backend.app.db.connection import get_connection


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> UserClaims:
    """Extract and verify Bearer JWT from Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={"code": "missing_token", "message": "Authorization header missing"},
        )

    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_token", "message": "Bearer token required"},
        )

    token = parts[1]
    settings = getattr(request.app.state, "settings", None) or load_settings()

    try:
        # We can pass db connection for email verification fallback if needed
        conn = None
        try:
            conn = get_connection(settings)
        except Exception:
            conn = None

        try:
            claims = verify_jwt(token, settings=settings, db_conn=conn)
        finally:
            if conn is not None:
                conn.close()

    except EmailNotVerifiedError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "email_not_verified", "message": exc.message},
        ) from exc
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_token", "message": str(exc)},
        ) from exc

    # Load profile details from database
    try:
        conn = get_connection(settings)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT segment, plan, role, status FROM public.profiles WHERE user_id = %s;",
                (claims.user_id,),
            )
            row = cur.fetchone()
            if row:
                claims.segment = row[0]
                claims.plan = row[1]
        conn.close()
    except Exception:
        pass

    return claims


async def require_admin(
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> UserClaims:
    """Ensure authenticated user has admin role in app_metadata."""
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "Administrator privileges required"},
        )
    return user
