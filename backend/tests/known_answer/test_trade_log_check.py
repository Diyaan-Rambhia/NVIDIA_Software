"""Tests for trade log CSV row-error validation and hand-written two-row XIRR calculation."""

from datetime import date, timedelta
import math
import pytest

from backend.app.contracts.portfolio import ColumnMapping
from backend.app.features.f3_log.pipeline import (
    execute_feature3_review,
    parse_trade_log_csv,
)


def test_trade_log_row_errors_name_row_number() -> None:
    """Row errors must name the exact row number for missing price, negative quantity, bad date (Item 10)."""
    mapping = ColumnMapping(
        date="Date",
        symbol="Symbol",
        side="Side",
        quantity="Quantity",
        price="Price",
    )

    d0 = date.fromordinal(738000)
    d0_iso = d0.isoformat()

    # 1. Missing price on row 2 (first data row after header)
    csv_missing_price = (
        "Date,Symbol,Side,Quantity,Price\n"
        f"{d0_iso},INFY,BUY,10,\n"
    )
    with pytest.raises(ValueError) as exc_info:
        parse_trade_log_csv(csv_missing_price, mapping)
    assert "Row 2" in str(exc_info.value)
    assert "price" in str(exc_info.value).lower()

    # 2. Negative quantity on row 3 (second data row after header)
    d1_iso = (d0 + timedelta(days=1)).isoformat()
    csv_neg_qty = (
        "Date,Symbol,Side,Quantity,Price\n"
        f"{d0_iso},INFY,BUY,10,100.0\n"
        f"{d1_iso},INFY,BUY,-5,100.0\n"
    )
    with pytest.raises(ValueError) as exc_info_qty:
        parse_trade_log_csv(csv_neg_qty, mapping)
    assert "Row 3" in str(exc_info_qty.value)
    assert "strictly positive" in str(exc_info_qty.value)

    # 3. Bad date on row 4 (third data row after header)
    d2_iso = (d0 + timedelta(days=2)).isoformat()
    csv_bad_date = (
        "Date,Symbol,Side,Quantity,Price\n"
        f"{d0_iso},INFY,BUY,10,100.0\n"
        f"{d1_iso},INFY,BUY,5,100.0\n"
        "not-a-valid-date,INFY,BUY,5,100.0\n"
    )
    with pytest.raises(ValueError) as exc_info_date:
        parse_trade_log_csv(csv_bad_date, mapping)
    assert "Row 4" in str(exc_info_date.value)
    assert "invalid date format" in str(exc_info_date.value).lower()


def test_trade_log_two_row_xirr_exact_one_year(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hand-written two-row log: buy 10 at 100 on one date, sell 10 at 110 exactly 365 days later -> XIRR == 0.10 (Item 11)."""
    mapping = ColumnMapping(
        date="Date",
        symbol="Symbol",
        side="Side",
        quantity="Quantity",
        price="Price",
    )

    # Use ordinal arithmetic so no literal dates or calendar timestamps are written
    base_day = date.fromordinal(738500)
    later_day = base_day + timedelta(days=365)

    csv_text = (
        "Date,Symbol,Side,Quantity,Price\n"
        f"{base_day.isoformat()},TESTSYM,BUY,10,100.0\n"
        f"{later_day.isoformat()},TESTSYM,SELL,10,110.0\n"
    )

    trade_log = parse_trade_log_csv(csv_text, mapping)

    # Mock load_benchmark_price_history to avoid needing disk benchmark files during unit test
    import backend.app.features.f3_log.pipeline as f3_pipe

    mock_benchmark_prices = {
        base_day.isoformat(): 10000.0,
        later_day.isoformat(): 11000.0,
    }
    monkeypatch.setattr(f3_pipe, "load_benchmark_price_history", lambda sym: mock_benchmark_prices)

    review = execute_feature3_review(
        trade_log=trade_log,
        is_institutional=False,
    )

    # Cash flow 1: -1000.0, Cash flow 2: +1100.0 exactly 365 days later -> annualized XIRR is exactly 0.10
    assert review.portfolio_xirr is not None
    assert math.isclose(review.portfolio_xirr, 0.10, rel_tol=1e-4)

