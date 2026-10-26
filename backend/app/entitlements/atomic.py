"""Atomic quota increments and usage tracking in PostgreSQL."""

import uuid
from typing import Any

import psycopg


def increment_quota_atomic(
    conn: psycopg.Connection[Any],
    user_id: uuid.UUID,
    feature: str,
    max_quota: int,
    settings: Any = None,
) -> tuple[bool, int]:
    """Atomically increment daily quota counter in public.usage with closed-connection retry.

    Ensures two parallel requests cannot both pass at limit minus one.
    Returns (True, new_count) if increment succeeded within quota.
    Returns (False, current_count) if quota is already exhausted.
    """
    if max_quota <= 0:
        return False, 0

    from backend.app.db.connection import get_connection, is_connection_closed
    from backend.app.llm.exceptions import LedgerError

    def _execute(target_conn: psycopg.Connection[Any]) -> tuple[bool, int]:
        with target_conn.cursor() as cur:
            # Atomic upsert guarded by WHERE clause on current count
            cur.execute(
                """
                INSERT INTO public.usage (user_id, feature, utc_date, count)
                VALUES (%s, %s, CURRENT_DATE, 1)
                ON CONFLICT (user_id, feature, utc_date)
                DO UPDATE SET count = public.usage.count + 1, updated_at = now()
                WHERE public.usage.count < %s
                RETURNING count;
                """,
                (user_id, feature, max_quota),
            )
            row = cur.fetchone()
            if not target_conn.autocommit:
                target_conn.commit()
            if row is not None:
                return True, int(row[0])

            # If 0 rows updated, query current count
            cur.execute(
                """
                SELECT count FROM public.usage
                WHERE user_id = %s AND feature = %s AND utc_date = CURRENT_DATE;
                """,
                (user_id, feature),
            )
            existing = cur.fetchone()
            if not target_conn.autocommit:
                target_conn.commit()
            current_val = int(existing[0]) if existing else max_quota
            return False, current_val

    if conn is not None and not is_connection_closed(conn):
        try:
            return _execute(conn)
        except Exception as first_exc:
            err_msg = str(first_exc).lower()
            if not (
                "closed" in err_msg
                or "broken" in err_msg
                or isinstance(first_exc, (psycopg.OperationalError, psycopg.InterfaceError))
            ):
                raise

    fresh_conn = None
    try:
        fresh_conn = get_connection(settings, autocommit=True)
        return _execute(fresh_conn)
    except Exception as second_exc:
        raise LedgerError(f"LEDGER_ERROR: Failed to update usage quota: {second_exc}") from second_exc
    finally:
        if fresh_conn is not None:
            try:
                fresh_conn.close()
            except Exception:
                pass


def get_today_usage(
    conn: psycopg.Connection[Any],
    user_id: uuid.UUID,
    feature: str,
    settings: Any = None,
) -> int:
    """Retrieve today's usage count for a user and feature with closed-conn resilience."""
    from backend.app.db.connection import get_connection, is_connection_closed

    def _query(target_conn: psycopg.Connection[Any]) -> int:
        with target_conn.cursor() as cur:
            cur.execute(
                """
                SELECT count FROM public.usage
                WHERE user_id = %s AND feature = %s AND utc_date = CURRENT_DATE;
                """,
                (user_id, feature),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    if conn is not None and not is_connection_closed(conn):
        try:
            return _query(conn)
        except Exception as first_exc:
            err_msg = str(first_exc).lower()
            if not (
                "closed" in err_msg
                or "broken" in err_msg
                or isinstance(first_exc, (psycopg.OperationalError, psycopg.InterfaceError))
            ):
                raise

    fresh_conn = None
    try:
        fresh_conn = get_connection(settings, autocommit=True)
        return _query(fresh_conn)
    finally:
        if fresh_conn is not None:
            try:
                fresh_conn.close()
            except Exception:
                pass

