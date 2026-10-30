import pathlib

p_prog = pathlib.Path("PROGRESS.md")
content = p_prog.read_text(encoding="utf-8").replace("\r\n", "\n")

target = """- [ ] **X10.5 Portfolio linkage** from F3 into F1 exposure (optional) and F2 company lists.
- [x] **X10.6 Route** `POST /agent/ask` with rate limits."""

replacement = """- [ ] **X10.5 Portfolio linkage** from F3 into F1 exposure (optional) and F2 company lists.
- [x] **X10.6 Route** `POST /agent/ask` with rate limits.
- [x] **X10.7 Hardened agent tool calling and verification** (items 1-11: model-driven tools market_scan/filings_check/market_news, removed keyword router, provider reply guards, clock system prompt, grounding validation, memory history & persistent attachment piping, verification script, unit tests)."""

assert target in content
content = content.replace(target, replacement)
p_prog.write_text(content, encoding="utf-8")
print("PROGRESS.md updated")

p_task = pathlib.Path("TASK_PROGRESS.md")
p_task.write_text("# Active Task Progress\n\nNo active tasks.\n", encoding="utf-8")
print("TASK_PROGRESS.md reset")

