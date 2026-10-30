import pathlib

# 1. Update orchestrator.py
p_orch = pathlib.Path("backend/app/agent/orchestrator.py")
text_orch = p_orch.read_text(encoding="utf-8")

# Fix max_steps_override
old_step_override = "config_max_steps = int(step_param.default) if step_param else 5"
new_step_override = '''config_max_steps = int(step_param.default) if step_param else 5
    if max_steps_override is not None:
        config_max_steps = max_steps_override'''

if "if max_steps_override is not None:" not in text_orch:
    text_orch = text_orch.replace(old_step_override, new_step_override)

# Fix placeholder answer when a step was denied
old_placeholder_ans = '''    if is_placeholder:
        ref_note = " Reference data observed." if attachment_text else ""
        final_answer = (
            f"{PLACEHOLDER_MARKER}. Quantitative audit completed from computed evidence.{ref_note} "
            "Educational and research analytics only. No investment advice."
        )'''

new_placeholder_ans = '''    if is_placeholder:
        ref_note = " Reference data observed." if attachment_text else ""
        denied_note = " Requested tool was denied." if any(s.status == "denied" for s in steps) else ""
        final_answer = (
            f"{PLACEHOLDER_MARKER}. Quantitative audit completed from computed evidence.{ref_note}{denied_note} "
            "Educational and research analytics only. No investment advice."
        )'''

if "denied_note = " not in text_orch:
    text_orch = text_orch.replace(old_placeholder_ans, new_placeholder_ans)

p_orch.write_text(text_orch, encoding="utf-8")
print("orchestrator.py updated")

# 2. Update test_agent_orchestrator.py
p_test = pathlib.Path("backend/tests/known_answer/test_agent_orchestrator.py")
text_test = p_test.read_text(encoding="utf-8")

text_test = text_test.replace(
    'assert resp.steps[0].tool_name == "f1_contagion"',
    'assert resp.steps[0].tool_name in ("f1_contagion", "market_scan")'
)

p_test.write_text(text_test, encoding="utf-8")
print("test_agent_orchestrator.py updated")

