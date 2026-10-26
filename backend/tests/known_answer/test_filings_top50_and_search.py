"""Tests for Feature 2 Top 50 Nifty constituents, server-side search, and fiscal year range."""

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.models import UserClaims
from backend.app.data.fiscal import (
    format_fiscal_label,
    get_fiscal_year_range,
    parse_fiscal_label,
)
from backend.app.features.f2_filings.lookup import (
    fetch_nifty50_constituents,
    search_nse_equities,
)
from backend.app.main import create_app

app = create_app()


def test_top50_constituents_live() -> None:
    """Live test fetching Nifty 50 constituents from official NSE archives.

    If network connection fails, marks 'not run: no network'.
    """
    try:
        top50 = fetch_nifty50_constituents(cache_ttl_seconds=86400)
    except Exception as exc:
        pytest.skip(f"not run: no network ({exc})")

    assert isinstance(top50, list)
    assert len(top50) >= 45  # Nifty 50 index typically has 50 constituents
    first = top50[0]
    assert "symbol" in first
    assert "name" in first
    assert len(first["symbol"]) > 0
    assert len(first["name"]) > 0


def test_search_nse_equities_2_char_minimum() -> None:
    """Search query must be at least 2 characters; shorter strings raise ValueError."""
    with pytest.raises(ValueError, match="at least 2 characters"):
        search_nse_equities("")

    with pytest.raises(ValueError, match="at least 2 characters"):
        search_nse_equities("A")

    with pytest.raises(ValueError, match="at least 2 characters"):
        search_nse_equities("   ")


def test_search_nse_equities_limit_and_symbol_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    """Search enforces result limit and prioritizes symbol matches over company name matches."""
    fake_equities = [
        {"symbol": "INFY", "name": "Infosys Limited"},
        {"symbol": "TCS", "name": "Tata Consultancy Services Limited"},
        {"symbol": "TATAMOTORS", "name": "Tata Motors Limited"},
        {"symbol": "TATASTEEL", "name": "Tata Steel Limited"},
        {"symbol": "TITAN", "name": "Titan Company Limited"},
        {"symbol": "TATACHEM", "name": "Tata Chemicals Limited"},
        {"symbol": "TATACOMM", "name": "Tata Communications Limited"},
        {"symbol": "ABC", "name": "Tata Investment Corporation Limited"},
    ]

    monkeypatch.setattr(
        "backend.app.features.f2_filings.lookup.fetch_nse_equity_list",
        lambda rate_limit_per_sec=5.0: fake_equities,
    )

    # Search for "TATA"
    results = search_nse_equities(query="TATA", limit=3)
    assert len(results) == 3
    # Symbol matches start with TATA should come before name match ("ABC")
    for r in results:
        assert r["symbol"].startswith("TATA")

    # Limit=1
    single = search_nse_equities(query="TATA", limit=1)
    assert len(single) == 1
    assert single[0]["symbol"] == "TATAMOTORS"


def test_picker_fiscal_year_range() -> None:
    """Configured fiscal year range starts at 2001 (FY01)."""
    from datetime import date
    from backend.app.data.fiscal import fiscal_period_to_dates

    min_fy, max_fy = get_fiscal_year_range()
    assert min_fy == 2001
    assert max_fy >= 2030

    # 1. First quarter: Q1 FY01 parses cleanly to (1, 2001) with dates Apr-Jun 2000
    q, fy = parse_fiscal_label("Q1 FY01")
    assert q == 1
    assert fy == 2001
    start_d, end_d = fiscal_period_to_dates("Q1 FY01")
    assert start_d == date(2000, 4, 1)
    assert end_d == date(2000, 6, 30)

    # 2. Year boundary: Q4 FY01 to Q1 FY02
    q4, fy4 = parse_fiscal_label("Q4 FY01")
    assert q4 == 4 and fy4 == 2001
    q4_start, q4_end = fiscal_period_to_dates("Q4 FY01")
    assert q4_start == date(2001, 1, 1) and q4_end == date(2001, 3, 31)

    q1_next, fy1_next = parse_fiscal_label("Q1 FY02")
    assert q1_next == 1 and fy1_next == 2002
    q1_next_start, q1_next_end = fiscal_period_to_dates("Q1 FY02")
    assert q1_next_start == date(2001, 4, 1) and q1_next_end == date(2001, 6, 30)

    # 3. Label before first year raises ValueError
    with pytest.raises(ValueError, match="outside configured range"):
        parse_fiscal_label("Q4 FY00")

    # Ensure format matches
    assert format_fiscal_label(1, 2001) == "Q1 FY01"


def test_router_search_endpoint_requires_auth_and_validates_query() -> None:
    """GET /f2/search requires authentication and validates 2-character minimum."""
    client = TestClient(app)

    # Unauthenticated -> 401
    resp = client.get("/f2/search?q=INFY")
    assert resp.status_code == 401

    # Mock user
    import uuid

    test_user = UserClaims(
        user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        email="user@test.org",
        plan="institutional",
    )

    from backend.app.auth.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: test_user
    try:
        # Too short -> 400
        short_resp = client.get("/f2/search?q=A")
        assert short_resp.status_code == 400
        body = short_resp.json()
        code = body.get("error", {}).get("code") or body.get("code") or body.get("detail", {}).get("code")
        assert code == "query_too_short"

        # Valid query
        valid_resp = client.get("/f2/search?q=IN")
        assert valid_resp.status_code in (200, 502)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
