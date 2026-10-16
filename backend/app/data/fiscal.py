"""Indian fiscal calendar and period label utilities per PROJECT.md §4.1 and §FR-FIL-006."""

import re
from datetime import date, datetime

from pathlib import Path

FISCAL_LABEL_REGEX = re.compile(r"^Q([1-4])\s+FY(\d{2})$")

_DEFAULT_MIN_FY = 2020
_DEFAULT_MAX_FY = 2030


def get_fiscal_year_range(config_path: Path | None = None) -> tuple[int, int]:
    """Retrieve configured (fiscal_year_min, fiscal_year_max) from parameters config."""
    try:
        from backend.app.config.loader import load_config_file
        from backend.app.config.models import ParametersConfig

        path = (
            config_path
            or Path(__file__).resolve().parent.parent.parent / "config" / "parameters.yaml"
        )
        if path.is_file():
            cfg = load_config_file(path, ParametersConfig)
            min_fy = int(cfg.parameters["fiscal_year_min"].default)
            max_fy = int(cfg.parameters["fiscal_year_max"].default)
            return min_fy, max_fy
    except Exception:
        pass
    return _DEFAULT_MIN_FY, _DEFAULT_MAX_FY


def parse_fiscal_label(
    label: str,
    min_year: int | None = None,
    max_year: int | None = None,
) -> tuple[int, int]:
    """Parse an Indian fiscal quarter label into (quarter, 4-digit fiscal_year).

    Accepts the exact canonical format appearing in PROJECT.md: 'Q{1-4} FY{YY}' (e.g. 'Q1 FY27').
    Rejects labels outside the configured fiscal year range with an explicit ValueError.
    """
    if not isinstance(label, str):
        raise ValueError(f"Fiscal period label must be a string, found: {type(label)}")

    match = FISCAL_LABEL_REGEX.match(label.strip())
    if not match:
        raise ValueError(
            f"Invalid fiscal period label: '{label}'. "
            "Expected canonical format 'Q{1-4} FY{YY}' (e.g. 'Q1 FY27')."
        )

    quarter = int(match.group(1))
    short_year = int(match.group(2))
    fiscal_year = 2000 + short_year

    if min_year is None or max_year is None:
        cfg_min, cfg_max = get_fiscal_year_range()
        min_year = cfg_min if min_year is None else min_year
        max_year = cfg_max if max_year is None else max_year

    if fiscal_year < min_year or fiscal_year > max_year:
        raise ValueError(
            f"Fiscal year {fiscal_year} from label '{label}' is outside configured range [{min_year}, {max_year}]."
        )

    return quarter, fiscal_year


def format_fiscal_label(
    quarter: int,
    fiscal_year: int,
    min_year: int | None = None,
    max_year: int | None = None,
) -> str:
    """Format quarter and fiscal year into canonical 'Q{q} FY{yy}' label."""
    if not isinstance(quarter, int) or not (1 <= quarter <= 4):
        raise ValueError(f"Quarter must be an integer between 1 and 4, found: {quarter}")

    if not isinstance(fiscal_year, int) or fiscal_year <= 0:
        raise ValueError(f"Fiscal year must be a positive integer, found: {fiscal_year}")

    if min_year is None or max_year is None:
        cfg_min, cfg_max = get_fiscal_year_range()
        min_year = cfg_min if min_year is None else min_year
        max_year = cfg_max if max_year is None else max_year

    if fiscal_year < min_year or fiscal_year > max_year:
        raise ValueError(
            f"Fiscal year {fiscal_year} is outside configured range [{min_year}, {max_year}]."
        )

    short_year = fiscal_year % 100
    return f"Q{quarter} FY{short_year:02d}"


def fiscal_period_to_dates(label: str) -> tuple[date, date]:
    """Map a fiscal period label like 'Q1 FY27' to (start_date, end_date).

    Indian fiscal year FY27 runs from April 1, 2026 to March 31, 2027.
    - Q1: April 1 to June 30
    - Q2: July 1 to September 30
    - Q3: October 1 to December 31
    - Q4: January 1 to March 31
    """
    quarter, fiscal_year = parse_fiscal_label(label)
    cal_year = fiscal_year - 1

    if quarter == 1:
        return date(cal_year, 4, 1), date(cal_year, 6, 30)
    if quarter == 2:
        return date(cal_year, 7, 1), date(cal_year, 9, 30)
    if quarter == 3:
        return date(cal_year, 10, 1), date(cal_year, 12, 31)
    if quarter == 4:
        return date(fiscal_year, 1, 1), date(fiscal_year, 3, 31)

    raise ValueError(f"Invalid quarter: {quarter}")


def date_to_fiscal_period(d: date | datetime) -> str:
    """Map a calendar date to its Indian fiscal quarter label (e.g. 'Q1 FY27')."""
    if isinstance(d, datetime):
        d = d.date()
    elif not isinstance(d, date):
        raise ValueError(f"Expected date or datetime object, found: {type(d)}")

    month = d.month
    year = d.year

    if 4 <= month <= 6:
        quarter = 1
        fiscal_year = year + 1
    elif 7 <= month <= 9:
        quarter = 2
        fiscal_year = year + 1
    elif 10 <= month <= 12:
        quarter = 3
        fiscal_year = year + 1
    elif 1 <= month <= 3:
        quarter = 4
        fiscal_year = year
    else:
        raise ValueError(f"Invalid month: {month}")

    return format_fiscal_label(quarter, fiscal_year)
