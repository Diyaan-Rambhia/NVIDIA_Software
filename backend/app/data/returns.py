"""Pure return calculations and Indian trading calendar alignment utilities."""

import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Literal


def calculate_returns(
    prices: Sequence[float],
    kind: Literal["log", "simple"] = "log",
) -> list[float]:
    """Calculate returns from a sequence of strictly positive prices.

    Supported kinds:
    - 'log': r_t = ln(P_t / P_{t-1}) per PROJECT.md §5.1
    - 'simple': r_t = (P_t - P_{t-1}) / P_{t-1}
    """
    if len(prices) == 0:
        raise ValueError("Prices sequence cannot be empty")

    for p in prices:
        if not isinstance(p, (int, float)) or math.isnan(p) or math.isinf(p):
            raise ValueError(f"Price must be a finite real number, found: {p!r}")
        if p <= 0:
            raise ValueError(f"Price values must be strictly positive, found: {p}")

    if len(prices) < 2:
        return []

    returns: list[float] = []
    for i in range(1, len(prices)):
        prev = prices[i - 1]
        curr = prices[i]
        if kind == "log":
            returns.append(math.log(curr / prev))
        elif kind == "simple":
            returns.append((curr - prev) / prev)
        else:
            raise ValueError(f"Unsupported return kind: '{kind}'. Allowed: 'log', 'simple'")

    return returns


def daily_log_returns(prices: Sequence[float]) -> list[float]:
    """Calculate daily log returns r_t = ln(P_t / P_{t-1}) per PROJECT.md §5.1."""
    return calculate_returns(prices, kind="log")


def _normalize_date(d: date | datetime) -> date:
    """Extract standard date object while checking datetime validity."""
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    raise ValueError(f"Expected date or datetime object, found: {type(d)}")


def _validate_calendar(calendar_days: Sequence[date | datetime]) -> list[date]:
    """Validate calendar days are non-empty, unique, sorted, and consistently typed."""
    if not calendar_days:
        raise ValueError("Calendar days sequence cannot be empty")

    # Check naive vs timezone-aware datetime mix if datetimes are present
    has_naive = any(isinstance(d, datetime) and d.tzinfo is None for d in calendar_days)
    has_aware = any(isinstance(d, datetime) and d.tzinfo is not None for d in calendar_days)
    if has_naive and has_aware:
        raise ValueError("Calendar contains mixed naive and timezone-aware datetimes")

    dates = [_normalize_date(d) for d in calendar_days]

    for i in range(1, len(dates)):
        if dates[i] <= dates[i - 1]:
            if dates[i] == dates[i - 1]:
                raise ValueError(f"Calendar days contain duplicate date: {dates[i]}")
            raise ValueError(
                f"Calendar days must be sorted in strictly ascending order: {dates[i - 1]} >= {dates[i]}"
            )

    return dates


def _extract_series_dict(
    series: Mapping[date | datetime, float] | Sequence[tuple[date | datetime, float]],
) -> dict[date, float]:
    """Extract and validate series map into dict[date, float]."""
    if isinstance(series, Mapping):
        if not series:
            raise ValueError("Series cannot be empty")
        raw_items = list(series.items())
    elif isinstance(series, Sequence):
        if not series:
            raise ValueError("Series cannot be empty")
        raw_items = list(series)
    else:
        raise ValueError("Series must be a mapping or sequence of (date, price) tuples")

    # Check naive vs aware mix
    has_naive = any(isinstance(k, datetime) and k.tzinfo is None for k, _ in raw_items)
    has_aware = any(isinstance(k, datetime) and k.tzinfo is not None for k, _ in raw_items)
    if has_naive and has_aware:
        raise ValueError("Series contains mixed naive and timezone-aware datetimes")

    series_map: dict[date, float] = {}
    for raw_d, price in raw_items:
        d = _normalize_date(raw_d)
        if d in series_map:
            raise ValueError(f"Series contains duplicate date: {d}")
        if not isinstance(price, (int, float)) or math.isnan(price) or math.isinf(price):
            raise ValueError(f"Series price must be a finite number, found: {price!r}")
        if price <= 0:
            raise ValueError(f"Series price must be strictly positive, found: {price}")
        series_map[d] = float(price)

    return series_map


def align_series(
    series: Mapping[date | datetime, float] | Sequence[tuple[date | datetime, float]],
    calendar_days: Sequence[date | datetime],
) -> list[float]:
    """Align a single series onto the provided trading calendar.

    Fails loud on missing days or misaligned extra dates.
    """
    valid_calendar = _validate_calendar(calendar_days)
    series_map = _extract_series_dict(series)

    calendar_set = set(valid_calendar)
    series_set = set(series_map.keys())

    missing = calendar_set - series_set
    if missing:
        raise ValueError(
            f"Series is missing data for required trading date(s): {sorted(missing)}"
        )

    extra = series_set - calendar_set
    if extra:
        raise ValueError(
            f"Series contains dates outside the provided trading calendar: {sorted(extra)}"
        )

    return [series_map[d] for d in valid_calendar]


def align_multiple_series(
    series_map: Mapping[
        str, Mapping[date | datetime, float] | Sequence[tuple[date | datetime, float]]
    ],
    calendar_days: Sequence[date | datetime],
) -> dict[str, list[float]]:
    """Align multiple named series onto a common Indian trading calendar."""
    if not series_map:
        raise ValueError("series_map cannot be empty")

    valid_calendar = _validate_calendar(calendar_days)
    aligned: dict[str, list[float]] = {}

    for name, s in series_map.items():
        try:
            aligned[name] = align_series(s, valid_calendar)
        except ValueError as exc:
            raise ValueError(f"Alignment error for series '{name}': {exc}") from exc

    return aligned
