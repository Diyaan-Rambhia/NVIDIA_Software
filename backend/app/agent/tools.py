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

F1_DATA_PATH = Path("demo_data") / "f1_scan_demo.json" if (Path("demo_data") / "f1_scan_demo.json").is_file() else Path("data") / "f1_scan_demo.json"
F2_DATA_PATH = Path("demo_data") / "f2_filings_demo.json" if (Path("demo_data") / "f2_filings_demo.json").is_file() else Path("data") / "f2_filings_demo.json"
F3_DATA_PATH = Path("demo_data") / "f3_review_demo.json" if (Path("demo_data") / "f3_review_demo.json").is_file() else Path("data") / "f3_review_demo.json"


def _evaluate_tool_entitlement(
    user: UserClaims,
    feature_key: str,
    all_config: AllConfig,
    conn: Any = None,
    now: datetime | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    """Check entitlement for feature_key. Returns (allowed, denial_dict)."""
    if user.plan == "judge_all":
        return True, None

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

    if not F1_DATA_PATH.is_file():
        return {
            "status": "error",
            "reason": "Feature 1 contagion scan data not available on disk",
        }

    try:
        raw_data = json.loads(F1_DATA_PATH.read_text(encoding="utf-8"))
        summary = {
            "as_of": raw_data.get("as_of"),
            "absorption_ratio": raw_data.get("absorption_ratio"),
            "ar_delta_std": raw_data.get("ar_delta_std"),
            "mean_correlation": raw_data.get("mean_correlation"),
            "significant_pairs_count": raw_data.get("significant_pairs_count"),
            "top_shifted_pairs": raw_data.get("top_shifted_pairs", [])[:3],
            "data_source_label": raw_data.get("data_source_label", "unofficial source, demo only"),
        }
        return {"status": "success", "data": summary}
    except Exception as exc:
        logger.error("Failed to read F1 data: %s", exc)
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

    target_file = F2_DATA_PATH
    if symbol:
        sym_clean = symbol.strip().upper()
        parsed_path = Path("demo_data") / f"f2_parsed_{sym_clean}.json"
        if not parsed_path.is_file():
            parsed_path = Path("data") / f"f2_parsed_{sym_clean}.json"
        if parsed_path.is_file():
            target_file = parsed_path

    if not target_file.is_file():
        return {
            "status": "error",
            "reason": f"Filing consistency data not found for target {target_file.name}",
        }

    try:
        raw_data = json.loads(target_file.read_text(encoding="utf-8"))
        inconsistencies = raw_data.get("inconsistencies", [])
        return {
            "status": "success",
            "data": {
                "source_file": target_file.name,
                "inconsistency_count": len(inconsistencies),
                "inconsistencies": inconsistencies[:5],
                "companies_checked": raw_data.get("companies_checked", [symbol] if symbol else []),
            },
        }
    except Exception as exc:
        logger.error("Failed to read F2 data: %s", exc)
        return {"status": "error", "reason": f"F2 execution error: {exc}"}


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

    if not F3_DATA_PATH.is_file():
        return {
            "status": "error",
            "reason": "Feature 3 portfolio review demo data not found on disk",
        }

    try:
        raw_data = json.loads(F3_DATA_PATH.read_text(encoding="utf-8"))
        summary = {
            "xirr": raw_data.get("xirr"),
            "benchmark_alpha_bps": raw_data.get("benchmark_alpha_bps"),
            "max_drawdown": raw_data.get("max_drawdown"),
            "win_rate": raw_data.get("win_rate"),
            "turnover_annualized": raw_data.get("turnover_annualized"),
            "is_synthetic_demo": raw_data.get("is_synthetic_demo", False),
            "disclosure_label": raw_data.get("disclosure_label"),
            "process_metrics": raw_data.get("process_metrics"),
        }
        return {"status": "success", "data": summary}
    except Exception as exc:
        logger.error("Failed to read F3 data: %s", exc)
        return {"status": "error", "reason": f"F3 execution error: {exc}"}


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
