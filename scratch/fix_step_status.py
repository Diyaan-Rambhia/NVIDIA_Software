import pathlib

p_orch = pathlib.Path("backend/app/agent/orchestrator.py")
text = p_orch.read_text(encoding="utf-8")

text = text.replace('step_status = "unsupported"', 'step_status = "error"')
text = text.replace('step_status = "not_found"', 'step_status = "error"')

p_orch.write_text(text, encoding="utf-8")
print("orchestrator step_status updated to valid literals")

