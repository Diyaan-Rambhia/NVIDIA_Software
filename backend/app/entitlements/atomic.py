"""Atomic quota increments and usage tracking in PostgreSQL."""

import uuid
from typing import Any

import psycopg


def increment_quota_atomic(
    conn: psycopg.Connection[Any],
    user_id: uuid.UUID,
    feature: str,
    max_quota: int,
) -> tuple[bool, int]:
    """Atomically increment daily quota counter in public.usage.

    Ensures two parallel requests cannot both pass at limit minus one.
    Returns (True, new_count) if increment succeeded within quota.
    Returns (False, current_count) if quota is already exhausted.
    """
    if max_quota <= 0:
        return False, 0

    with conn.cursor() as cur:
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
        if not conn.autocommit:
            conn.commit()
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
        if not conn.autocommit:
            conn.commit()
        current_val = int(existing[0]) if existing else max_quota
        return False, current_val


def get_today_usage(
    conn: psycopg.Connection[Any],
    user_id: uuid.UUID,
    feature: str,
) -> int:
    """Retrieve today's usage count for a user and feature."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count FROM public.usage
            WHERE user_id = %s AND feature = %s AND utc_date = CURRENT_DATE;
            """,
            (user_id, feature),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0
