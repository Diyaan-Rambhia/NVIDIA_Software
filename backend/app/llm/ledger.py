"""Token usage accounting and budget guard backed by public.llm_ledger."""

import uuid
from typing import Any

import psycopg

from backend.app.llm.exceptions import BudgetExceededError


def calculate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    price_per_1m_input_usd: float,
    price_per_1m_output_usd: float,
) -> float:
    """Calculate call cost in USD from token counts and per-million pricing."""
    in_cost = (max(0, input_tokens) / 1_000_000.0) * price_per_1m_input_usd
    out_cost = (max(0, output_tokens) / 1_000_000.0) * price_per_1m_output_usd
    return round(in_cost + out_cost, 6)


def get_today_spent_usd(conn: psycopg.Connection[Any]) -> float:
    """Sum today's estimated LLM spend from public.llm_ledger."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT coalesce(sum(est_cost_usd), 0.0)
            FROM public.llm_ledger
            WHERE ts >= CURRENT_DATE;
            """
        )
        row = cur.fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0


def check_budget_guard(
    conn: psycopg.Connection[Any],
    projected_cost_usd: float,
    daily_budget_usd: float,
) -> None:
    """Refuse call if today's spend + projected cost exceeds daily budget."""
    if daily_budget_usd <= 0.0:
        return

    current_spent = get_today_spent_usd(conn)
    if (current_spent + projected_cost_usd) > daily_budget_usd:
        raise BudgetExceededError(
            f"Daily LLM budget limit of ${daily_budget_usd:.4f} exceeded. "
            f"Current spend: ${current_spent:.4f}, projected cost: ${projected_cost_usd:.4f}."
        )


def record_llm_call(
    conn: psycopg.Connection[Any],
    user_id: uuid.UUID | None,
    route: str,
    alias: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    est_cost_usd: float,
    cache_hit: bool = False,
) -> uuid.UUID:
    """Record an LLM invocation in public.llm_ledger (server-side only)."""
    ledger_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.llm_ledger (
                id, ts, user_id, route, alias, model_id,
                input_tokens, output_tokens, est_cost_usd, cache_hit
            ) VALUES (
                %s, now(), %s, %s, %s, %s,
                %s, %s, %s, %s
            );
            """,
            (
                ledger_id,
                user_id,
                route,
                alias,
                model_id,
                input_tokens,
                output_tokens,
                est_cost_usd,
                cache_hit,
            ),
        )
    if not conn.autocommit:
        conn.commit()

    return ledger_id
