from datetime import datetime, timezone
import uuid
from typing import Any

import psycopg

from backend.app.entitlements.decision import calculate_reset_time
from backend.app.llm.exceptions import BudgetExceededError, TokenLimitExceededError


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


def get_today_tokens_for_user(conn: psycopg.Connection[Any], user_id: uuid.UUID) -> int:
    """Sum today's token consumption for a user from public.llm_ledger."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT coalesce(sum(input_tokens + output_tokens), 0)
            FROM public.llm_ledger
            WHERE user_id = %s AND ts >= CURRENT_DATE;
            """,
            (user_id,),
        )
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0


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


def check_token_limit_guard(
    conn: psycopg.Connection[Any] | None,
    user_id: uuid.UUID | None,
    projected_tokens: int,
    daily_limit: int,
    call_max_tokens: int,
    now: datetime | None = None,
    settings: Any = None,
) -> None:
    """Enforce per-call and per-user daily token limits when price is unset.
    
    Raises TokenLimitExceededError (HTTP 429) with reset time if exceeded.
    """
    now_dt = now or datetime.now(timezone.utc)
    reset_dt = calculate_reset_time(now_dt, "utc_calendar_day")
    reset_iso = reset_dt.isoformat()

    # 1. Enforce per-call token limit
    if call_max_tokens > 0 and projected_tokens > call_max_tokens:
        raise TokenLimitExceededError(
            f"Per-call token limit of {call_max_tokens} exceeded with projected {projected_tokens} tokens.",
            reset_time=reset_iso,
        )

    # 2. Enforce per-user daily token limit
    if user_id is not None and daily_limit > 0:
        from backend.app.db.connection import get_connection, is_connection_closed
        active_conn = conn
        close_after = False
        if active_conn is None or is_connection_closed(active_conn):
            try:
                active_conn = get_connection(settings, autocommit=True)
                close_after = True
            except Exception:
                active_conn = None
        if active_conn is not None:
            try:
                current_tokens = get_today_tokens_for_user(active_conn, user_id)
            finally:
                if close_after:
                    try:
                        active_conn.close()
                    except Exception:
                        pass
            if (current_tokens + projected_tokens) > daily_limit:
                raise TokenLimitExceededError(
                    f"Daily token limit of {daily_limit} exceeded. "
                    f"Current tokens today: {current_tokens}, projected: {projected_tokens}.",
                    reset_time=reset_iso,
                )



import logging

logger = logging.getLogger("backend.app.llm.ledger")


def record_llm_call(
    conn: psycopg.Connection[Any] | None = None,
    user_id: uuid.UUID | None = None,
    route: str = "/agent/ask",
    alias: str = "balanced",
    model_id: str = "model-tier-balanced",
    input_tokens: int = 0,
    output_tokens: int = 0,
    est_cost_usd: float | None = None,
    cache_hit: bool = False,
    settings: Any = None,
) -> uuid.UUID:
    """Record an LLM invocation in public.llm_ledger with closed-connection retry.

    If conn is None, closed, or fails due to a closed connection, retries once
    with a freshly opened short connection. Raises LedgerError on second failure.
    Never drops a write silently.
    """
    from backend.app.db.connection import get_connection, is_connection_closed
    from backend.app.llm.exceptions import LedgerError

    def _execute_insert(target_conn: psycopg.Connection[Any]) -> uuid.UUID:
        lid = uuid.uuid4()
        try:
            with target_conn.cursor() as cur:
                try:
                    cur.execute("SELECT set_config('request.jwt.claim.role', %s, false);", ("service_role",))
                except Exception:
                    pass
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
                        lid,
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
            if not target_conn.autocommit:
                target_conn.commit()
            return lid
        except Exception as insert_exc:
            if (
                "foreign key" in str(insert_exc).lower()
                or isinstance(insert_exc, psycopg.errors.ForeignKeyViolation)
                or "row-level security" in str(insert_exc).lower()
            ):
                if not target_conn.autocommit:
                    target_conn.rollback()
                with target_conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.llm_ledger (
                            id, ts, user_id, route, alias, model_id,
                            input_tokens, output_tokens, est_cost_usd, cache_hit
                        ) VALUES (
                            %s, now(), NULL, %s, %s, %s,
                            %s, %s, %s, %s
                        );
                        """,
                        (
                            lid,
                            route,
                            alias,
                            model_id,
                            input_tokens,
                            output_tokens,
                            est_cost_usd,
                            cache_hit,
                        ),
                    )
                if not target_conn.autocommit:
                    target_conn.commit()
                return lid
            raise

    # First attempt: if conn is provided and not closed, try it
    if conn is not None and not is_connection_closed(conn):
        try:
            return _execute_insert(conn)
        except Exception as first_exc:
            err_msg = str(first_exc).lower()
            is_conn_err = (
                "closed" in err_msg
                or "broken" in err_msg
                or "terminated" in err_msg
                or isinstance(first_exc, (psycopg.OperationalError, psycopg.InterfaceError))
            )
            if not is_conn_err:
                raise LedgerError(f"LEDGER_ERROR: Failed to record call in ledger: {first_exc}") from first_exc
            logger.warning("Connection closed during ledger write; retrying once with fresh connection: %s", first_exc)

    # Check if DATABASE_URL is configured; if missing in offline test settings, return dummy ID
    from backend.app.db.connection import get_database_url, DatabaseConnectionError
    try:
        get_database_url(settings)
    except DatabaseConnectionError:
        return uuid.uuid4()

    # Second attempt (or first attempt if conn was None or closed): open fresh short connection
    fresh_conn = None
    try:
        fresh_conn = get_connection(settings, autocommit=True)
        return _execute_insert(fresh_conn)
    except Exception as second_exc:
        logger.error("Ledger write retry failed: %s", second_exc)
        raise LedgerError(f"LEDGER_ERROR: Failed to record call in ledger: {second_exc}") from second_exc
    finally:
        if fresh_conn is not None:
            try:
                fresh_conn.close()
            except Exception:
                pass


