"""Known-answer tests for Razorpay payment order creation and webhook verification."""

import hashlib
import hmac
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import UserClaims
from backend.app.main import create_app
from backend.app.payments.webhook import (
    process_payment_event,
    verify_razorpay_signature,
)


@pytest.fixture
def retail_user() -> UserClaims:
    return UserClaims(
        user_id=uuid.uuid4(),
        email="retail@example.com",
        plan="retail_free",
        role="user",
        segment="retail",
    )


def test_list_billing_plans():
    """Verify listing available subscription plans."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/billing/plans")
    assert resp.status_code == 200
    data = resp.json()
    assert "retail_free" in data
    assert "retail_paid" in data
    assert "institutional_paid" in data
    assert data["retail_paid"]["price_inr_per_month"] == 499
    assert data["institutional_paid"]["price_inr_per_month"] == 4999


def test_create_order_unconfigured_gateway(retail_user: UserClaims, monkeypatch):
    """Verify order creation fails loudly when payment gateway credentials are not configured."""
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: retail_user
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
    monkeypatch.delenv("PAYMENT_KEY_ID", raising=False)
    monkeypatch.delenv("PAYMENT_KEY_SECRET", raising=False)

    client = TestClient(app)
    resp = client.post("/api/billing/create-order", json={"plan_name": "retail_paid"})
    assert resp.status_code == 503
    data = resp.json()
    err_code = data.get("error", {}).get("code") or data.get("detail", {}).get("code")
    assert err_code == "payment_gateway_unconfigured"


def test_create_order_judge_all_prohibited(retail_user: UserClaims):
    """Verify judge_all plan cannot be purchased."""
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: retail_user

    client = TestClient(app)
    resp = client.post("/api/billing/create-order", json={"plan_name": "judge_all"})
    assert resp.status_code == 403
    data = resp.json()
    err_code = data.get("error", {}).get("code") or data.get("detail", {}).get("code")
    assert err_code == "plan_not_purchasable"


def test_verify_razorpay_signature():
    """Verify HMAC SHA-256 signature verification mathematics."""
    secret = "test_webhook_secret_key_12345"
    body = b'{"event":"payment.captured","id":"evt_12345"}'

    valid_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert verify_razorpay_signature(body, valid_sig, secret) is True
    assert verify_razorpay_signature(body, "bad_signature_string", secret) is False


def test_webhook_endpoint_signature_verification(monkeypatch):
    """Verify webhook endpoint rejects invalid signature and accepts valid signature."""
    secret = "test_webhook_secret_key_12345"
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", secret)

    app = create_app()
    client = TestClient(app)

    event_data = {
        "id": f"evt_{uuid.uuid4().hex[:10]}",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_123",
                    "amount": 49900,
                    "currency": "INR",
                    "notes": {
                        "user_id": str(uuid.uuid4()),
                        "plan_name": "retail_paid",
                    },
                }
            }
        },
    }
    raw_bytes = json.dumps(event_data).encode("utf-8")
    valid_sig = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

    # 1. Invalid signature returns 400
    bad_resp = client.post(
        "/api/billing/webhook",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "invalid"},
    )
    assert bad_resp.status_code == 400
    bad_data = bad_resp.json()
    bad_err_code = bad_data.get("error", {}).get("code") or bad_data.get("detail", {}).get("code")
    assert bad_err_code == "invalid_signature"

    # 2. Valid signature returns 200
    good_resp = client.post(
        "/api/billing/webhook",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_sig},
    )
    assert good_resp.status_code == 200
    assert good_resp.json()["status"] == "processed"

    # 3. Duplicate event returns ignored (idempotency check)
    dup_resp = client.post(
        "/api/billing/webhook",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_sig},
    )
    assert dup_resp.status_code == 200
    assert dup_resp.json()["status"] == "ignored"
