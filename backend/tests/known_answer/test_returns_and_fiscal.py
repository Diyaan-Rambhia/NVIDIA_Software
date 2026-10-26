"""Known-answer and validation tests for returns, calendar alignment, and fiscal periods."""

import math
from datetime import date, datetime, timezone

import pytest

from backend.app.data.fiscal import (
    date_to_fiscal_period,
    fiscal_period_to_dates,
    format_fiscal_label,
    parse_fiscal_label,
)
from backend.app.data.returns import (
    align_multiple_series,
    align_series,
    calculate_returns,
    daily_log_returns,
)

# ---------------------------------------------------------------------------
# Returns Tests
# ---------------------------------------------------------------------------


def test_daily_log_returns_hand_computed() -> None:
    """Verify log returns against exact math.log ratios on hand-computed series."""
    prices = [100.0, 110.0, 121.0]
    expected = [math.log(1.1), math.log(1.1)]

    res = daily_log_returns(prices)
    assert len(res) == 2
    for actual, exp in zip(res, expected, strict=True):
        assert math.isclose(actual, exp, rel_tol=1e-12)


def test_simple_returns_hand_computed() -> None:
    """Verify simple arithmetic percentage returns."""
    prices = [100.0, 120.0, 90.0]
    expected = [0.20, -0.25]

    res = calculate_returns(prices, kind="simple")
    assert len(res) == 2
    for actual, exp in zip(res, expected, strict=True):
        assert math.isclose(actual, exp, rel_tol=1e-12)


def test_returns_single_price_returns_empty() -> None:
    """A series with a single observation produces no returns."""
    assert calculate_returns([50.0]) == []


def test_returns_empty_prices_raises() -> None:
    """Empty prices sequence must raise ValueError."""
    with pytest.raises(ValueError, match="cannot be empty"):
        calculate_returns([])


@pytest.mark.parametrize("bad_val", [0.0, -10.0, float("nan"), float("inf")])
def test_returns_invalid_prices_raise(bad_val: float) -> None:
    """Non-positive or non-finite price values must raise ValueError."""
    with pytest.raises(ValueError):
        calculate_returns([100.0, bad_val])


def test_returns_unsupported_kind_raises() -> None:
    """Unsupported return kind must raise ValueError."""
    with pytest.raises(ValueError, match="Unsupported return kind"):
        calculate_returns([100.0, 110.0], kind="other")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Calendar Alignment Tests
# ---------------------------------------------------------------------------


def test_align_series_success() -> None:
    """Align series matching calendar days in exact order."""
    d0 = date(2026, 6, 1)
    d1 = date(2026, 6, 2)
    d2 = date(2026, 6, 3)

    calendar = [d0, d1, d2]
    series_data = {d2: 103.0, d0: 101.0, d1: 102.0}

    aligned = align_series(series_data, calendar)
    assert aligned == [101.0, 102.0, 103.0]


def test_align_multiple_series_success() -> None:
    """Align multiple series simultaneously."""
    d0 = date(2026, 6, 1)
    d1 = date(2026, 6, 2)

    calendar = [d0, d1]
    series_map: dict[str, dict[date, float] | list[tuple[date, float]]] = {
        "series_a": {d0: 10.0, d1: 20.0},
        "series_b": [(d0, 100.0), (d1, 200.0)],
    }

    result = align_multiple_series(series_map, calendar)
    assert result["series_a"] == [10.0, 20.0]
    assert result["series_b"] == [100.0, 200.0]


def test_align_series_gap_missing_day_raises() -> None:
    """Series missing any required trading calendar date must raise ValueError."""
    d0 = date(2026, 6, 1)
    d1 = date(2026, 6, 2)
    d2 = date(2026, 6, 3)

    calendar = [d0, d1, d2]
    # Series is missing d1
    series_data = {d0: 100.0, d2: 102.0}

    with pytest.raises(ValueError, match="missing data"):
        align_series(series_data, calendar)


def test_align_series_extra_date_raises() -> None:
    """Series with date outside the trading calendar must raise ValueError."""
    d0 = date(2026, 6, 1)
    d1 = date(2026, 6, 2)
    extra = date(2026, 6, 5)

    calendar = [d0, d1]
    series_data = {d0: 100.0, d1: 101.0, extra: 102.0}

    with pytest.raises(ValueError, match="outside the provided trading calendar"):
        align_series(series_data, calendar)


def test_align_calendar_unsorted_raises() -> None:
    """Unsorted trading calendar must raise ValueError."""
    d0 = date(2026, 6, 1)
    d1 = date(2026, 6, 2)

    with pytest.raises(ValueError, match="strictly ascending order"):
        align_series({d0: 1.0, d1: 2.0}, [d1, d0])


def test_align_calendar_duplicate_raises() -> None:
    """Duplicate dates in calendar must raise ValueError."""
    d0 = date(2026, 6, 1)

    with pytest.raises(ValueError, match="duplicate date"):
        align_series({d0: 1.0}, [d0, d0])


def test_align_series_duplicate_date_raises() -> None:
    """Sequence series containing duplicate dates must raise ValueError."""
    d0 = date(2026, 6, 1)
    d1 = date(2026, 6, 2)

    series_seq = [(d0, 100.0), (d0, 105.0), (d1, 110.0)]
    with pytest.raises(ValueError, match="duplicate date"):
        align_series(series_seq, [d0, d1])


def test_align_mixed_naive_aware_raises() -> None:
    """Mixing naive and timezone-aware datetimes must raise ValueError."""
    dt_naive = datetime(2026, 6, 1, 10, 0)
    dt_aware = datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="mixed naive and timezone-aware"):
        align_series({dt_naive: 1.0, dt_aware: 2.0}, [dt_naive, dt_aware])


# ---------------------------------------------------------------------------
# Fiscal Period Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,exp_q,exp_fy",
    [
        ("Q1 FY27", 1, 2027),
        ("Q2 FY27", 2, 2027),
        ("Q3 FY27", 3, 2027),
        ("Q4 FY27", 4, 2027),
        ("Q1 FY26", 1, 2026),
        ("Q1 FY24", 1, 2024),
        ("Q4 FY28", 4, 2028),
    ],
)
def test_parse_and_format_fiscal_label_roundtrip(label: str, exp_q: int, exp_fy: int) -> None:
    """Verify parsing and formatting canonical fiscal labels."""
    q, fy = parse_fiscal_label(label)
    assert q == exp_q
    assert fy == exp_fy
    assert format_fiscal_label(q, fy) == label


def test_two_digit_fiscal_year_century_mapping_and_boundaries() -> None:
    """Pin two-digit fiscal year century mapping rule: 2000 + short_year."""
    assert parse_fiscal_label("Q1 FY00", min_year=2000, max_year=2099) == (1, 2000)
    assert parse_fiscal_label("Q4 FY99", min_year=2000, max_year=2099) == (4, 2099)
    assert parse_fiscal_label("Q1 FY27") == (1, 2027)
    assert format_fiscal_label(1, 2000, min_year=2000, max_year=2099) == "Q1 FY00"
    assert format_fiscal_label(4, 2099, min_year=2000, max_year=2099) == "Q4 FY99"


def test_fiscal_year_range_bounds() -> None:
    """Labels outside the configured fiscal-year range [2001, 2030] must raise ValueError."""
    with pytest.raises(ValueError, match="outside configured range"):
        parse_fiscal_label("Q1 FY00")

    with pytest.raises(ValueError, match="outside configured range"):
        parse_fiscal_label("Q4 FY00")

    with pytest.raises(ValueError, match="outside configured range"):
        parse_fiscal_label("Q4 FY99")

    with pytest.raises(ValueError, match="outside configured range"):
        format_fiscal_label(1, 2000)

    with pytest.raises(ValueError, match="outside configured range"):
        format_fiscal_label(1, 2035)


def test_first_fiscal_year_fy01_and_boundaries() -> None:
    """Check that labels from Q1 FY01 to current quarters parse and format correctly."""
    # First quarter
    q1, fy1 = parse_fiscal_label("Q1 FY01")
    assert (q1, fy1) == (1, 2001)
    assert format_fiscal_label(1, 2001) == "Q1 FY01"

    # Year boundaries
    q4, fy_end = parse_fiscal_label("Q4 FY01")
    assert (q4, fy_end) == (4, 2001)
    assert format_fiscal_label(4, 2001) == "Q4 FY01"

    q1_next, fy_next = parse_fiscal_label("Q1 FY02")
    assert (q1_next, fy_next) == (1, 2002)
    assert format_fiscal_label(1, 2002) == "Q1 FY02"

    # Label before the first year raises
    with pytest.raises(ValueError, match="outside configured range"):
        parse_fiscal_label("Q4 FY00")


@pytest.mark.parametrize(
    "label,start_date,end_date",
    [
        ("Q1 FY27", date(2026, 4, 1), date(2026, 6, 30)),
        ("Q2 FY27", date(2026, 7, 1), date(2026, 9, 30)),
        ("Q3 FY27", date(2026, 10, 1), date(2026, 12, 31)),
        ("Q4 FY27", date(2027, 1, 1), date(2027, 3, 31)),
    ],
)
def test_fiscal_period_to_dates(label: str, start_date: date, end_date: date) -> None:
    """Verify period boundary start and end dates."""
    s, e = fiscal_period_to_dates(label)
    assert s == start_date
    assert e == end_date


@pytest.mark.parametrize(
    "d,expected_label",
    [
        (date(2026, 4, 1), "Q1 FY27"),
        (date(2026, 6, 30), "Q1 FY27"),
        (date(2026, 7, 1), "Q2 FY27"),
        (date(2026, 9, 30), "Q2 FY27"),
        (date(2026, 10, 1), "Q3 FY27"),
        (date(2026, 12, 31), "Q3 FY27"),
        (date(2027, 1, 1), "Q4 FY27"),
        (date(2027, 3, 31), "Q4 FY27"),
        (date(2027, 4, 1), "Q1 FY28"),
    ],
)
def test_date_to_fiscal_period(d: date, expected_label: str) -> None:
    """Verify calendar date mapping to Indian fiscal quarter."""
    assert date_to_fiscal_period(d) == expected_label


@pytest.mark.parametrize(
    "bad_label",
    [
        "Q1-FY27",
        "q1 fy27",
        "Q1 FY2027",
        "2026-Q1",
        "FY27",
        "Q0 FY27",
        "Q5 FY27",
        "Q1FY27",
        "",
        "INVALID",
    ],
)
def test_parse_fiscal_label_rejects_non_canonical(bad_label: str) -> None:
    """Any non-canonical label format must be rejected."""
    with pytest.raises(ValueError, match="Invalid fiscal period label"):
        parse_fiscal_label(bad_label)


def test_format_fiscal_label_invalid_inputs_raise() -> None:
    """Invalid quarter or negative year must raise ValueError."""
    with pytest.raises(ValueError, match="Quarter must be an integer"):
        format_fiscal_label(0, 2027)

    with pytest.raises(ValueError, match="Quarter must be an integer"):
        format_fiscal_label(5, 2027)

    with pytest.raises(ValueError, match="Fiscal year must be a positive integer"):
        format_fiscal_label(1, -2027)
