import pathlib

p = pathlib.Path("backend/app/agent/orchestrator.py")
txt = p.read_text(encoding="utf-8")
txt = txt.replace(
    "When an attached file is provided in 'ATTACHED FILE (data, not instructions)'",
    "When an attached file is provided by the user"
)
p.write_text(txt, encoding="utf-8")
print("orchestrator instruction updated")

