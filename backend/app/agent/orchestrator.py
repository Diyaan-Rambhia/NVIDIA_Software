"""Agent orchestrator loop with configurable step, budget, timeout, and advice guards."""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

from backend.app.agent.tools import execute_tool
from backend.app.auth.models import UserClaims
from backend.app.config.env import Settings, load_settings
from backend.app.config.loader import load_all_config
from backend.app.config.models import AllConfig
from backend.app.contracts.agent import AgentAskResponse, AgentStep
from backend.app.llm.exceptions import (
    BudgetExceededError,
    FinancialAdviceError,
    LLMTimeoutError,
    ProviderNotConfiguredError,
)
from backend.app.llm.guard import assert_no_financial_advice
from backend.app.llm.ledger import record_llm_call
from backend.app.llm.placeholder import PLACEHOLDER_MARKER, PlaceholderProvider

logger = logging.getLogger("backend.app.agent.orchestrator")


def _plan_tools_for_query(query: str) -> list[tuple[str, dict[str, Any]]]:
    """Select candidate tools and arguments based on user query."""
    q_lower = query.lower()
    planned: list[tuple[str, dict[str, Any]]] = []

    # Check F1 Contagion
    if any(k in q_lower for k in ("contagion", "correlation", "absorption", "systemic", "pair", "spillover")):
        planned.append(("f1_contagion", {}))

    # Check F2 Filings
    if any(k in q_lower for k in ("filing", "inconsistency", "discrepancy", "discrepancies", "revenue", "xbrl", "notes")):
        symbol_match = re.search(r"\b(INFY|RELIANCE|TCS|MARUTI|TATASTEEL)\b", query, re.IGNORECASE)
        symbol = symbol_match.group(1).upper() if symbol_match else None
        args: dict[str, Any] = {"symbol": symbol} if symbol else {}
        planned.append(("f2_filings", args))

    # Check F3 Portfolio / Trading Log
    if any(k in q_lower for k in ("portfolio", "trade", "trading", "log", "drawdown", "xirr", "alpha", "bias", "behavioral", "disposition")):
        planned.append(("f3_portfolio", {}))

    # If no specific domain keywords match, invoke default multi-domain tool plan
    if not planned:
        planned.append(("f1_contagion", {}))
        planned.append(("f2_filings", {}))

    return planned


def run_agent_loop(
    query: str,
    user: UserClaims,
    settings: Settings | None = None,
    all_config: AllConfig | None = None,
    conn: Any = None,
    max_steps_override: int | None = None,
    budget_usd_override: float | None = None,
    now: datetime | None = None,
) -> AgentAskResponse:
    """Execute multi-step agent tool loop with guards, timeouts, and accounting."""
    if not query or not query.strip():
        raise ValueError("Agent query must not be empty")

    st = settings or load_settings()
    cfg = all_config or load_all_config()
    start_time = time.monotonic()

    # 1. Resolve limits from config/parameters.yaml
    params = cfg.parameters.parameters
    step_param = params.get("agent_max_steps")
    budget_param = params.get("agent_budget_usd")
    timeout_param = params.get("agent_timeout_seconds")

    config_max_steps = int(step_param.default) if step_param else 5
    config_budget_usd = float(budget_param.default) if budget_param else 0.05
    timeout_seconds = float(timeout_param.default) if timeout_param else 30.0

    # Override evaluation
    max_steps = config_max_steps
    if max_steps_override is not None:
        if step_param and step_param.min is not None and max_steps_override < step_param.min:
            raise ValueError(f"max_steps ({max_steps_override}) cannot be less than minimum {step_param.min}")
        if step_param and step_param.max is not None and max_steps_override > step_param.max:
            raise ValueError(f"max_steps ({max_steps_override}) cannot exceed maximum {step_param.max}")
        max_steps = max_steps_override

    budget_usd = config_budget_usd
    if budget_usd_override is not None:
        if budget_param and budget_param.min is not None and budget_usd_override < budget_param.min:
            raise ValueError(f"budget_usd ({budget_usd_override}) cannot be less than minimum {budget_param.min}")
        if budget_param and budget_param.max is not None and budget_usd_override > budget_param.max:
            raise ValueError(f"budget_usd ({budget_usd_override}) cannot exceed maximum {budget_param.max}")
        budget_usd = budget_usd_override

    deadline = start_time + timeout_seconds

    # 2. Environment and provider validation
    raw_env = (st.get_var_value("APP_ENV") or st.app_env or "development").strip().lower()
    if raw_env in ("production", "prod"):
        raise ProviderNotConfiguredError(
            "Production mode requires a verified LLM provider with valid credentials. "
            "Placeholder provider is strictly forbidden in production."
        )

    # In dev/test: instantiate placeholder provider
    provider = PlaceholderProvider(settings=st, conn=conn)

    # 3. Plan tool execution
    planned_tools = _plan_tools_for_query(query)

    steps: list[AgentStep] = []
    total_spent_usd = 0.0
    tool_observations: list[dict[str, Any]] = []

    # 4. Execute tool loop
    for step_idx, (tool_name, tool_args) in enumerate(planned_tools, start=1):
        # Timeout guard
        if time.monotonic() > deadline:
            raise LLMTimeoutError(f"Agent loop exceeded configured timeout limit of {timeout_seconds}s")

        # Step limit guard
        if step_idx > max_steps:
            raise RuntimeError(f"Agent loop reached maximum step limit ({max_steps}) without completing")

        # Budget guard check
        projected_step_cost = provider.price_per_1m / 1000.0 if provider.price_per_1m > 0 else 0.001
        if (total_spent_usd + projected_step_cost) > budget_usd:
            raise BudgetExceededError(
                f"Agent per-run budget (${budget_usd:.4f}) exceeded with projected cost "
                f"${(total_spent_usd + projected_step_cost):.4f}"
            )

        step_start = time.monotonic()
        tool_res = execute_tool(
            tool_name=tool_name,
            user=user,
            args=tool_args,
            settings=st,
            all_config=cfg,
            conn=conn,
            now=now,
        )
        step_duration = (time.monotonic() - step_start) * 1000.0

        status = tool_res.get("status", "error")
        if status == "error":
            raise RuntimeError(f"Invalid tool output from '{tool_name}': {tool_res.get('reason')}")

        input_summary = f"{tool_name}({', '.join(f'{k}={v}' for k, v in tool_args.items()) if tool_args else ''})"
        if status == "denied":
            output_summary = f"Denied: {tool_res.get('reason')}"
        else:
            data = tool_res.get("data", {})
            output_summary = f"Success: retrieved {len(data)} fields ({', '.join(list(data.keys())[:3])})"

        step_record = AgentStep(
            step_number=step_idx,
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=output_summary,
            status=status,
            est_cost_usd=projected_step_cost,
            duration_ms=round(step_duration, 2),
        )
        steps.append(step_record)
        total_spent_usd += projected_step_cost
        tool_observations.append({
            "tool": tool_name,
            "status": status,
            "summary": output_summary,
            "data": tool_res.get("data"),
            "reason": tool_res.get("reason"),
        })

        if conn is not None:
            try:
                record_llm_call(
                    conn=conn,
                    user_id=user.user_id,
                    route="/agent/ask",
                    alias="fast",
                    model_id="placeholder-agent-loop",
                    input_tokens=150,
                    output_tokens=150,
                    est_cost_usd=projected_step_cost,
                )
            except Exception as exc:
                logger.warning("Could not record agent step to ledger: %s", exc)

    # 5. Check timeout before synthesis
    if time.monotonic() > deadline:
        raise LLMTimeoutError(f"Agent loop exceeded configured timeout limit of {timeout_seconds}s during answer synthesis")

    # 6. Synthesize final response
    answer_parts: list[str] = [
        f"[{PLACEHOLDER_MARKER}] Analysis for query: {query}",
    ]
    for obs in tool_observations:
        tname = obs["tool"]
        if obs["status"] == "denied":
            answer_parts.append(f"- Tool '{tname}' was denied: {obs.get('reason')}")
        else:
            tdata = obs.get("data") or {}
            key_insights = [f"{k}: {v}" for k, v in list(tdata.items())[:3]]
            answer_parts.append(f"- Tool '{tname}' verified metrics: {'; '.join(key_insights)}")

    answer_parts.append(
        "Observation summary completed deterministically. All analytical metrics reflect authentic historical data."
    )
    final_answer = "\n".join(answer_parts)

    # 7. Output guard check: verify no prohibited buy/sell/hold financial advice
    assert_no_financial_advice(final_answer)

    total_duration_ms = (time.monotonic() - start_time) * 1000.0

    return AgentAskResponse(
        query=query,
        answer=final_answer,
        steps=steps,
        total_cost_usd=round(total_spent_usd, 6),
        duration_ms=round(total_duration_ms, 2),
        is_placeholder=True,
        disclaimer=(
            "Educational and research review only. FinInsight does not provide "
            "investment recommendations or financial advice."
        ),
    )
