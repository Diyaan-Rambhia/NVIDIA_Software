"""Tests for database connection resilience and retry in llm_ledger and agent path.

Verifies:
(a) closed real connection on purpose reconnects and writes the ledger row;
(b) held connection with a 3-second wait in provider complete finishes and ledger row exists;
(c) both tries fail when pointed at unreachable address, returning LEDGER_ERROR.
"""

import time
import uuid
from typing import Any

import pytest

from backend.app.agent.orchestrator import run_agent_loop
from backend.app.auth.models import UserClaims
from backend.app.config.env import Settings, load_settings
from backend.app.config.loader import load_all_config
from backend.app.db.connection import get_connection
from backend.app.llm.exceptions import LedgerError
from backend.app.llm.ledger import record_llm_call


def _check_real_database() -> bool:
    try:
        s = load_settings()
        c = get_connection(s, autocommit=True)
        with c.cursor() as cur:
            cur.execute("SELECT 1;")
        c.close()
        return True
    except Exception:
        return False


def test_closed_connection_reconnects_and_writes_row() -> None:
    """(a) Close a real connection on purpose, then call ledger write function;

    It must reconnect and write the row back to public.llm_ledger.
    """
    if not _check_real_database():
        pytest.skip("not run: real database not available")

    settings = load_settings()
    conn = get_connection(settings, autocommit=True)
    # Deliberately close the connection
    conn.close()
    assert conn.closed, "Connection must be closed prior to ledger call"

    test_route = f"/test/resilience/closed_conn_{uuid.uuid4().hex[:8]}"
    ledger_id: uuid.UUID | None = None
    try:
        ledger_id = record_llm_call(
            conn=conn,
            user_id=None,
            route=test_route,
            alias="balanced",
            model_id="test-resilience-model",
            input_tokens=120,
            output_tokens=60,
            est_cost_usd=0.0001,
            cache_hit=False,
            settings=settings,
        )
        assert ledger_id is not None, "record_llm_call should return a valid UUID"

        # Verify row exists in DB
        verify_conn = get_connection(settings, autocommit=True)
        try:
            with verify_conn.cursor() as cur:
                cur.execute(
                    "SELECT route, input_tokens, output_tokens FROM public.llm_ledger WHERE id = %s;",
                    (ledger_id,),
                )
                row = cur.fetchone()
                assert row is not None, "Ledger row must exist in database after reconnection"
                assert row[0] == test_route
                assert row[1] == 120
                assert row[2] == 60
        finally:
            with verify_conn.cursor() as cur:
                cur.execute("DELETE FROM public.llm_ledger WHERE route = %s;", (test_route,))
            verify_conn.close()
    except Exception:
        raise


def test_held_connection_with_3s_wait_in_provider_writes_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """(b) Hold a connection, run a 3-second wait inside request path with test provider helper,

    then write; the row exists.
    """
    if not _check_real_database():
        pytest.skip("not run: real database not available")

    # Mock tool execution to complete deterministically without slow external calls
    monkeypatch.setattr(
        "backend.app.agent.orchestrator.execute_tool",
        lambda **kwargs: {"status": "success", "data": {"absorption_ratio": 0.85}},
    )

    settings = load_settings()
    all_config = load_all_config()

    init_conn = get_connection(settings, autocommit=True)
    with init_conn.cursor() as cur:
        cur.execute("SELECT id, email FROM auth.users LIMIT 1;")
        user_row = cur.fetchone()
        real_user_id = user_row[0] if user_row else uuid.uuid4()
        real_email = user_row[1] if user_row else "judge@example.com"
    init_conn.close()

    user = UserClaims(
        user_id=real_user_id,
        email=real_email,
        role="judge",
        plan="judge_all",
        segment="internal",
        is_admin=True,
    )

    test_route = f"/test/resilience/wait3s_{uuid.uuid4().hex[:8]}"

    class SlowTestProvider:
        def __init__(self) -> None:
            self.is_placeholder = False

            class PricingReg:
                def get_pricing(self, alias: str) -> tuple[float, float]:
                    return (0.1, 0.2)

            self.registry = PricingReg()

        def complete(self, alias: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
            # Simulate a 3-second network wait inside request path
            time.sleep(3)
            # Record ledger write directly as complete normally does
            record_llm_call(
                conn=None,
                user_id=real_user_id,
                route=test_route,
                alias=alias,
                model_id="model-tier-balanced",
                input_tokens=200,
                output_tokens=100,
                est_cost_usd=0.00004,
                settings=settings,
            )
            return {
                "id": "chatcmpl-test-slow-wait",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Analysis for query: test 3s wait.\nDeterministic audit completed.",
                        }
                    }
                ],
            }

    held_conn = get_connection(settings, autocommit=True)
    try:
        provider = SlowTestProvider()
        resp = run_agent_loop(
            query="Analyze market contagion absorption ratio",
            user=user,
            settings=settings,
            all_config=all_config,
            conn=held_conn,
            model_tier="balanced",
            provider=provider,
        )
        assert resp is not None
        assert "Analysis for query:" in resp.answer

        # Verify the ledger row exists
        with held_conn.cursor() as cur:
            cur.execute(
                "SELECT id, route, input_tokens FROM public.llm_ledger WHERE route = %s;",
                (test_route,),
            )
            row = cur.fetchone()
            assert row is not None, "Ledger row must exist in database after 3s wait"
            assert row[1] == test_route
            assert row[2] == 200
    finally:
        try:
            with held_conn.cursor() as cur:
                cur.execute("DELETE FROM public.llm_ledger WHERE route = %s;", (test_route,))
        except Exception:
            pass
        held_conn.close()


def test_both_tries_fail_returns_ledger_error() -> None:
    """(c) Both tries fail (point write at unreachable address through settings):

    the result is LEDGER_ERROR.
    """
    unreachable_settings = Settings(
        app_env="test",
        database_url="postgresql://invalid_user:invalid_pass@127.0.0.1:54329/unreachable_db?connect_timeout=1",
    )

    with pytest.raises(LedgerError) as exc_info:
        record_llm_call(
            conn=None,
            user_id=None,
            route="/test/unreachable",
            alias="balanced",
            model_id="test-unreachable",
            input_tokens=10,
            output_tokens=10,
            settings=unreachable_settings,
        )

    err_str = str(exc_info.value)
    assert "LEDGER_ERROR" in err_str, f"Expected LEDGER_ERROR in message, got: {err_str}"
