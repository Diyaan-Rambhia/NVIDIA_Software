"""Razorpay cryptographic webhook verification and subscription plan promotion.

Per PROJECT.md §4.11 and FR-PAY-003..007.
Enforces:
- HMAC SHA-256 signature verification with constant-time equality check.
- Idempotent processing rejecting duplicated event IDs.
- Automatic profile plan promotion on successful payment capture.
"""

import hashlib
import hmac
import logging
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger("backend.app.payments.webhook")

# In-memory processed events cache for fast replay rejection
_PROCESSED_EVENT_IDS: set[str] = set()


def verify_razorpay_signature(
    body: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify Razorpay HMAC SHA-256 signature using constant-time comparison."""
    if not signature or not secret:
        return False

    computed = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature.strip())


def process_payment_event(
    event_payload: dict[str, Any],
    conn: Any = None,
) -> dict[str, Any]:
    """Process verified payment event and upgrade user subscription plan."""
    global _PROCESSED_EVENT_IDS

    event_id = event_payload.get("id") or ""
    event_type = event_payload.get("event") or ""

    if not event_id:
        raise HTTPException(
            status_code=400,
            detail={"code": "missing_event_id", "message": "Webhook event missing 'id' identifier"},
        )

    # Idempotency check: replay protection
    if event_id in _PROCESSED_EVENT_IDS:
        logger.info("Ignoring duplicate webhook event %s", event_id)
        return {"status": "ignored", "reason": "already_processed", "event_id": event_id}

    if event_type in ("payment.captured", "order.paid"):
        payment_entity = (
            event_payload.get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )
        if not payment_entity:
            payment_entity = (
                event_payload.get("payload", {})
                .get("order", {})
                .get("entity", {})
            )

        notes = payment_entity.get("notes", {})
        user_id = notes.get("user_id")
        plan_name = notes.get("plan_name")

        if user_id and plan_name:
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE public.profiles
                            SET plan = %s, updated_at = now()
                            WHERE user_id = %s;
                            """,
                            (plan_name, user_id),
                        )
                    conn.commit()
                    logger.info("Successfully upgraded user %s to plan %s via webhook", user_id, plan_name)
                except Exception as exc:
                    logger.error("Failed to update profile for user %s: %s", user_id, exc)
                    raise HTTPException(
                        status_code=500,
                        detail={"code": "database_update_error", "message": str(exc)},
                    ) from exc

        _PROCESSED_EVENT_IDS.add(event_id)
        return {
            "status": "processed",
            "event_id": event_id,
            "event_type": event_type,
            "user_id": user_id,
            "plan_upgraded": plan_name,
        }

    _PROCESSED_EVENT_IDS.add(event_id)
    return {"status": "unhandled_event", "event_type": event_type}
