"""Tool registry wrapping live analytical functions with in-tool entitlement evaluation."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.auth.models import UserClaims
from backend.app.config.env import Settings, load_settings
from backend.app.config.loader import load_all_config
from backend.app.config.models import AllConfig
from backend.app.entitlements.atomic import get_today_usage
from backend.app.entitlements.decision import decide
from backend.app.features.f2_filings.lookup import UnsupportedCompanyTypeError

logger = logging.getLogger("backend.app.agent.tools")


def normalize_fiscal_period(period_str: str | None) -> str:
    """Normalize fiscal period variations like Q3FY25 or q3 fy25 to standard Q3 FY25."""
    if not period_str:
        return "Q3 FY25"
    s = str(period_str).strip()
    m = re.match(r"^(Q[1-4])\s*[-_]?\s*(FY\s*\d{2,4})$", s, re.IGNORECASE)
    if m:
        q_part = m.group(1).upper()
        fy_raw = m.group(2).upper()
        fy_clean = re.sub(r"\s+", "", fy_raw)
        return f"{q_part} {fy_clean}"
    return s

def resolve_iso_date(date_input: str | None, now: datetime | None = None) -> str | None:
    """Resolve user or partial dates to standard ISO date without hardcoded dates."""
    if not date_input:
        return None
    s = str(date_input).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s

    clock_dt = now or datetime.now(timezone.utc)
    curr_year = clock_dt.year

    cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s, flags=re.IGNORECASE)
    for fmt in ("%d %B", "%B %d", "%d %b", "%b %d"):
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.replace(year=curr_year).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def _evaluate_tool_entitlement(
    user: UserClaims,
    feature_key: str,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    usage = 0
    if conn is not None:
        db_map = {
            "feature1_contagion": "contagion",
            "feature2_filings": "filing_consistency",
            "feature3_forensic": "investment_log",
        }
        db_feat = db_map.get(feature_key, feature_key)
        try:
            usage = get_today_usage(conn, user.user_id, db_feat)
        except Exception:
            usage = 0

    eval_now = now or datetime.now(timezone.utc)
    decision = decide(
        plan=user.plan,
        feature=feature_key,
        usage=usage,
        now=eval_now,
        plans_config=all_config.plans,
    )

    if not decision.allowed:
        return False, {
            "status": "denied",
            "decision": decision.decision,
            "reason": decision.reason or f"Access to {feature_key} is not permitted on plan '{user.plan}'",
            "status_code": decision.status,
            "upgrade_targets": decision.upgrade_targets or [],
        }

    return True, None


def tool_market_scan(
    user: UserClaims,
    settings: Settings,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
    as_of: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute live systemic market contagion scan across benchmark Indian equities."""
    fetched_at = (now or datetime.now(timezone.utc)).isoformat()
    as_of_resolved = resolve_iso_date(as_of, now=now)

    allowed, denial = _evaluate_tool_entitlement(user, "feature1_contagion", all_config, conn, now)
    if not allowed:
        denial_dict = dict(denial or {"status": "denied", "reason": "Entitlement denied", "status_code": 403})
        denial_dict["as_of"] = as_of_resolved or (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
        denial_dict["fetched_at"] = fetched_at
        return denial_dict

    try:
        from backend.app.features.f1_contagion.pipeline import run_correlation_scan

        overrides = {"as_of": as_of_resolved} if as_of_resolved else None
        scan = run_correlation_scan(overrides=overrides, live=True)

        summary = {
            "scope": "market-wide",
            "as_of": as_of_resolved or str(scan.as_of),
            "fetched_at": fetched_at,
            "regime_tier": scan.regime_flag,
            "absorption_ratio": round(float(scan.absorption_ratio), 4),
            "ar_delta_std": round(float(scan.ar_delta_std), 4),
            "mean_correlation": round(float(scan.mean_correlation), 4),
            "significant_pairs_count": int(scan.significant_pairs_count),
            "top_shifted_pairs": [
                {
                    "pair": p.pair,
                    "baseline_corr": round(float(p.baseline_corr), 4),
                    "current_corr": round(float(p.current_corr), 4),
                    "fr_adjusted_corr": round(float(p.fr_adjusted_corr), 4),
                }
                for p in scan.top_shifted_pairs[:5]
            ],
        }
        return {"status": "success", "data": summary}
    except Exception as exc:
        logger.error("Failed to execute live market_scan: %s", exc)
        return {
            "status": "error",
            "reason": f"Market scan error: {exc}",
            "as_of": as_of_resolved or (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d"),
            "fetched_at": fetched_at,
        }


def tool_filings_check(
    user: UserClaims,
    settings: Settings,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
    company: str | None = None,
    period: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Inspect quarterly or annual financial filings for any listed Indian company."""
    fetched_at = (now or datetime.now(timezone.utc)).isoformat()
    allowed, denial = _evaluate_tool_entitlement(user, "feature2_filings", all_config, conn, now)
    if not allowed:
        denial_dict = dict(denial or {"status": "denied", "reason": "Entitlement denied", "status_code": 403})
        denial_dict["as_of"] = period or "Q3 FY25"
        denial_dict["fetched_at"] = fetched_at
        return denial_dict

    company_query = (company or kwargs.get("symbol") or "INFY").strip()
    period_query = normalize_fiscal_period(period or "Q3 FY25")

    try:
        from backend.app.features.f2_filings.lookup import perform_f2_lookup

        res = perform_f2_lookup(company_query, period_query)
        rules = res.get("rules_evaluated") or res.get("rules", [])
        as_of_val = res.get("reporting_period") or res.get("requested_period", period_query)

        derived_metrics = res.get("verified_metrics") or res.get("metrics", {})
        clean_derived_numbers = {
            k: round(float(v), 4) if isinstance(v, (int, float)) else v
            for k, v in derived_metrics.items()
        }

        inconsistencies = [
            {
                "rule_id": r.get("rule_id"),
                "rule_name": r.get("rule_name"),
                "status": r.get("status"),
                "severity": r.get("severity"),
                "metric_name": r.get("metric_name"),
                "metric_value": r.get("metric_value"),
                "reason": r.get("reason") or r.get("rationale") or r.get("evidence_summary"),
                "claim_quote": r.get("claim_quote") or r.get("claim_text"),
            }
            for r in rules
            if r.get("status") in ("flag", "fail")
        ]

        return {
            "status": "success",
            "data": {
                "company": res.get("company", company_query),
                "symbol": res.get("symbol", company_query),
                "period": as_of_val,
                "as_of": as_of_val,
                "fetched_at": fetched_at,
                "verified_metrics": clean_derived_numbers,
                "rules_evaluated": len(rules),
                "inconsistencies": inconsistencies,
            },
        }
    except UnsupportedCompanyTypeError as exc:
        return {
            "status": "unsupported",
            "reason": str(exc),
            "company": company_query,
            "period": period_query,
            "as_of": period_query,
            "fetched_at": fetched_at,
        }
    except (ValueError, RuntimeError) as exc:
        err_msg = str(exc)
        if "404" in err_msg or "source unavailable" in err_msg or "no data for" in err_msg:
            return {
                "status": "not_found",
                "reason": f"No XBRL filing document is available for {company_query} for period {period_query} in the NSE exchange archives.",
                "company": company_query,
                "period": period_query,
                "as_of": period_query,
                "fetched_at": fetched_at,
            }
        return {
            "status": "not_found" if isinstance(exc, ValueError) else "error",
            "reason": str(exc) if isinstance(exc, ValueError) else f"Filings check error: {exc}",
            "company": company_query,
            "period": period_query,
            "as_of": period_query,
            "fetched_at": fetched_at,
        }
    except Exception as exc:
        logger.error("Failed to execute filings_check for %s: %s", company_query, exc)
        return {
            "status": "error",
            "reason": f"Filings check error: {exc}",
            "company": company_query,
            "period": period_query,
            "as_of": period_query,
            "fetched_at": fetched_at,
        }


def tool_market_news(
    user: UserClaims,
    settings: Settings,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
    query: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Search Indian equity macro and market news context carrying evidence identifiers."""
    fetched_at = (now or datetime.now(timezone.utc)).isoformat()
    as_of_val = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")

    allowed, denial = _evaluate_tool_entitlement(user, "feature1_contagion", all_config, conn, now)
    if not allowed and user.plan not in all_config.plans.plans:
        denial_dict = dict(denial or {"status": "denied", "reason": "Entitlement denied", "status_code": 403})
        denial_dict["as_of"] = as_of_val
        denial_dict["fetched_at"] = fetched_at
        return denial_dict

    search_query = (query or "Indian equity market systemic risk correlation contagion").strip()
    try:
        from backend.app.features.f1_contagion.explanation import fetch_tavily_news

        raw_news = fetch_tavily_news(search_query, settings=settings, max_results=3)
        if not raw_news:
            return {
                "status": "empty",
                "data": {
                    "query": search_query,
                    "as_of": as_of_val,
                    "fetched_at": fetched_at,
                    "items": [],
                },
            }

        items = [
            {
                "evidence_id": f"E{idx}",
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")[:250],
            }
            for idx, r in enumerate(raw_news, start=1)
        ]
        return {
            "status": "success",
            "data": {
                "query": search_query,
                "as_of": as_of_val,
                "fetched_at": fetched_at,
                "items": items,
            },
        }
    except ValueError as exc:
        if "not run: no key" in str(exc):
            return {
                "status": "not_run",
                "reason": "not run: no search key",
                "as_of": as_of_val,
                "fetched_at": fetched_at,
            }
        return {
            "status": "error",
            "reason": str(exc),
            "as_of": as_of_val,
            "fetched_at": fetched_at,
        }
    except Exception as exc:
        logger.error("Failed to execute market_news: %s", exc)
        return {
            "status": "error",
            "reason": f"Market news search error: {exc}",
            "as_of": as_of_val,
            "fetched_at": fetched_at,
        }


TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "market_scan": {
        "name": "market_scan",
        "description": "Execute live systemic market contagion scan across benchmark Indian equities. Note: this scan is market-wide, not per company.",
        "parameters": {
            "type": "object",
            "properties": {
                "as_of": {
                    "type": "string",
                    "description": "Optional ISO date (YYYY-MM-DD) or date string to run historical scan as of.",
                }
            },
        },
        "func": tool_market_scan,
    },
    "filings_check": {
        "name": "filings_check",
        "description": "Inspect quarterly or annual financial filings for any listed Indian company and reported XBRL inconsistencies.",
        "parameters": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Company name or NSE equity symbol (e.g., INFY, MARUTI, RELIANCE).",
                },
                "period": {
                    "type": "string",
                    "description": "Reporting period, e.g., 'Q3 FY25', 'Q1 FY27', or 'annual'.",
                },
            },
            "required": ["company", "period"],
        },
        "func": tool_filings_check,
    },
    "market_news": {
        "name": "market_news",
        "description": "Search Indian equity and macro market news context carrying evidence identifiers.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for Indian market news context.",
                },
            },
            "required": ["query"],
        },
        "func": tool_market_news,
    },
}

# Legacy aliases for compatibility with earlier test suites
tool_f1_contagion = tool_market_scan
tool_f2_filings = tool_filings_check
tool_f3_portfolio = tool_filings_check


def get_available_tools() -> list[dict[str, Any]]:
    """Return OpenAI-compatible function schema definitions for the standard 3 agent tools."""
    tools: list[dict[str, Any]] = []
    for tool_name, tool_info in TOOL_DEFINITIONS.items():
        tools.append({
            "name": tool_name,
            "type": "function",
            "description": tool_info["description"],
            "parameters": tool_info["parameters"],
            "function": {
                "name": tool_name,
                "description": tool_info["description"],
                "parameters": tool_info["parameters"],
            },
        })
    return tools


def execute_tool(
    tool_name: str,
    user: UserClaims,
    tool_args: dict[str, Any],
    settings: Settings,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Execute a registered tool function with arguments and entitlement checks."""
    canonical_map = {
        "f1_contagion": "market_scan",
        "f2_filings": "filings_check",
    }
    target_name = canonical_map.get(tool_name, tool_name)

    if target_name not in TOOL_DEFINITIONS:
        logger.warning("Agent requested unknown tool: %s", tool_name)
        return {
            "status": "error",
            "reason": f"Tool '{tool_name}' is not registered or supported.",
            "status_code": 404,
        }

    tool_fn = TOOL_DEFINITIONS[target_name]["func"]
    return tool_fn(
        user=user,
        settings=settings,
        all_config=all_config,
        conn=conn,
        now=now,
        **tool_args,
    )
