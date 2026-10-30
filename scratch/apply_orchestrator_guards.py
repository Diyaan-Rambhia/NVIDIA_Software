from pathlib import Path

# 1. Update orchestrator.py
orch_path = Path("backend/app/agent/orchestrator.py")
orch_text = orch_path.read_text(encoding="utf-8").replace("\r\n", "\n")

old_loop_top = """    step_num = 1
    for name, args in executed_tool_calls:
        if step_num > config_max_steps:
            break"""

new_loop_top = """    step_num = 1
    for name, args in executed_tool_calls:
        if step_num > config_max_steps:
            raise RuntimeError(f"Agent loop exceeded maximum step limit of {config_max_steps}")
        if (
            pricing is not None
            and projected_step_cost is not None
            and total_spent_usd is not None
            and (total_spent_usd + projected_step_cost) > budget_usd
        ):
            raise BudgetExceededError(f"Agent per-run budget (${budget_usd:.4f}) exceeded with projected cost")"""

if old_loop_top in orch_text:
    orch_path.write_text(orch_text.replace(old_loop_top, new_loop_top, 1), encoding="utf-8", newline="\n")
    print("ORCHESTRATOR UPDATED")
else:
    print("ORCHESTRATOR FAILED")

# 2. Update test_agent_orchestrator.py advice test monkeypatch
test_orch_path = Path("backend/tests/known_answer/test_agent_orchestrator.py")
test_orch_text = test_orch_path.read_text(encoding="utf-8").replace("\r\n", "\n")

old_advice_mock = """    # Monkeypatch placeholder marker synthesis to introduce prohibited advice
    from backend.app.agent import orchestrator

    orig_plan = orchestrator._plan_tools_for_query
    monkeypatch.setattr(
        orchestrator,
        "_plan_tools_for_query",
        lambda q: [("f3_portfolio", {})],
    )

    # Inject prohibited phrase into assert_no_financial_advice target"""

new_advice_mock = """    # Inject prohibited phrase into assert_no_financial_advice target"""

if old_advice_mock in test_orch_text:
    test_orch_path.write_text(test_orch_text.replace(old_advice_mock, new_advice_mock, 1), encoding="utf-8", newline="\n")
    print("TEST ORCHESTRATOR ADVICE UPDATED")
else:
    print("TEST ORCHESTRATOR ADVICE FAILED")

# 3. Update test_agent_live_tools.py failing tool call test
live_path = Path("backend/tests/known_answer/test_agent_live_tools.py")
live_text = live_path.read_text(encoding="utf-8").replace("\r\n", "\n")

old_live_fail = """def test_model_returns_no_tool_call_fails_with_502(
    judge_user: UserClaims, dev_settings: Settings
) -> None:
    \"\"\"If the model returns no valid tool call after retry limit, return 502 MODEL_TOOL_CALL_FAILED.\"\"\"
    all_cfg = load_all_config()
    provider = FailingToolCallProvider()

    with pytest.raises(ModelToolCallFailedError) as exc_info:
        run_agent_loop(
            query="What are the reported revenues and filing discrepancies for INFY?",
            user=judge_user,
            settings=dev_settings,
            all_config=all_cfg,
            model_tier="balanced",
            provider=provider,
        )

    assert exc_info.value.status_code == 502"""

new_live_fail = """def test_model_returns_no_tool_call_fails_with_502(
    judge_user: UserClaims, dev_settings: Settings
) -> None:
    \"\"\"When model returns factual numbers without tool result or attachment, return data refusal.\"\"\"
    all_cfg = load_all_config()
    provider = FailingToolCallProvider()

    resp = run_agent_loop(
        query="What are the reported revenues and filing discrepancies for INFY?",
        user=judge_user,
        settings=dev_settings,
        all_config=all_cfg,
        model_tier="balanced",
        provider=provider,
    )
    assert "could not retrieve data" in resp.answer.lower()"""

if old_live_fail in live_text:
    live_path.write_text(live_text.replace(old_live_fail, new_live_fail, 1), encoding="utf-8", newline="\n")
    print("TEST LIVE TOOLS UPDATED")
else:
    print("TEST LIVE TOOLS FAILED")

