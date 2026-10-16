"""Pydantic models for authentication and user profiles."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictAuthModel(BaseModel):
    """Base model for auth contracts forbidding unknown fields."""

    model_config = ConfigDict(extra="forbid")


class UserClaims(StrictAuthModel):
    """Authenticated user context extracted from verified JWT."""

    user_id: uuid.UUID
    email: str
    role: str = "user"
    is_admin: bool = False
    segment: str | None = None
    plan: str | None = None
    app_metadata: dict[str, Any] = Field(default_factory=dict)
    user_metadata: dict[str, Any] = Field(default_factory=dict)


class SignUpRequest(StrictAuthModel):
    """Sign up payload."""

    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    password: str = Field(min_length=8)
    segment: Literal["retail", "institutional"]
    tos_accepted: bool = Field(
        description="Must accept Terms of Service and educational disclaimer"
    )
    tos_version: str = Field(default="v1")


class SignUpResponse(StrictAuthModel):
    """Sign up response."""

    user_id: uuid.UUID
    email: str
    segment: str
    plan: str
    requires_email_verification: bool = True
    message: str


class UserProfileResponse(StrictAuthModel):
    """User profile response."""

    user_id: uuid.UUID
    email: str
    segment: str
    plan: str
    role: str
    status: str
    tos_accepted_version: str | None = None


class LoginRequest(StrictAuthModel):
    """User login payload."""

    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1)


class LoginResponse(StrictAuthModel):
    """User login response."""

    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID

