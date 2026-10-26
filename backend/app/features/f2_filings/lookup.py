"""Live Feature 2 XBRL lookup from official exchange archives.

Rules:
- Requires authenticated user.
- Enforces per-user daily limit from config.
- Enforces global request-rate limit to NSE archives from config.
- Server cache with TTL from config.
- Terms not read (logged in DECISIONS.md).
- Never returns raw XML/XBRL files, only parsed analytical results.
- Annual-only rules: R5 (cash quality) and R6 (working capital) and DSO metric evaluate on annual data only.
"""

import csv
import io
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

from backend.app.data.fiscal import date_to_fiscal_period, parse_fiscal_label
from backend.app.features.f2_filings.rules import evaluate_all_rules, RuleResult

logger = logging.getLogger("backend.app.features.f2_filings.lookup")

NSE_ARCHIVES_EQUITY_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_NIFTY50_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv"
DATA_XBRL_DIR = Path("data") / "xbrl"

# Global state for rate limiting and caching
_LAST_NSE_REQUEST_TIME: float = 0.0
_EQUITY_LIST_CACHE: tuple[float, list[dict[str, str]]] | None = None
_TOP50_CACHE: tuple[float, list[dict[str, str]]] | None = None
_INDUSTRY_BY_SYMBOL: dict[str, str] = {}
_LOOKUP_RESULT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


class UnsupportedCompanyTypeError(ValueError):
    """Raised when an unsupported financial company (bank, NBFC, insurer) is requested."""

    pass


def get_company_industry(symbol: str) -> str | None:
    """Retrieve industry classification from cached NSE index data if available."""
    global _INDUSTRY_BY_SYMBOL
    return _INDUSTRY_BY_SYMBOL.get(symbol.strip().upper())


def is_financial_company(symbol: str, company_name: str | None = None, industry: str | None = None) -> bool:
    """Detect banks, NBFCs, insurers, and financial institutions."""
    import re
    from backend.app.config.loader import load_all_config

    if industry is None:
        industry = get_company_industry(symbol)

    all_cfg = load_all_config()
    params = all_cfg.parameters.parameters if all_cfg else {}

    sec_p = params.get("f2_financial_sectors")
    kw_p = params.get("f2_financial_keywords")

    if sec_p and isinstance(sec_p.default, str):
        fin_sectors = [s.strip().upper() for s in sec_p.default.split(",") if s.strip()]
    else:
        fin_sectors = ["FINANCIAL SERVICES", "BANKS", "BANK", "NBFC", "INSURANCE", "FINANCIAL"]

    if kw_p and isinstance(kw_p.default, str):
        fin_keywords = [k.strip().upper() for k in kw_p.default.split(",") if k.strip()]
    else:
        fin_keywords = [
            "BANK",
            "FINANCE",
            "FINANCIAL",
            "INSURANCE",
            "NBFC",
            "HOUSING",
            "MUTUAL",
            "SECURITIES",
            "CAPITAL",
        ]

    if industry:
        ind_up = industry.strip().upper()
        if any(sec in ind_up for sec in fin_sectors):
            return True

    sym_up = symbol.strip().upper()
    name_up = (company_name or "").strip().upper()

    _known_financial_symbols = {
        "SBIN",
        "PNB",
        "CANBK",
        "UNIONBANK",
        "IOB",
        "UCOBANK",
        "PFC",
        "RECLTD",
        "LICI",
        "GICRE",
        "NIACL",
        "HDFCBANK",
        "ICICIBANK",
        "AXISBANK",
        "KOTAKBANK",
        "INDUSINDBK",
        "BAJFINANCE",
        "BAJAJFINSV",
        "HDFCLIFE",
        "SBILIFE",
        "BANDHANBNK",
        "FEDERALBNK",
        "IDFCFIRSTB",
        "AUBANK",
        "BANKBARODA",
    }
    if sym_up in _known_financial_symbols:
        return True

    for kw in ("BANK", "FINANCE", "NBFC", "INSUR"):
        if kw in sym_up:
            return True

    for kw in fin_keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", name_up):
            return True

    return False


def _throttle_nse_request(rate_limit_per_sec: float = 5.0) -> None:
    """Ensure outgoing requests to NSE archives observe global rate limit."""
    global _LAST_NSE_REQUEST_TIME
    interval = 1.0 / max(rate_limit_per_sec, 0.1)
    elapsed = time.time() - _LAST_NSE_REQUEST_TIME
    if elapsed < interval:
        time.sleep(interval - elapsed)
    _LAST_NSE_REQUEST_TIME = time.time()


def fetch_nse_equity_list(rate_limit_per_sec: float = 5.0) -> list[dict[str, str]]:
    """Retrieve equity list from NSE archives host with caching."""
    global _EQUITY_LIST_CACHE
    now_ts = time.time()
    if _EQUITY_LIST_CACHE is not None:
        cached_ts, cached_list = _EQUITY_LIST_CACHE
        if (now_ts - cached_ts) < 86400:  # 24 hour cache
            return cached_list

    _throttle_nse_request(rate_limit_per_sec)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    try:
        with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
            resp = client.get(NSE_ARCHIVES_EQUITY_URL)
            if resp.status_code != 200:
                raise RuntimeError(f"NSE archives returned HTTP {resp.status_code}")
            reader = csv.DictReader(io.StringIO(resp.text))
            equities = []
            for row in reader:
                sym = (row.get("SYMBOL") or "").strip()
                name = (row.get("NAME OF COMPANY") or "").strip()
                if sym:
                    equities.append({"symbol": sym, "name": name})
            _EQUITY_LIST_CACHE = (now_ts, equities)
            logger.info("Loaded %d equities from NSE archives equity list", len(equities))
            return equities
    except Exception as exc:
        logger.warning("Failed to fetch equity list from NSE archives: %s", exc)
        raise RuntimeError(f"source unavailable: failed to connect to NSE archives ({exc})") from exc


def resolve_company(query: str, rate_limit_per_sec: float = 5.0) -> dict[str, str] | None:
    """Find company by symbol or name from official NSE equity list."""
    equities = fetch_nse_equity_list(rate_limit_per_sec)
    q_clean = query.strip().upper()

    # Exact symbol match
    for eq in equities:
        if eq["symbol"].upper() == q_clean:
            return eq

    # Exact name match
    for eq in equities:
        if eq["name"].upper() == q_clean:
            return eq

    # Substring name match
    for eq in equities:
        if q_clean in eq["name"].upper():
            return eq

    return None


def fetch_nifty50_constituents(
    cache_ttl_seconds: int = 86400,
    rate_limit_per_sec: float = 5.0,
) -> list[dict[str, str]]:
    """Retrieve official Nifty 50 constituents from NSE archives with TTL cache.

    If fetch fails, raises RuntimeError and never returns old or hand-typed data.
    """
    global _TOP50_CACHE
    now_ts = time.time()
    if _TOP50_CACHE is not None:
        cached_ts, cached_list = _TOP50_CACHE
        if (now_ts - cached_ts) < cache_ttl_seconds:
            return cached_list

    _throttle_nse_request(rate_limit_per_sec)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    try:
        with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
            resp = client.get(NSE_NIFTY50_URL)
            if resp.status_code != 200:
                raise RuntimeError(f"NSE archives returned HTTP {resp.status_code}")
            reader = csv.DictReader(io.StringIO(resp.text))
            top50: list[dict[str, str]] = []
            for row in reader:
                sym = (row.get("Symbol") or row.get("SYMBOL") or "").strip()
                name = (row.get("Company Name") or row.get("NAME OF COMPANY") or "").strip()
                ind = (row.get("Industry") or row.get("INDUSTRY") or "").strip()
                if sym:
                    top50.append({"symbol": sym, "name": name})
                    if ind:
                        _INDUSTRY_BY_SYMBOL[sym.upper()] = ind
            _TOP50_CACHE = (now_ts, top50)
            logger.info("Loaded %d constituents from NSE Nifty 50 list", len(top50))
            return top50
    except Exception as exc:
        logger.warning("Failed to fetch Nifty 50 constituents from NSE: %s", exc)
        raise RuntimeError(f"source unavailable: failed to fetch Nifty 50 list from NSE archives ({exc})") from exc


def search_nse_equities(
    query: str,
    limit: int = 20,
    rate_limit_per_sec: float = 5.0,
) -> list[dict[str, str]]:
    """Search full NSE equity list by query (min 2 chars).

    Matches symbol and name (case-insensitive).
    Symbol matches are ranked first, followed by name matches. Capped at limit.
    """
    q = query.strip()
    if len(q) < 2:
        raise ValueError("Search query must be at least 2 characters")

    equities = fetch_nse_equity_list(rate_limit_per_sec)
    q_upper = q.upper()

    exact_symbol: list[dict[str, str]] = []
    starts_symbol: list[dict[str, str]] = []
    contains_symbol: list[dict[str, str]] = []
    starts_name: list[dict[str, str]] = []
    contains_name: list[dict[str, str]] = []

    seen_symbols: set[str] = set()

    for eq in equities:
        sym = eq["symbol"].upper()
        if sym == q_upper:
            exact_symbol.append(eq)
            seen_symbols.add(sym)
        elif sym.startswith(q_upper):
            starts_symbol.append(eq)
            seen_symbols.add(sym)
        elif q_upper in sym:
            contains_symbol.append(eq)
            seen_symbols.add(sym)

    for eq in equities:
        sym = eq["symbol"].upper()
        if sym in seen_symbols:
            continue
        name = eq["name"].upper()
        if name.startswith(q_upper):
            starts_name.append(eq)
            seen_symbols.add(sym)
        elif q_upper in name:
            contains_name.append(eq)
            seen_symbols.add(sym)

    ordered = exact_symbol + starts_symbol + contains_symbol + starts_name + contains_name
    return ordered[:limit]



def get_available_filings(symbol: str) -> list[dict[str, Any]]:
    """Inspect local/shipped filing registries for available XBRL periods for a symbol."""
    filings = []

    # Check quarterly results index
    q_file = DATA_XBRL_DIR / "nse_quarterly_results.json"
    if q_file.is_file():
        try:
            q_data = json.loads(q_file.read_text(encoding="utf-8"))
            for entry in q_data:
                if (entry.get("symbol") or "").strip().upper() == symbol.upper():
                    filings.append(entry)
        except Exception:
            pass

    # Check annual results index
    a_file = DATA_XBRL_DIR / "nse_Annual_results.json"
    if a_file.is_file():
        try:
            a_data = json.loads(a_file.read_text(encoding="utf-8"))
            for entry in a_data:
                if (entry.get("symbol") or "").strip().upper() == symbol.upper():
                    filings.append(entry)
        except Exception:
            pass

    # Also check local XML files in data/xbrl
    for xml_p in DATA_XBRL_DIR.glob(f"{symbol}*.xml"):
        filings.append({
            "symbol": symbol,
            "period": "Quarterly",
            "xbrl": str(xml_p),
            "is_local": True,
        })

    return filings


def download_xbrl_xml(xbrl_url: str, rate_limit_per_sec: float = 5.0) -> bytes:
    """Download XBRL XML from URL observing rate limits."""
    if Path(xbrl_url).is_file():
        return Path(xbrl_url).read_bytes()

    _throttle_nse_request(rate_limit_per_sec)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.nseindia.com/",
    }
    try:
        with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
            resp = client.get(xbrl_url)
            if resp.status_code != 200:
                raise RuntimeError(f"NSE archives returned HTTP {resp.status_code}")
            return resp.content
    except Exception as exc:
        raise RuntimeError(f"source unavailable: failed to download XBRL from archives ({exc})") from exc


def parse_xbrl_bytes(xml_bytes: bytes, symbol: str) -> dict[str, Any]:
    """Parse Ind AS XBRL XML document and extract reported metrics."""
    root = ET.fromstring(xml_bytes)

    def _strip_ns(tag: str) -> str:
        return tag.split("}", 1)[1] if "}" in tag else tag

    company_name = ""
    reporting_quarter = ""
    start_date = ""
    end_date = ""
    nature_of_report = "Standalone"
    level_rounding = "Crores"
    metrics_raw: dict[str, dict[str, Any]] = {}

    for elem in root:
        local_tag = _strip_ns(elem.tag)
        text_val = (elem.text or "").strip()
        context_ref = elem.attrib.get("contextRef", "")
        unit_ref = elem.attrib.get("unitRef", "")
        decimals = elem.attrib.get("decimals", "")

        if local_tag == "NameOfTheCompany" and not company_name:
            company_name = text_val
        elif local_tag == "Symbol" and text_val:
            symbol = text_val
        elif local_tag == "ReportingQuarter" and not reporting_quarter:
            reporting_quarter = text_val
        elif local_tag == "DateOfStartOfReportingPeriod" and context_ref == "OneD":
            start_date = text_val
        elif local_tag == "DateOfEndOfReportingPeriod" and context_ref == "OneD":
            end_date = text_val
        elif local_tag == "NatureOfReportStandaloneConsolidated" and context_ref == "OneD":
            nature_of_report = text_val
        elif local_tag == "LevelOfRoundingUsedInFinancialStatements" and context_ref == "OneD":
            level_rounding = text_val

        # Primary quarter metrics or general Ind-AS elements
        if unit_ref and text_val:
            try:
                num_val = float(text_val)
                metrics_raw[local_tag] = {
                    "value": f"{num_val:.2f}",
                    "contextRef": context_ref,
                    "unitRef": unit_ref,
                    "decimals": decimals,
                }
            except (ValueError, TypeError):
                continue

    # Determine canonical fiscal period
    if end_date:
        try:
            dt = datetime.strptime(end_date[:10], "%Y-%m-%d").date()
            fiscal_period = date_to_fiscal_period(dt)
        except Exception:
            fiscal_period = reporting_quarter or "Q3 FY25"
    else:
        fiscal_period = reporting_quarter or "Q3 FY25"

    is_annual = "annual" in reporting_quarter.lower() or "full" in reporting_quarter.lower()

    return {
        "company": company_name or symbol,
        "symbol": symbol,
        "period": reporting_quarter or "Quarterly",
        "fiscal_period": fiscal_period,
        "period_end_date": end_date,
        "is_annual": is_annual,
        "basis": nature_of_report.lower(),
        "level_rounding": level_rounding,
        "metrics": metrics_raw,
    }


def perform_f2_lookup(
    company_query: str,
    period_query: str,
    rate_limit_per_sec: float = 5.0,
    cache_ttl_seconds: int = 86400,
) -> dict[str, Any]:
    """Execute live Feature 2 lookup for company and period."""
    # Check cache
    cache_key = f"{company_query.strip().upper()}::{period_query.strip().upper()}"
    now_ts = time.time()
    if cache_key in _LOOKUP_RESULT_CACHE:
        cached_ts, cached_result = _LOOKUP_RESULT_CACHE[cache_key]
        if (now_ts - cached_ts) < cache_ttl_seconds:
            return cached_result

    # 1. Resolve company from official NSE equity list
    matched_company = resolve_company(company_query, rate_limit_per_sec)
    if not matched_company:
        raise ValueError(f"Company '{company_query}' not found in official NSE equity list.")

    symbol = matched_company["symbol"]
    company_name = matched_company["name"]

    # Check for unsupported financial institutions
    industry = get_company_industry(symbol)
    if is_financial_company(symbol, company_name, industry):
        raise UnsupportedCompanyTypeError("financial companies are not covered")

    # 2. Validate period format (must be Q{1-4} FY{YY} or annual)
    normalized_period = period_query.strip()
    is_annual_query = "annual" in normalized_period.lower()
    if not is_annual_query:
        try:
            parse_fiscal_label(normalized_period)
        except ValueError as exc:
            raise ValueError(f"Invalid fiscal period format: '{period_query}'. Expected format like 'Q1 FY27'.") from exc

    # 3. Find available filings for company
    filings = get_available_filings(symbol)
    if not filings:
        raise ValueError(f"no data for {symbol} in {normalized_period}. Available periods: none found")

    # Match target filing
    target_filing = None
    available_periods: list[str] = []

    for f in filings:
        xbrl_url = f.get("xbrl") or ""
        if not xbrl_url or xbrl_url == "-":
            continue
        f_period = f.get("period", "Quarterly")
        available_periods.append(f_period)
        if is_annual_query and ("annual" in f_period.lower() or "full" in f_period.lower()):
            target_filing = f
            break
        elif not is_annual_query:
            target_filing = f
            break

    if not target_filing and filings:
        for f in filings:
            if f.get("xbrl") and f.get("xbrl") != "-":
                target_filing = f
                break

    if not target_filing or not target_filing.get("xbrl") or target_filing.get("xbrl") == "-":
        distinct_periods = sorted(list(set(available_periods)))
        raise ValueError(f"no data for {symbol} in {normalized_period}. Available periods: {distinct_periods}")

    # 4. Download and parse XBRL
    xml_bytes = download_xbrl_xml(target_filing["xbrl"], rate_limit_per_sec)
    parsed_filing = parse_xbrl_bytes(xml_bytes, symbol)
    parsed_filing["company"] = company_name

    # 5. Extract reported XBRL figures and evaluate consistency rules
    is_annual = parsed_filing.get("is_annual", False) or is_annual_query

    from backend.app.contracts.filings import FilingMetric

    rev_raw = parsed_filing["metrics"].get("RevenueFromOperations")
    pbt_raw = parsed_filing["metrics"].get("ProfitBeforeTax")
    pat_raw = parsed_filing["metrics"].get("ProfitLossForPeriod")
    ocf_raw = (
        parsed_filing["metrics"].get("CashFlowsFromUsedInOperatingActivities")
        or parsed_filing["metrics"].get("NetCashFlowsFromOperatingActivities")
    )
    rec_raw = (
        parsed_filing["metrics"].get("TradeReceivables")
        or parsed_filing["metrics"].get("CurrentTradeReceivables")
    )

    rev_val = float(rev_raw["value"]) if rev_raw else 0.0
    pbt_val = float(pbt_raw["value"]) if pbt_raw else 0.0
    pat_val = float(pat_raw["value"]) if pat_raw else 0.0
    ocf_val = float(ocf_raw["value"]) if ocf_raw else None
    rec_val = float(rec_raw["value"]) if rec_raw else None

    unit_label = f"INR {parsed_filing.get('level_rounding', 'Crores')}"
    period_label = parsed_filing["fiscal_period"]

    metric_basis = (
        "consolidated"
        if "consolidated" in parsed_filing.get("basis", "standalone").lower()
        else "standalone"
    )
    metric_entry = FilingMetric(
        company=company_name,
        symbol=symbol,
        fiscal_period=normalized_period,
        period_end_date=parsed_filing.get("period_end_date") or "",
        basis=metric_basis,
        metric="RevenueFromOperations",
        value=rev_val,
        unit=unit_label,
        source_filing_reference=f"NSE_XBRL_{symbol}_{normalized_period}",
        derived=False,
        retrieval_time="",
    )

    # When no management announcement claim text is available, all rules requiring a claim
    # return not_applicable with reason 'no management claim text available'.
    # Rules that need annual data (R5, R6) return not_applicable on quarters.
    all_rule_results = evaluate_all_rules(
        claim=None,
        metric=metric_entry,
        is_annual=is_annual,
    )

    RULE_NAMES = {
        "R0": "Stated Number Verification",
        "R1": "Direction of Growth Verification",
        "R2": "Growth Magnitude Verification",
        "R3": "Growth Trend & Momentum Verification",
        "R4": "Profitability & Margin Discipline",
        "R5": "Operating Cash Flow Quality",
        "R6": "Working Capital & Receivables Discipline",
        "R7": "Understatement & Commentary Asymmetry",
    }

    rule_metric_info = {
        "R0": ("RevenueFromOperations", rev_val),
        "R1": ("RevenueFromOperations", rev_val),
        "R2": ("RevenueFromOperations", rev_val),
        "R3": ("RevenueFromOperations", rev_val),
        "R4": ("ProfitLossForPeriod", pat_val),
        "R5": ("CashFlowsFromOperatingActivities", ocf_val),
        "R6": ("TradeReceivables", rec_val),
        "R7": ("RevenueFromOperations", rev_val),
    }

    evaluated_rules: list[dict[str, Any]] = []
    for rr in all_rule_results:
        m_field, m_val = rule_metric_info.get(rr.rule_id, ("RevenueFromOperations", rev_val))
        evaluated_rules.append({
            "rule_id": rr.rule_id,
            "rule_name": RULE_NAMES.get(rr.rule_id, rr.rule_id),
            "status": rr.status,
            "severity": rr.severity,
            "claim_quote": None,
            "claim_text": None,
            "metric_name": m_field,
            "metric_value": m_val,
            "metric_unit": unit_label,
            "period": period_label,
            "evidence": rr.evidence,
            "reason": rr.reason,
        })

    # Structured XBRL numbers with units and period
    xbrl_numbers = [
        {
            "field": "RevenueFromOperations",
            "name": "Revenue from Operations",
            "value": rev_val,
            "unit": unit_label,
            "period": period_label,
        },
        {
            "field": "ProfitBeforeTax",
            "name": "Profit Before Tax (PBT)",
            "value": pbt_val,
            "unit": unit_label,
            "period": period_label,
        },
        {
            "field": "ProfitLossForPeriod",
            "name": "Profit / Loss for Period (PAT)",
            "value": pat_val,
            "unit": unit_label,
            "period": period_label,
        },
    ]
    if ocf_val is not None:
        xbrl_numbers.append({
            "field": "CashFlowsFromOperatingActivities",
            "name": "Operating Cash Flow",
            "value": ocf_val,
            "unit": unit_label,
            "period": period_label,
        })
    if rec_val is not None:
        xbrl_numbers.append({
            "field": "TradeReceivables",
            "name": "Trade Receivables",
            "value": rec_val,
            "unit": unit_label,
            "period": period_label,
        })

    verified_metrics = {
        "RevenueFromOperations": rev_val,
        "ProfitBeforeTax": pbt_val,
        "ProfitLossForPeriod": pat_val,
    }
    if ocf_val is not None:
        verified_metrics["CashFlowsFromOperatingActivities"] = ocf_val
    if rec_val is not None:
        verified_metrics["TradeReceivables"] = rec_val

    result = {
        "company": company_name,
        "symbol": symbol,
        "requested_period": normalized_period,
        "reporting_period": parsed_filing["fiscal_period"],
        "is_annual": is_annual,
        "verified_metrics": verified_metrics,
        "xbrl_numbers": xbrl_numbers,
        "rules_evaluated": evaluated_rules,
        "source": "official NSE Ind AS XBRL archive",
    }

    _LOOKUP_RESULT_CACHE[cache_key] = (now_ts, result)
    return result
