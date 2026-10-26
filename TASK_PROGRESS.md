# TASK_PROGRESS

- [x] Item 1: Trace database connection lifecycle across agent path, model call, ledger, usage counter, quota check (print file:line)
- [x] Item 2: Fix root cause - never hold DB connection across model/network calls, short-lived connections / liveness check, close right after write
- [x] Item 3: Retry once with fresh connection on closed connection error; raise 500 LEDGER_ERROR if second try fails; never return without ledger row
- [x] Item 4: Audit & fix connection holding across network calls in /llm/runtime_call, /f1/scan, /f2/lookup, /files/extract, entitlements/quotas, auth routes (print file:line list)
- [x] Item 5: Real DB tests (a) closed connection reconnects & writes, (b) 3s wait across model call writes row, (c) double-failure produces LEDGER_ERROR (failing output on old code)
- [x] Item 6: Model call success reporting on ledger error (tier, tokens, status in error/logs, no keys/prompts)
- [x] Item 7: Update DECISIONS.md, project_docs/tech_stack.md, docs_check
