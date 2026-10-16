# Agent Instructions

Read `PROJECT.md` and `PROGRESS.md` first before beginning any task.

## Core Rules

1. **Real-data policy (PROJECT.md §2.7):** No mocks, fakes, stubs, simulated services, injected faults, synthetic datasets, or recorded fixtures standing in for a live service.
2. **Secrets & storage:** Secrets live in `.env` (gitignored). Raw logs and raw market data live in `private/` and `data/` (gitignored). Only `.env.example` is committed.
3. **No dates anywhere:** Never write dates, timestamps, or release dates in code, comments, documentation, or commit files.
4. **Filesystem paths:** Use Python's `pathlib` module exclusively. Do not use `os.path`.
5. **Dependencies:** Do not add dependencies without recording a rationale in `DECISIONS.md`.
6. **Loud failures:** Surface upstream errors with their real status and message. No silent fallbacks.
7. **India market context:** Instruments, exchanges (NSE/BSE), currency (INR), fiscal calendar (April-March), and regulatory context (SEBI) apply throughout.
8. **Configurability:** Analytical thresholds and window parameters must come from configuration, never hardcoded.
9. **Status markers in PROGRESS.md:**
   - `[ ]` todo
   - `[~]` in progress
   - `[x]` done (tick only after verification)
   - `[!]` blocked
10. **Secret length for redaction:** Secrets must be at least 6 characters or they are not redacted in logs.
11. **TASK_PROGRESS.md lifecycle:** At the start of a task, start a fresh TASK_PROGRESS.md with only that task's steps; when the task finishes, its ticks go to PROGRESS.md and the file is reset. Never put completed history in TASK_PROGRESS.md.
