# Agent Instructions

Read `project_docs/project.md`, `project_docs/tech_stack.md`, and `project_docs/finance_stack.md` before beginning any task.

---

## 1. Core Engineering Rules

1. **Real-Data Policy:** Never use mocks, fakes, stubs, or synthetic fixtures for live external services.
2. **Secrets and Storage:** Store secrets in `.env` (gitignored). Keep raw logs and market data in `private/` and `data/`.
3. **No Dates Anywhere:** Never write dates, timestamps, or release dates in code, comments, or documentation.
4. **Filesystem Paths:** Use Python's `pathlib` module exclusively. Do not use `os.path`.
5. **Dependencies:** Do not add dependencies without recording a rationale in `DECISIONS.md`.
6. **Loud Failures:** Surface upstream errors with their real status and message. Never write silent fallbacks.
7. **India Market Context:** Instruments, exchanges (NSE/BSE), currency (INR), fiscal calendar, and SEBI apply throughout.
8. **Configurability:** Analytical thresholds and window parameters must come from configuration files, never hardcoded.
9. **Status Markers in PROGRESS.md:**
   - `[ ]` todo
   - `[~]` in progress
   - `[x]` done (tick only after verification)
   - `[!]` blocked
10. **Secret Redaction:** Redact any secret of 6 or more characters in logs.
11. **TASK_PROGRESS.md Lifecycle:** Start a fresh `TASK_PROGRESS.md` containing only active task steps. Transfer completed ticks to `PROGRESS.md` when finished. Never store completed history in `TASK_PROGRESS.md`.
12. **Provisional Finance Values:** Financial values operate as provisional baselines without human financial advisor review.

---

## 2. Glossary

- **Loud Failure:** Raising an immediate exception that reports original upstream error status and message.
- **Provisional:** Working value adopted in code and configuration without human financial advisor review.
- **Real-Data Policy:** Architectural rule requiring live APIs or real recorded exchange datasets instead of synthetic stubs.
- **SEBI:** Securities and Exchange Board of India.
