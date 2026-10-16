"""Institutional registration submission and admin review routes."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.app.auth.dependencies import get_current_user, require_admin
from backend.app.auth.models import UserClaims
from backend.app.config.env import load_settings
from backend.app.db.connection import get_connection

router = APIRouter(prefix="/api", tags=["verifications"])


class SubmitVerificationRequest(BaseModel):
    """Institutional regulator registration submission payload."""

    model_config = ConfigDict(extra="forbid")

    regulator: str = Field(
        min_length=2, max_length=50, description="Regulator name, e.g. SEBI, RBI"
    )
    registration_number: str = Field(min_length=3, max_length=100)


class ReviewVerificationRequest(BaseModel):
    """Admin review decision payload."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject"]
    review_notes: str | None = None


class VerificationResponse(BaseModel):
    """Institutional verification record response."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    user_id: uuid.UUID
    regulator: str
    registration_number: str
    status: str
    review_notes: str | None = None


@router.post("/verifications", response_model=VerificationResponse)
def submit_verification(
    payload: SubmitVerificationRequest,
    user: Annotated[UserClaims, Depends(get_current_user)],
    request: Request,
) -> VerificationResponse:
    """Submit regulator registration for institutional account verification."""
    settings = getattr(request.app.state, "settings", None) or load_settings()
    conn = get_connection(settings)
    try:
        with conn.cursor() as cur:
            # Check segment
            cur.execute("SELECT segment FROM public.profiles WHERE user_id = %s;", (user.user_id,))
            row = cur.fetchone()
            if not row or row[0] != "institutional":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "segment_mismatch",
                        "message": "Only institutional accounts can submit verification",
                    },
                )

            # Insert verification record
            v_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO public.institutional_verifications (
                    id, user_id, regulator, registration_number, status
                ) VALUES (
                    %s, %s, %s, %s, 'pending'
                ) RETURNING id, user_id, regulator, registration_number, status;
                """,
                (v_id, user.user_id, payload.regulator, payload.registration_number),
            )
            created = cur.fetchone()
            assert created is not None
        conn.commit()
    finally:
        conn.close()

    return VerificationResponse(
        id=created[0],
        user_id=created[1],
        regulator=created[2],
        registration_number=created[3],
        status=created[4],
    )


@router.post("/admin/verifications/{verification_id}/review", response_model=VerificationResponse)
def review_verification(
    verification_id: uuid.UUID,
    payload: ReviewVerificationRequest,
    admin: Annotated[UserClaims, Depends(require_admin)],
    request: Request,
) -> VerificationResponse:
    """Review and approve/reject institutional verification.

    Upon approval, upgrades user profile to institutional_paid.
    """
    settings = getattr(request.app.state, "settings", None) or load_settings()
    conn = get_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, regulator, registration_number, status
                FROM public.institutional_verifications
                WHERE id = %s;
                """,
                (verification_id,),
            )
            v_row = cur.fetchone()
            if not v_row:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "code": "verification_not_found",
                        "message": "Verification record not found",
                    },
                )

            v_user_id = v_row[1]
            new_status = "approved" if payload.action == "approve" else "rejected"

            cur.execute(
                """
                UPDATE public.institutional_verifications
                SET status = %s, rejection_reason = %s, reviewed_by = %s, reviewed_at = now()
                WHERE id = %s
                RETURNING id, user_id, regulator, registration_number, status, rejection_reason;
                """,
                (new_status, payload.review_notes, admin.user_id, verification_id),
            )
            updated = cur.fetchone()
            assert updated is not None

            # If approved, upgrade profile plan to institutional_paid
            if payload.action == "approve":
                cur.execute(
                    """
                    UPDATE public.profiles
                    SET plan = 'institutional_paid', updated_at = now()
                    WHERE user_id = %s;
                    """,
                    (v_user_id,),
                )
        conn.commit()
    finally:
        conn.close()

    return VerificationResponse(
        id=updated[0],
        user_id=updated[1],
        regulator=updated[2],
        registration_number=updated[3],
        status=updated[4],
        review_notes=updated[5],
    )
