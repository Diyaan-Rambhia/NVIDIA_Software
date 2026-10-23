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


def tool_f1_contagion(
    user: UserClaims,
    settings: Settings,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Analyze market contagion metrics and systemic correlation shifts."""
    allowed, denial = _evaluate_tool_entitlement(user, "feature1_contagion", all_config, conn, now)
    if not allowed:
        return denial or {"status": "denied", "reason": "Entitlement denied"}

    try:
        from backend.app.features.f1_contagion.pipeline import run_correlation_scan
        scan = run_correlation_scan()
        summary = {
            "as_of": scan.as_of,
            "absorption_ratio": scan.absorption_ratio,
            "ar_delta_std": scan.ar_delta_std,
            "mean_correlation": scan.mean_correlation,
            "significant_pairs_count": scan.significant_pairs_count,
            "top_shifted_pairs": [p.model_dump() for p in scan.top_shifted_pairs[:3]],
            "data_source_label": scan.source_label,
        }
        return {"status": "success", "data": summary}
    except Exception as exc:
        logger.error("Failed to execute live F1 scan: %s", exc)
        return {"status": "error", "reason": f"F1 execution error: {exc}"}


def tool_f2_filings(
    user: UserClaims,
    settings: Settings,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
    symbol: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Inspect quarterly financial filings for reported inconsistencies."""
    allowed, denial = _evaluate_tool_entitlement(user, "feature2_filings", all_config, conn, now)
    if not allowed:
        return denial or {"status": "denied", "reason": "Entitlement denied"}

    try:
        from backend.app.features.f2_filings.lookup import perform_f2_lookup
        sym = (symbol or "INFY").strip().upper()
        res = perform_f2_lookup(sym, "Q1 FY27")
        rules = res.get("rules", [])
        return {
            "status": "success",
            "data": {
                "company": res.get("company_name", sym),
                "period": res.get("fiscal_period", "Q1 FY27"),
                "rules_evaluated": len(rules),
                "inconsistencies": [r for r in rules if r.get("status") in ("flag", "fail")][:5],
            },
        }
    except Exception as exc:
        logger.error("Failed to execute live F2 lookup: %s", exc)
        return {"status": "error", "reason": f"F2 lookup error: {exc}"}


def tool_f3_portfolio(
    user: UserClaims,
    settings: Settings,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Review investment trade log for performance, risk, and behavioral metrics."""
    allowed, denial = _evaluate_tool_entitlement(user, "feature3_forensic", all_config, conn, now)
    if not allowed:
        return denial or {"status": "denied", "reason": "Entitlement denied"}

    return {
        "status": "success",
        "data": {
            "message": "Upload a trade log CSV in the Trade Log review view to evaluate portfolio metrics and XIRR.",
            "metrics_available": ["FIFO lot accounting", "XIRR vs benchmark", "Disposition effect", "Turnover"],
        },
    }


TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "f1_contagion": {
        "name": "f1_contagion",
        "description": "Inspect market contagion metrics, systemic absorption ratio, and correlation shifts across benchmark equities.",
        "parameters": {},
        "func": tool_f1_contagion,
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
        "func": tool_f2_filings,
    },
    "f3_portfolio": {
        "name": "f3_portfolio",
        "description": "Review trade log execution for return metrics (XIRR, alpha), risk metrics (drawdown), and behavioral biases.",
        "parameters": {},
        "func": tool_f3_portfolio,
    },
}


def get_available_tools() -> list[dict[str, Any]]:
    """Return tool schemas for agent prompts."""
    return [
        {
            "name": name,
            "description": info["description"],
            "parameters": info["parameters"],
        }
        for name, info in TOOL_DEFINITIONS.items()
    ]


def execute_tool(
    tool_name: str,
    user: UserClaims,
    args: dict[str, Any],
    settings: Settings | None = None,
    all_config: AllConfig | None = None,
    conn: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Execute a registered tool by name with entitlement verification."""
    if tool_name not in TOOL_DEFINITIONS:
        return {
            "status": "error",
            "reason": f"Tool '{tool_name}' is not recognized. Available tools: {list(TOOL_DEFINITIONS.keys())}",
        }

    st = settings or load_settings()
    cfg = all_config or load_all_config()
    func: Callable[..., dict[str, Any]] = TOOL_DEFINITIONS[tool_name]["func"]
    return func(user=user, settings=st, all_config=cfg, conn=conn, now=now, **args)
