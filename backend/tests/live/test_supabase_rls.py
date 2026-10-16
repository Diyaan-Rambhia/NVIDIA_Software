"""Live integration tests for Supabase Row-Level Security (RLS) per PROGRESS.md X2.1."""

import uuid
from collections.abc import Generator

import psycopg
import pytest

from backend.app.config.env import load_settings
from backend.app.db.connection import DatabaseConnectionError, get_database_url


@pytest.fixture
def db_conn() -> Generator[psycopg.Connection, None, None]:
    """Provide a real database connection, skipping if DATABASE_URL is not configured."""
    settings = load_settings()
    try:
        url = get_database_url(settings)
    except DatabaseConnectionError:
        pytest.skip("not run: no database")

    try:
        conn = psycopg.connect(url, connect_timeout=5, autocommit=True)
    except Exception:
        pytest.skip("not run: no database")

    try:
        yield conn
    finally:
        conn.close()


def create_test_user(conn: psycopg.Connection) -> uuid.UUID:
    """Create a real test user in auth.users and return user_id."""
    user_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO auth.users (
                id, instance_id, aud, role, email,
                raw_app_meta_data, raw_user_meta_data, created_at, updated_at
            ) VALUES (
                %s, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
                %s, '{"provider":"email"}', '{}', now(), now()
            );
            """,
            (user_id, f"test_{user_id}@example.com"),
        )
    return user_id


def delete_test_user(conn: psycopg.Connection, user_id: uuid.UUID) -> None:
    """Delete a test user from auth.users (cascades to all user rows)."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM auth.users WHERE id = %s;", (user_id,))


def test_rls_isolation_between_users(db_conn: psycopg.Connection) -> None:
    """RLS blocks a user from reading another user's profile row."""
    user_a = create_test_user(db_conn)
    user_b = create_test_user(db_conn)

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.profiles (user_id, segment, plan, role, status)
            VALUES (%s, 'retail', 'retail_free', 'user', 'active'),
                   (%s, 'retail', 'retail_free', 'user', 'active');
            """,
            (user_a, user_b),
        )

        try:
            # Switch to user A
            cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false);", (str(user_a),))
            cur.execute("SELECT set_config('request.jwt.claim.role', 'authenticated', false);")
            cur.execute("SET ROLE authenticated;")

            # User A can query their own row
            cur.execute("SELECT user_id FROM public.profiles WHERE user_id = %s;", (user_a,))
            res_a = cur.fetchone()
            assert res_a is not None and res_a[0] == user_a

            # User A cannot query User B's row
            cur.execute("SELECT user_id FROM public.profiles WHERE user_id = %s;", (user_b,))
            res_b = cur.fetchone()
            assert res_b is None

        finally:
            cur.execute("RESET ROLE;")
            delete_test_user(db_conn, user_a)
            delete_test_user(db_conn, user_b)


def test_user_cannot_change_own_plan_or_segment(db_conn: psycopg.Connection) -> None:
    """A user cannot change their own plan or segment via authenticated role; service role can."""
    test_user = create_test_user(db_conn)

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.profiles (user_id, segment, plan, role, status)
            VALUES (%s, 'retail', 'retail_free', 'user', 'active');
            """,
            (test_user,),
        )

        try:
            cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false);", (str(test_user),))
            cur.execute("SELECT set_config('request.jwt.claim.role', 'authenticated', false);")
            cur.execute("SET ROLE authenticated;")

            # Attempt to escalate plan and segment -> 0 rows updated
            cur.execute(
                """
                UPDATE public.profiles
                SET plan = 'institutional_paid', segment = 'institutional'
                WHERE user_id = %s;
                """,
                (test_user,),
            )
            assert cur.rowcount == 0

            # Service role update succeeds
            cur.execute("RESET ROLE;")
            cur.execute(
                """
                UPDATE public.profiles
                SET plan = 'institutional_paid', segment = 'institutional'
                WHERE user_id = %s;
                """,
                (test_user,),
            )
            assert cur.rowcount == 1

        finally:
            cur.execute("RESET ROLE;")
            delete_test_user(db_conn, test_user)


def test_user_cannot_change_approval_status(db_conn: psycopg.Connection) -> None:
    """A user cannot approve their own registration; service role can."""
    test_user = create_test_user(db_conn)

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.institutional_verifications (
                user_id, regulator, registration_number, status
            ) VALUES (%s, 'SEBI', 'INZ0000001', 'pending');
            """,
            (test_user,),
        )

        try:
            cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false);", (str(test_user),))
            cur.execute("SELECT set_config('request.jwt.claim.role', 'authenticated', false);")
            cur.execute("SET ROLE authenticated;")

            # User attempts to self-approve -> 0 rows updated
            cur.execute(
                """
                UPDATE public.institutional_verifications
                SET status = 'approved'
                WHERE user_id = %s;
                """,
                (test_user,),
            )
            assert cur.rowcount == 0

            # Service role can approve
            cur.execute("RESET ROLE;")
            cur.execute(
                """
                UPDATE public.institutional_verifications
                SET status = 'approved'
                WHERE user_id = %s;
                """,
                (test_user,),
            )
            assert cur.rowcount == 1

        finally:
            cur.execute("RESET ROLE;")
            delete_test_user(db_conn, test_user)


def test_user_cannot_modify_quota_counter(db_conn: psycopg.Connection) -> None:
    """A user cannot insert or update usage quota counters directly; service role can."""
    test_user = create_test_user(db_conn)

    with db_conn.cursor() as cur:
        try:
            cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false);", (str(test_user),))
            cur.execute("SELECT set_config('request.jwt.claim.role', 'authenticated', false);")
            cur.execute("SET ROLE authenticated;")

            # User attempts to insert quota counter directly -> raises RLS error
            with pytest.raises(psycopg.Error):
                cur.execute(
                    """
                    INSERT INTO public.usage (user_id, feature, utc_date, count)
                    VALUES (%s, 'contagion', CURRENT_DATE, 0);
                    """,
                    (test_user,),
                )

            # Service role can manage usage counters
            cur.execute("RESET ROLE;")
            cur.execute(
                """
                INSERT INTO public.usage (user_id, feature, utc_date, count)
                VALUES (%s, 'contagion', CURRENT_DATE, 1)
                ON CONFLICT (user_id, feature, utc_date) DO UPDATE SET count = usage.count + 1;
                """,
                (test_user,),
            )
            assert cur.rowcount >= 1

        finally:
            cur.execute("RESET ROLE;")
            delete_test_user(db_conn, test_user)


def test_user_cannot_insert_row_for_another_user(db_conn: psycopg.Connection) -> None:
    """A user cannot insert a profile or record belonging to another user."""
    user_a = create_test_user(db_conn)
    user_b = create_test_user(db_conn)

    with db_conn.cursor() as cur:
        try:
            cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false);", (str(user_a),))
            cur.execute("SELECT set_config('request.jwt.claim.role', 'authenticated', false);")
            cur.execute("SET ROLE authenticated;")

            # User A attempts to insert profile for User B -> RLS WITH CHECK violation
            with pytest.raises(psycopg.Error):
                cur.execute(
                    """
                    INSERT INTO public.profiles (user_id, segment, plan, role, status)
                    VALUES (%s, 'retail', 'retail_free', 'user', 'active');
                    """,
                    (user_b,),
                )

        finally:
            cur.execute("RESET ROLE;")
            delete_test_user(db_conn, user_a)
            delete_test_user(db_conn, user_b)
