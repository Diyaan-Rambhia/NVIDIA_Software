"""Tests for Feature 3 hosted demo mode and upload refusal."""

from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.app.auth.models import UserClaims
from backend.app.config.loader import load_all_config
from backend.app.features.f3_log.router import _require_f3
from backend.app.main import create_app


@pytest.fixture
def judge_claims() -> UserClaims:
    return UserClaims(
        user_id="00000000-0000-0000-0000-000000000001",
        email="judge@example.com",
        plan="judge_all",
        role="judge",
        segment="institutional",
    )


def test_f3_upload_hosted_demo_mode_returns_503(judge_claims: UserClaims) -> None:
    """When hosted_demo_mode is True, POST /f3/review returns 503 with exact clear message."""
    app = create_app()
    app.dependency_overrides[_require_f3] = lambda: judge_claims

    # Ensure hosted_demo_mode is true in state
    all_cfg = load_all_config()
    param = all_cfg.parameters.parameters.get("hosted_demo_mode")
    assert param is not None
    assert param.default is True

    client = TestClient(app)
    payload = {
        "csv_text": "Date,Symbol,Side,Quantity,Price\n2024-01-01,INFY,BUY,10,1500.0\n",
        "mapping": {
            "date": "Date",
            "symbol": "Symbol",
            "side": "Side",
            "quantity": "Quantity",
            "price": "Price",
        },
        "consent_given": False,
        "benchmark_symbol": "NSEI",
    }
    resp = client.post("/f3/review", json=payload)
    assert resp.status_code == 503
    data = resp.json()
    err_msg = data.get("error", {}).get("message") or data.get("detail", {}).get("message")
    assert err_msg == "not available in the hosted demo: benchmark data is not shipped"


def test_f3_upload_local_mode_allows_upload(judge_claims: UserClaims, monkeypatch: pytest.MonkeyPatch) -> None:
    """When hosted_demo_mode is False (local mode), POST /f3/review executes upload."""
    app = create_app()
    app.dependency_overrides[_require_f3] = lambda: judge_claims

    all_cfg = load_all_config()
    all_cfg.parameters.parameters["hosted_demo_mode"].default = False
    app.state.all_config = all_cfg

    from backend.app.contracts.portfolio import DecisionReview
    from backend.app.features.f3_log import router as f3_router
    demo_json = (Path("demo_data") / "f3_review_demo.json").read_text(encoding="utf-8")
    real_review = DecisionReview.model_validate_json(demo_json)
    monkeypatch.setattr(f3_router, "execute_feature3_review", lambda **kwargs: real_review)

    client = TestClient(app)
    payload = {
        "csv_text": "Date,Symbol,Side,Quantity,Price\n2024-01-01,INFY,BUY,10,1500.0\n",
        "mapping": {
            "date": "Date",
            "symbol": "Symbol",
            "side": "Side",
            "quantity": "Quantity",
            "price": "Price",
        },
        "consent_given": False,
        "benchmark_symbol": "NSEI",
    }
    resp = client.post("/f3/review", json=payload)
    assert resp.status_code == 200
