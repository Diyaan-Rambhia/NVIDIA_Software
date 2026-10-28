"""Razorpay payment gateway service for order creation and plan upgrades.

Per PROJECT.md §4.11, §6.5, and FR-PAY-001..011.
Enforces:
- Segment-restricted purchasing (institutional plans require verified registration).
- Non-purchasable judge_all protection.
- Currency INR, amounts in Paise.
- Real test mode credentials in .env.
"""

import base64
import json
import logging
import urllib.request
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

from fastapi import HTTPException

from backend.app.auth.models import UserClaims
from backend.app.config.env import Settings, load_settings
from backend.app.config.loader import load_all_config

logger = logging.getLogger("backend.app.payments.service")

PLANS_PATH = Path("config") / "plans.yaml"


def get_available_plans() -> dict[str, Any]:
    """Retrieve purchasable plans and pricing configuration."""
    cfg = load_all_config()
    return cfg.plans.plans


def create_razorpay_order(
    user: UserClaims,
    plan_name: str,
    settings: Settings | None = None,
    conn: Any = None,
) -> dict[str, Any]:
    """Create a new payment order with Razorpay test mode.

    Fails loudly if payment gateway credentials are not configured.
    """
    import os

    st = settings or load_settings()
    key_id = (
        st.get_var_value("PAYMENT_KEY_ID")
        or st.get_var_value("RAZORPAY_KEY_ID")
        or os.environ.get("PAYMENT_KEY_ID")
        or os.environ.get("RAZORPAY_KEY_ID")
    )
    key_secret = (
        st.get_var_value("PAYMENT_KEY_SECRET")
        or st.get_var_value("RAZORPAY_KEY_SECRET")
        or os.environ.get("PAYMENT_KEY_SECRET")
        or os.environ.get("RAZORPAY_KEY_SECRET")
    )

    # 1. Plan eligibility check
    plans = get_available_plans()
    if plan_name not in plans:
        raise HTTPException(
            status_code=404,
            detail={"code": "plan_not_found", "message": f"Plan '{plan_name}' does not exist"},
        )

    plan = plans[plan_name]
    if not plan.purchasable or plan_name == "judge_all":
        raise HTTPException(
            status_code=403,
            detail={"code": "plan_not_purchasable", "message": f"Plan '{plan_name}' is not purchasable"},
        )

    # 2. Segment and verification guard
    if plan.segment == "institutional" and plan_name == "institutional_paid":
        if user.role != "admin":
            if user.segment != "institutional":
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "segment_restricted",
                        "message": "Only institutional accounts can purchase institutional plans",
                    },
                )
            if conn is not None:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT status FROM public.institutional_verifications WHERE user_id = %s ORDER BY id DESC LIMIT 1;",
                        (user.user_id,),
                    )
                    row = cur.fetchone()
                    if not row or row[0] != "approved":
                        raise HTTPException(
                            status_code=403,
                            detail={
                                "code": "institutional_verification_required",
                                "message": "Institutional verification must be approved before purchasing institutional plan",
                            },
                        )

    # 3. Calculate amount in paise
    price_inr = plan.price_inr_per_month or 0
    amount_paise = int(price_inr * 100)
    if amount_paise <= 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "free_plan_no_payment", "message": "Free plans do not require payment processing"},
        )

    # 4. Gateway credentials check
    if not key_id or not key_secret:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "payment_gateway_unconfigured",
                "message": "RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required for payment processing.",
            },
        )

    # 5. Order creation call to Razorpay
    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"rcpt_{str(user.user_id)[:8]}_{plan_name}",
        "notes": {
            "user_id": str(user.user_id),
            "email": user.email,
            "plan_name": plan_name,
        },
    }

    url = "https://api.razorpay.com/v1/orders"
    auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode("utf-8")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "order_id": data.get("id"),
                "amount": data.get("amount"),
                "currency": data.get("currency"),
                "key_id": key_id,
                "plan_name": plan_name,
            }
    except HTTPError as exc:
        err_msg = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=502,
            detail={"code": "payment_gateway_error", "message": f"Razorpay returned {exc.code}: {err_msg}"},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "payment_gateway_error", "message": f"Failed to connect to Razorpay: {exc}"},
        ) from exc
