from pathlib import Path

p = Path("backend/app/agent/orchestrator.py")
t = p.read_text(encoding="utf-8").replace("\r\n", "\n")

old = """        model_tier=canonical_tier,
        is_placeholder=False,
    )"""

new = """        model_tier=canonical_tier,
        is_placeholder=bool(getattr(provider, "is_placeholder", False)),
    )"""

if old in t:
    p.write_text(t.replace(old, new, 1), encoding="utf-8", newline="\n")
    print("SUCCESS")
else:
    print("FAILURE")

