"""Billing and Payments API router for Razorpay checkout and webhooks."""

import hashlib
import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import UserClaims
from backend.app.config.env import load_settings
from backend.app.db.connection import get_connection
from backend.app.payments.service import create_razorpay_order, get_available_plans
from backend.app.payments.webhook import process_payment_event, verify_razorpay_signature

router = APIRouter(prefix="/api/billing", tags=["billing"])


class CreateOrderRequest(BaseModel):
    """Payload to initiate an upgrade order."""

    plan_name: str = Field(..., min_length=2, max_length=50)


class CreateOrderResponse(BaseModel):
    """Created Razorpay order details."""

    order_id: str
    amount: int
    currency: str
    key_id: str
    plan_name: str


class VerifyPaymentRequest(BaseModel):
    """Payload for client-side payment signature verification."""

    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan_name: str


@router.get("/plans")
def list_billing_plans() -> dict[str, Any]:
    """Retrieve purchasable subscription plans, quotas, and monthly prices."""
    plans = get_available_plans()
    return {
        name: {
            "segment": p.segment,
            "purchasable": p.purchasable,
            "price_inr_per_month": p.price_inr_per_month,
            "features": {
                f_name: {
                    "access": f_val.access,
                    "quota_per_day": f_val.quota_per_day,
                }
                for f_name, f_val in p.features.items()
            },
        }
        for name, p in plans.items()
    }


@router.post("/create-order", response_model=CreateOrderResponse)
def create_billing_order(
    payload: CreateOrderRequest,
    user: Annotated[UserClaims, Depends(get_current_user)],
    request: Request,
) -> CreateOrderResponse:
    """Create a new payment order for subscription plan upgrade."""
    settings = getattr(request.app.state, "settings", None) or load_settings()
    conn = None
    try:
        conn = get_connection(settings)
    except Exception:
        conn = None

    try:
        order_data = create_razorpay_order(
            user=user,
            plan_name=payload.plan_name,
            settings=settings,
            conn=conn,
        )
        return CreateOrderResponse(
            order_id=order_data["order_id"],
            amount=order_data["amount"],
            currency=order_data["currency"],
            key_id=order_data["key_id"],
            plan_name=order_data["plan_name"],
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


@router.post("/verify")
def verify_payment(
    payload: VerifyPaymentRequest,
    user: Annotated[UserClaims, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    """Verify client checkout signature and upgrade user profile."""
    settings = getattr(request.app.state, "settings", None) or load_settings()
    key_secret = settings.get_var_value("RAZORPAY_KEY_SECRET")

    if not key_secret:
        raise HTTPException(
            status_code=503,
            detail={"code": "payment_gateway_unconfigured", "message": "Razorpay secret is not configured"},
        )

    # Razorpay standard client signature check: HMAC_SHA256(order_id + "|" + payment_id, secret)
    message = f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}"
    computed = hmac.new(key_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, payload.razorpay_signature):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_payment_signature", "message": "Payment signature verification failed"},
        )

    # Signature valid: promote user plan
    conn = get_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.profiles
                SET plan = %s, updated_at = now()
                WHERE user_id = %s;
                """,
                (payload.plan_name, user.user_id),
            )
        conn.commit()
    finally:
        conn.close()

    return {
        "status": "success",
        "message": f"Successfully upgraded account to {payload.plan_name}",
        "plan": payload.plan_name,
    }


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Cryptographic server webhook receiving payment lifecycle events from Razorpay."""
    import os

    settings = getattr(request.app.state, "settings", None) or load_settings()
    webhook_secret = (
        settings.get_var_value("PAYMENT_WEBHOOK_SECRET")
        or settings.get_var_value("RAZORPAY_WEBHOOK_SECRET")
        or settings.get_var_value("PAYMENT_KEY_SECRET")
        or settings.get_var_value("RAZORPAY_KEY_SECRET")
        or os.environ.get("PAYMENT_WEBHOOK_SECRET")
        or os.environ.get("RAZORPAY_WEBHOOK_SECRET")
        or os.environ.get("PAYMENT_KEY_SECRET")
        or os.environ.get("RAZORPAY_KEY_SECRET")
    )

    if not webhook_secret:
        raise HTTPException(
            status_code=503,
            detail={"code": "webhook_unconfigured", "message": "Razorpay webhook secret is not configured"},
        )

    if not x_razorpay_signature:
        raise HTTPException(
            status_code=400,
            detail={"code": "missing_signature", "message": "X-Razorpay-Signature header is required"},
        )

    raw_body = await request.body()
    if not verify_razorpay_signature(raw_body, x_razorpay_signature, webhook_secret):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_signature", "message": "Webhook signature verification failed"},
        )

    import json
    event_payload = json.loads(raw_body.decode("utf-8"))

    conn = None
    try:
        conn = get_connection(settings)
    except Exception:
        conn = None

    try:
        result = process_payment_event(event_payload, conn=conn)
        return result
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
