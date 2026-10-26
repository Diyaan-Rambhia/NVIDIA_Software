"""Tool registry wrapping Feature 1, 2, and 3 with in-tool entitlement evaluation."""

import json
import logging
from collections.abc import Callable
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


def tool_filings_check(
    user: UserClaims,
    settings: Settings,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
    company: str | None = None,
    period: str | None = None,
    symbol: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Inspect quarterly or annual financial filings for any listed Indian company."""
    allowed, denial = _evaluate_tool_entitlement(user, "feature2_filings", all_config, conn, now)
    if not allowed:
        return denial or {"status": "denied", "reason": "Entitlement denied", "status_code": 403}

    company_query = (company or symbol or "INFY").strip()
    period_query = (period or "Q3 FY25").strip()

    try:
        from backend.app.features.f2_filings.lookup import perform_f2_lookup

        res = perform_f2_lookup(company_query, period_query)
        rules = res.get("rules", [])
        return {
            "status": "success",
            "data": {
                "company": res.get("company_name", company_query),
                "symbol": res.get("symbol", company_query),
                "period": res.get("fiscal_period", period_query),
                "xbrl_numbers": res.get("metrics", {}),
                "rule_results": [
                    {
                        "rule_id": r.get("rule_id"),
                        "rule_name": r.get("rule_name"),
                        "status": r.get("status"),
                        "metric_name": r.get("metric_name"),
                        "metric_value": r.get("metric_value"),
                        "reason": r.get("rationale") or r.get("evidence_summary"),
                    }
                    for r in rules
                ],
                "rules_evaluated": len(rules),
                "inconsistencies": [r for r in rules if r.get("status") in ("flag", "fail")][:5],
            },
        }
    except UnsupportedCompanyTypeError as exc:
        return {
            "status": "unsupported",
            "reason": str(exc),
            "company": company_query,
            "period": period_query,
        }
    except ValueError as exc:
        return {
            "status": "not_found",
            "reason": str(exc),
            "company": company_query,
            "period": period_query,
        }
    except Exception as exc:
        logger.error("Failed to execute filings_check for %s: %s", company_query, exc)
        return {
            "status": "error",
            "reason": f"Filings check error: {exc}",
            "company": company_query,
            "period": period_query,
        }


def tool_market_scan(
    user: UserClaims,
    settings: Settings,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Analyze market contagion metrics and systemic correlation shifts (market-wide)."""
    allowed, denial = _evaluate_tool_entitlement(user, "feature1_contagion", all_config, conn, now)
    if not allowed:
        return denial or {"status": "denied", "reason": "Entitlement denied", "status_code": 403}

    try:
        from backend.app.features.f1_contagion.pipeline import run_correlation_scan

        scan = run_correlation_scan()
        summary = {
            "scope": "market-wide, not per company",
            "as_of": scan.as_of,
            "regime_tier": scan.regime_flag,
            "absorption_ratio": scan.absorption_ratio,
            "ar_delta_std": scan.ar_delta_std,
            "mean_correlation": scan.mean_correlation,
            "significant_pairs_count": scan.significant_pairs_count,
            "flagged_pairs": [
                {
                    "pair": p.pair,
                    "baseline_corr": p.baseline_corr,
                    "current_corr": p.current_corr,
                    "fr_adjusted_corr": p.fr_adjusted_corr,
                }
                for p in scan.top_shifted_pairs[:5]
            ],
            "hypotheses": [
                {"id": h.id, "text": h.text, "evidence_ids": h.evidence_ids}
                for h in (scan.hypotheses or [])
            ],
            "data_source_label": scan.source_label,
        }
        return {"status": "success", "data": summary}
    except Exception as exc:
        logger.error("Failed to execute live market_scan: %s", exc)
        return {"status": "error", "reason": f"Market scan error: {exc}"}


def tool_market_news(
    user: UserClaims,
    settings: Settings,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
    query: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Search external macro and market news context carrying evidence identifiers."""
    search_query = (query or "Indian equity market systemic risk correlation contagion").strip()
    try:
        from backend.app.features.f1_contagion.explanation import fetch_tavily_news

        raw_news = fetch_tavily_news(search_query, settings=settings, max_results=3)
        if not raw_news:
            return {"status": "empty", "data": {"query": search_query, "items": []}}

        items = [
            {
                "evidence_id": f"E{idx}",
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")[:250],
            }
            for idx, r in enumerate(raw_news, start=1)
        ]
        return {"status": "success", "data": {"query": search_query, "items": items}}
    except ValueError as exc:
        if "not run: no key" in str(exc):
            return {"status": "not_run", "reason": "not run: no search key"}
        return {"status": "error", "reason": str(exc)}
    except Exception as exc:
        logger.error("Failed to execute market_news: %s", exc)
        return {"status": "error", "reason": f"Market news search error: {exc}"}


def tool_trade_review(
    user: UserClaims,
    settings: Settings,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
    trade_log_text: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Review investment trade log for performance, risk, and behavioral metrics."""
    allowed, denial = _evaluate_tool_entitlement(user, "feature3_forensic", all_config, conn, now)
    if not allowed:
        return denial or {"status": "denied", "reason": "Entitlement denied", "status_code": 403}

    if not trade_log_text or not trade_log_text.strip():
        return {
            "status": "success",
            "data": {
                "message": "Trade review requires an attached trade log CSV in this request.",
                "metrics_available": ["FIFO lot accounting", "XIRR vs benchmark", "Disposition effect", "Turnover"],
            },
        }

    try:
        from backend.app.contracts.portfolio import ColumnMapping
        from backend.app.features.f3_log.pipeline import parse_trade_log_csv

        mapping = ColumnMapping(
            date="trade_date",
            symbol="symbol",
            side="side",
            quantity="quantity",
            price="price",
        )
        trade_log = parse_trade_log_csv(trade_log_text, mapping=mapping)
        return {
            "status": "success",
            "data": {
                "total_trades": trade_log.total_trades,
                "symbols_count": len(trade_log.symbols),
                "symbols": trade_log.symbols[:5],
                "date_range": [trade_log.start_date, trade_log.end_date],
            },
        }
    except Exception as exc:
        logger.error("Failed to parse trade review attachment: %s", exc)
        return {"status": "error", "reason": f"Trade log parse error: {exc}"}


tool_f1_contagion = tool_market_scan
tool_f2_filings = tool_filings_check
tool_f3_portfolio = tool_trade_review


TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "filings_check": {
        "name": "filings_check",
        "description": "Inspect quarterly or annual financial filings for any listed Indian company and reported XBRL inconsistencies.",
        "parameters": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Company name or NSE equity symbol (e.g., Rajesh Exports, RAJESHEXPO, INFY, RELIANCE).",
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
    "market_scan": {
        "name": "market_scan",
        "description": "Execute live systemic market contagion scan across benchmark equities. Note: this scan is market-wide, not per company.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "func": tool_market_scan,
    },
    "market_news": {
        "name": "market_news",
        "description": "Search external macro and market news context carrying evidence identifiers.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for market news context.",
                },
            },
            "required": ["query"],
        },
        "func": tool_market_news,
    },
    "trade_review": {
        "name": "trade_review",
        "description": "Review trade execution log for money-weighted return (XIRR), risk, and behavioral metrics.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "func": tool_trade_review,
    },
    # Legacy aliases
    "f1_contagion": {
        "name": "f1_contagion",
        "description": "Inspect market contagion metrics, systemic absorption ratio, and correlation shifts across benchmark equities.",
        "parameters": {},
        "func": tool_market_scan,
    },
    "f2_filings": {
        "name": "f2_filings",
        "description": "Examine quarterly financial filings for reported numeric inconsistencies and discrepancies.",
        "parameters": {
            "symbol": {
                "type": "string",
                "description": "Optional equity symbol to check (e.g., INFY, RELIANCE, TCS).",
            }
        },
        "func": tool_filings_check,
    },
    "f3_portfolio": {
        "name": "f3_portfolio",
        "description": "Review trade log execution for return metrics (XIRR, alpha), risk metrics (drawdown), and behavioral biases.",
        "parameters": {},
        "func": tool_trade_review,
    },
}


def get_available_tools(attachment_present: bool = False) -> list[dict[str, Any]]:
    """Return tool schemas for agent prompts."""
    names = ["filings_check", "market_scan", "market_news", "f1_contagion", "f2_filings", "f3_portfolio"]
    if attachment_present:
        names.append("trade_review")

    return [
        {
            "name": name,
            "description": TOOL_DEFINITIONS[name]["description"],
            "parameters": TOOL_DEFINITIONS[name]["parameters"],
            "type": "function",
            "function": {
                "name": name,
                "description": TOOL_DEFINITIONS[name]["description"],
                "parameters": TOOL_DEFINITIONS[name]["parameters"],
            },
        }
        for name in names
    ]


def execute_tool(
    tool_name: str,
    user: UserClaims,
    args: dict[str, Any],
    settings: Settings | None = None,
    all_config: AllConfig | None = None,
    conn: Any = None,
    now: datetime | None = None,
    trade_log_text: str | None = None,
) -> dict[str, Any]:
    """Execute a registered tool by name with entitlement verification."""
    # Map names
    effective_name = tool_name
    if tool_name == "f1_contagion":
        effective_name = "market_scan"
    elif tool_name == "f2_filings":
        effective_name = "filings_check"
    elif tool_name == "f3_portfolio":
        effective_name = "trade_review"

    if effective_name not in TOOL_DEFINITIONS:
        return {
            "status": "error",
            "reason": f"Tool '{tool_name}' is not recognized. Available tools: {list(TOOL_DEFINITIONS.keys())}",
        }

    st = settings or load_settings()
    cfg = all_config or load_all_config()
    func: Callable[..., dict[str, Any]] = TOOL_DEFINITIONS[effective_name]["func"]

    call_args = dict(args)
    if effective_name == "trade_review" and trade_log_text and "trade_log_text" not in call_args:
        call_args["trade_log_text"] = trade_log_text

    return func(user=user, settings=st, all_config=cfg, conn=conn, now=now, **call_args)
