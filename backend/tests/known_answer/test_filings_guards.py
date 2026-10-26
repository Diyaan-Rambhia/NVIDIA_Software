"""Tests for filing consistency claim requirements, same-field guards, and financial company detection."""

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import UserClaims
from backend.app.contracts.filings import Claim, FilingMetric
from backend.app.entitlements.guard import require_feature
from backend.app.features.f2_filings.lookup import (
    UnsupportedCompanyTypeError,
    is_financial_company,
    perform_f2_lookup,
)
from backend.app.features.f2_filings.rules import (
    assert_not_same_field,
    evaluate_all_rules,
    evaluate_r0_stated_number,
)
from backend.app.main import create_app

app = create_app()


@pytest.fixture
def sample_metric() -> FilingMetric:
    return FilingMetric(
        company="Maruti Suzuki India Limited",
        symbol="MARUTI",
        fiscal_period="Q3 FY25",
        period_end_date="2024-12-31",
        basis="consolidated",
        metric="revenue",
        value=37500.0,
        unit="INR_Crore",
        source_filing_reference="NSE_XBRL_Q3FY25",
        derived=False,
        retrieval_time="2025-01-20T10:00:00Z",
    )


@pytest.fixture
def sample_claim() -> Claim:
    return Claim(
        metric="revenue",
        descriptor="strong",
        direction="grew",
        quote="revenue rose to 37500 crore",
        start=0,
        end=28,
        period="Q3 FY25",
        basis="reported",
    )


def test_quarter_with_no_claim_text_gives_not_applicable_for_r0(sample_metric: FilingMetric) -> None:
    """When no management claim text exists for a quarter, R0 returns not_applicable."""
    res_none = evaluate_r0_stated_number(None, sample_metric, stated_value=37500.0)
    assert res_none.rule_id == "R0"
    assert res_none.status == "not_applicable"
    assert "no management claim text available" in res_none.reason

    all_res = evaluate_all_rules(None, sample_metric, stated_value=37500.0)
    r0_eval = [r for r in all_res if r.rule_id == "R0"][0]
    assert r0_eval.status == "not_applicable"
    assert "no management claim text available" in r0_eval.reason


def test_same_field_guard_raises(sample_claim: Claim, sample_metric: FilingMetric) -> None:
    """assert_not_same_field raises ValueError if stated_value source and metric field are identical."""
    with pytest.raises(ValueError, match="cannot be the same field as filed metric"):
        assert_not_same_field("revenue", "revenue")

    with pytest.raises(ValueError, match="cannot be the same field as filed metric"):
        assert_not_same_field("  REVENUE  ", "revenue")

    # In evaluate_r0_stated_number, comparing identical fields raises ValueError
    with pytest.raises(ValueError, match="cannot be the same field as filed metric"):
        evaluate_r0_stated_number(
            sample_claim,
            sample_metric,
            stated_value=37500.0,
            stated_value_source="revenue",
        )


def test_financial_company_detection() -> None:
    """Financial companies are detected by symbol, name, and sector."""
    assert is_financial_company("HDFCBANK") is True
    assert is_financial_company("SBIN") is True
    assert is_financial_company("BAJFINANCE") is True
    assert is_financial_company("ICICIBANK") is True
    assert is_financial_company("HDFCLIFE") is True
    assert is_financial_company("MARUTI") is False
    assert is_financial_company("INFY") is False


def test_financial_company_lookup_raises() -> None:
    """perform_f2_lookup raises UnsupportedCompanyTypeError for financial companies."""
    import time
    from backend.app.features.f2_filings import lookup as lookup_mod

    prev_cache = lookup_mod._EQUITY_LIST_CACHE
    lookup_mod._EQUITY_LIST_CACHE = (
        time.time(),
        [
            {"symbol": "HDFCBANK", "name": "HDFC Bank Limited"},
            {"symbol": "SBIN", "name": "State Bank of India"},
        ] + (prev_cache[1] if prev_cache else []),
    )
    try:
        with pytest.raises(UnsupportedCompanyTypeError, match="financial companies are not covered"):
            perform_f2_lookup("HDFCBANK", "Q3 FY25")
    finally:
        lookup_mod._EQUITY_LIST_CACHE = prev_cache


def test_financial_company_endpoint_returns_422() -> None:
    """GET /f2/lookup returns HTTP 422 UNSUPPORTED_COMPANY_TYPE for banks and NBFCs."""
    import time
    from backend.app.features.f2_filings import lookup as lookup_mod

    prev_cache = lookup_mod._EQUITY_LIST_CACHE
    lookup_mod._EQUITY_LIST_CACHE = (
        time.time(),
        [
            {"symbol": "HDFCBANK", "name": "HDFC Bank Limited"},
            {"symbol": "SBIN", "name": "State Bank of India"},
        ] + (prev_cache[1] if prev_cache else []),
    )

    client = TestClient(app)
    test_user = UserClaims(
        user_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        email="auditor@test.org",
        plan="institutional_paid",
    )
    _require_f2 = require_feature("feature2_filings")
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[_require_f2] = lambda: test_user

    try:
        resp = client.get("/f2/lookup?company=HDFCBANK&period=Q3 FY25")
        assert resp.status_code == 422
        body = resp.json()
        err_obj = body.get("error", {})
        code = err_obj.get("code") or body.get("code")
        assert code == "UNSUPPORTED_COMPANY_TYPE"
        message = err_obj.get("message") or body.get("message")
        assert "financial companies are not covered" in message
    finally:
        lookup_mod._EQUITY_LIST_CACHE = prev_cache
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(_require_f2, None)
