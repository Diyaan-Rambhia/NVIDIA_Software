# PROGRESS.md: Task Progress

Companion files: `PROJECT.md` (the SRS; requirement IDs refer to it) and `finance/` (finance detail for the advisor). This file defines the **order** of work. It contains no dates and no deadlines: work proceeds batch by batch, and a batch starts only when the previous gate passes.

## Rules for every agent (read first)

1. **Real-data policy (PROJECT.md §2.7).** No mocks, fakes, stubs, simulated services, injected faults, synthetic datasets, or recorded fixtures standing in for a live service. Anything needing an external service is built and tested against the real one (payments use the gateway's real test mode).
   - *Only exception:* known-answer tests of pure arithmetic on tiny hand-computable inputs.
2. **Secrets and external values live in a gitignored `<repo>/.env`.** Real trade logs and raw exchange data live in the gitignored `<repo>/private/` and `<repo>/data/`. Only `.env.example` (names, no values) is committed. No raw exchange data is committed.
3. **Loud failures.** Surface upstream errors with their real status and message. No silent fallbacks.
4. **Order.** Phase A needs no external service. Phase X holds everything that does. Do not start a Phase X batch before its predecessor's gate, except where "may run in parallel" is stated.
5. **Everything is for India** (NSE/BSE, INR, IST, April-March fiscal year, SEBI regulation). No US filings or US-listed instruments, except global macro drivers.
6. **Parameters are configurable** (PROJECT.md P-8). No inline thresholds or window lengths.
7. **The ops console is never left behind.** Every Phase X batch ends with a task that adds its panel or view to the basic ops frontend.
8. **Status markers:** `[ ]` todo, `[~]` in progress, `[x]` done, `[!]` blocked (add a row to the Blockers log). Mark `[x]` only when the **Accept** check passes, then add a Change log row.
9. **One batch per agent session, one branch per batch.** Merge only when the gate passes.
10. **Contracts are frozen after Gate A0.** Changes need a `DECISIONS.md` entry.
11. **Live tests** are marked `live`, use real keys, draw from `TEST_DAILY_LLM_BUDGET_USD`, and may bypass the cache with `NO_CACHE=1`.
12. **Finance choices are proposals** until the advisor confirms them (`finance/09_open_questions_for_advisor.md`). Implement from `config/` so confirmed changes need no code changes.
13. **Task brief template:** goal, files to touch, interface, constraints, Accept check, "do not touch" list. Log Token Factory, Nemotron and Nebius friction in `FEEDBACK.md` as it happens.

## Order of work

```
A0 → A1 → A2 → A3                       (no external services)
X1 → X2 → X3 → X4                       (foundation: feasibility, Supabase/auth, LLM, ops console)
X4 → X5 (market + F1 stats) and X6 (filings)   [may run in parallel]
X5 → X7 (F1 explanation)      X6 → X8 (F2)
X5 → X9 (F3)  [needs prices; also needs real logs from X1.8]
G-F3 gate sits after X8, before X9 is finalized
X7, X8, X9 → X10 (agent) → X11 (payments) → X12 (precompute, deploy, submit)
```

**G-F3 gate:** after X8 completes, decide whether X9 continues in full or Feature 3 ships using only the real logs already obtained. Record the decision in `DECISIONS.md`.

---

# PHASE A: NO EXTERNAL SERVICES

## A0: Scaffold, policy, config, contracts

- [ ] **A0.1 Repo scaffold** per PROJECT.md §3.4. Add `pyproject.toml`, Makefile (`make test`, `make test-live`, `make run`, `make lint`), LICENSE (decide T15), `.gitignore` excluding `.env`, `.env.*` (except `.env.example`), `private/`, `data/`, caches. Create `DECISIONS.md`, `FEEDBACK.md`, `AGENTS.md`. *Accept:* `make test` green; `git check-ignore .env private/ data/` prints all three.
- [x] **A0.2 Config loader** (FR-CFG-001..006): reads `<repo>/.env`, process env overrides, validates required variables, fails fast naming missing ones, never prints values. *Accept:* with `.env` absent the app exits naming each missing variable; no secret appears in logs. Tested with real temporary env files.
- [x] **A0.3 `.env.example`** with every variable name from PROJECT.md Appendix A and no values.
- [x] **A0.4 Parameter system** (FR-CFG-005..008, P-8): `config/parameters.yaml` with default, min, max, override-allowed per parameter; loader and request-level validation; every result records parameters used. Include every row of PROJECT.md §5.2. *Accept:* an out-of-bounds window is rejected with a clear error; an in-bounds override is applied and recorded.
- [x] **A0.5 Contract schemas** (PROJECT.md §7.3): models without §7.3 field definitions deferred to respective consuming batches per DECISIONS.md D-08; schema exporter script established.
- [x] **A0.6 App shell:** FastAPI app, `/health`, `/ready`, structured logging with request IDs, error envelope (FR-OBS-001..003).
- [x] **A0.7 `AGENTS.md`:** the rules above, style rules, "read PROJECT.md and PROGRESS.md first".

**Gate A0:** clean checkout runs `make test` and `make run`; contracts frozen.

## A1: Entitlement logic (pure rules)

- [x] **A1.1 `config/plans.yaml` and loader** with `retail_free`, `retail_paid`, `institutional_free`, `institutional_paid`, `judge_all`, segments, features, quotas, and provisional monthly price fields (D-09). *Accept:* schema-validated at startup.
- [x] **A1.2 Entitlement decision function** (FR-ENT-002..005): given a profile and a feature, return allowed / limited / upgrade_available (402) / segment_restricted (403) with payloads. *Accept (known-answer):* the full matrix of 5 plans × 3 features gives the expected results; F1 for retail is always 403; F1 for `institutional_free` is 402; F2 for any institutional plan is limited at retail-free quotas, never full.
- [x] **A1.3 Quota arithmetic and reset-time calculation** (FR-QUO-001/002). *Accept:* known-answer tests including the day boundary in UTC.
- [x] **A1.4 `judge_all` rules** (FR-ENT-008, FR-QUO-004): not purchasable; never produced by a payment path. *Accept:* a test proves no payment-derived plan equals `judge_all`.

**Gate A1:** matrix test suite green.

## A2: Pure algorithm library (known-answer checks only)

- [x] **A2.1 Returns and Indian-calendar alignment utilities.**
- [x] **A2.2 Covariance and correlation estimators** (rolling, EWMA, Ledoit-Wolf via scikit-learn), with all windows taken from parameters. *Accept:* no lookahead by construction; parameter bounds enforced.
- [x] **A2.3 Forbes-Rigobon adjustment** (§5.3). *Accept:* hand-computed example; identity when δ ≤ 0.
- [x] **A2.4 Spearman wrapper.**
- [x] **A2.5 Absorption ratio and standardized shift** (§5.5). *Accept:* identity gives k/N; rank-one gives 1.
- [x] **A2.6 Moving-block bootstrap** with recorded seed. *Accept:* same seed reproduces the same output. (Statistical behavior verified on real data in X5.)
- [x] **A2.7 XIRR** with Brent solver and an explicit "no root" result. *Accept:* −100 then +110 a year later gives 10%.
- [x] **A2.8 Process-metric formulas:** HHI, turnover, disposition effect (PGR/PLR), max drawdown. *Accept:* hand-computed examples.
- [x] **A2.9 Institutional metric formulas:** beta, alpha, tracking error, information ratio (definitions pending advisor; implement from `config`). *Accept:* hand-computed examples.
- [x] **A2.10 Derived filing metrics:** YoY, QoQ, margins, DSO, OCF conversion, Q4 derivation from cumulative figures. *Accept:* arithmetic known-answers.
- [x] **A2.11 Fiscal-period utilities:** parse "Q1 FY27"-style labels to period-end dates and back. *Accept:* known-answer table.
- [x] **A2.12 Text utilities:** chunker with stable offsets; verbatim-quote check. *Accept:* offset round-trip on literal strings.
- [x] **A2.13 Rule engine** for R1-R7 reading `config/lexicon.yaml` and `config/thresholds.yaml`. *Accept:* rule evaluations on hand-written metric/claim pairs.

**Gate A2:** library lint- and type-clean; no network access anywhere in the batch.

## A3: Infrastructure logic (no external services)

- [x] **A3.1 Response-cache key and on-disk cache,** bypassable with `NO_CACHE`.
- [x] **A3.2 Budget guard logic** (FR-LLM-009): pure function over a spend total and a cap. *Accept:* known-answer.
- [x] **A3.3 Cost-report calculations** (FR-CAC-004) from ledger-shaped rows. *Accept:* known-answer.
- [x] **A3.4 Dockerfile and startup check;** the image never contains secrets.

**Gate A3 (end of Phase A):** `make test` green; nothing in the repo contacts an external service.

---

# PHASE X: REAL SERVICES

## X1: Accounts, keys, feasibility  *(human-led)*

- [ ] **X1.1 Register for Devpost credits and the Builders Program.**
- [ ] **X1.2 Create Supabase project,** Token Factory key, Tavily key, FRED key, Google OAuth client, payment-gateway test credentials; fill `<repo>/.env` from `.env.example`.
- [ ] **X1.3 Connectivity script** `scripts/check_services.py`: one real minimal call to every service in PROJECT.md §6.5 that has an API, printing pass/fail and real status codes. *Accept:* all required services pass; failures go to `DECISIONS.md` and `FEEDBACK.md`.
- [x] **X1.4 Indian price-data feasibility:** for each candidate source (yfinance NSE/BSE tickers, index-provider downloads, Alpha Vantage, Twelve Data, exchange archives), pull real daily history for the candidate universe and record coverage, history length, adjusted/unadjusted behavior, corporate-action handling, rate limits and terms. Choose sources. *Accept:* a decision table in `DECISIONS.md` (T4).
- [x] **X1.5 Filings feasibility:** retrieve real Ind AS financial-results XBRL for a few companies from NSE or BSE; locate real earnings-call transcripts, press releases and presentations for the same fiscal periods; record access method, throttling needed, format and terms. Choose the method. *Accept:* decision table (T12).
- [x] **X1.6 Macro feasibility:** RBI/FBIL series, FRED series IDs, FPI flow data: confirm access and IDs.
- [x] **X1.7 Confirm Supabase-only datastore** (T2).
- [ ] **X1.8 Obtain real trade logs** with written consent and identifiers removed, into `private/logs/`. Record which may appear publicly. (Human task.)
- [ ] **X1.9 Engage the finance advisor:** send `finance/` and collect answers to `finance/09_open_questions_for_advisor.md`; record answers in `DECISIONS.md` and update `config/`.

**Gate X1:** every service needed by later batches is reachable or has a recorded alternative; data-source decisions are made.

## X2: Supabase, auth, accounts

- [x] **X2.1 Schema and migrations** for the tables in PROJECT.md §7.1 on the real Supabase project; row-level security policies. *Accept:* a second real test user cannot read the first user's rows.
- [x] **X2.2 JWT verification** (FR-AUTH-004) and profile loading. *Accept (live):* a real token passes; an expired or tampered token is rejected.

- [ ] **X2.3 Sign-up with segment, email verification, Google OAuth, Terms-of-Service acceptance record** (FR-AUTH-001..003, 006, 010). *Accept (live):* a real verification email is received; Google login works; an unverified account is blocked from features.
- [ ] **X2.4 Origin validation and auth rate limits** (FR-AUTH-007/008).
- [ ] **X2.5 Wire A1 entitlement logic to real profiles** and usage counters; `require_feature` dependency; `GET /api/entitlements`. *Accept (live):* the 5 × 3 matrix passes with real accounts, with correct 402 and 403 payloads.
- [ ] **X2.6 Seed command** (FR-QUO-005): `judge`, `demo-retail`, `demo-institutional`. *Accept:* idempotent; passwords never printed.
- [ ] **X2.7 Admin CLI** (plan assignment, disable, usage) and the `events` writer (FR-OBS-004).
- [ ] **X2.8 Decide email sender adequacy** (T: built-in limits versus custom SMTP) and record.

**Gate X2:** all four plans exercised with real accounts.

## X3: LLM gateway on Token Factory

- [ ] **X3.1 Client wrapper** (FR-LLM-001/003). *Accept (live):* a real call succeeds; a call with an invalid key surfaces the real 401.
- [ ] **X3.2 Model registry** (FR-LLM-002) from the real model list. *Accept (live):* all three aliases resolve.
- [ ] **X3.3 Structured-output helper** (FR-LLM-004). *Accept (live):* real calls on each model return schema-valid output; retry-with-error exercised only by real invalid responses.
- [ ] **X3.4 Tool-call loop** (FR-LLM-005). *Accept (live):* a real round trip on `mid` calls a real tool.
- [ ] **X3.5 Ledger and budget guard on Supabase** with real usage fields (FR-LLM-006/009); cache (FR-LLM-007).
- [ ] **X3.6 Live spike report** `scripts/spike_llm.py`: for Nano, Super and Ultra, hello, JSON-schema, tool-call and reasoning-content format. Save the table.
- [ ] **X3.7 Decisions in `DECISIONS.md`:** real model IDs, native or JSON-based tool selection, reasoning handling, accepted context size, rate limits (T3).

**Gate X3:** if tool calling fails on a model, the agent design decision is recorded before continuing.

## X4: Basic ops frontend (foundation)

- [x] **X4.1 Scaffold `frontend/`** console, sign-in with Supabase Auth, admin-only gate (FR-UI-001).
- [x] **X4.2 Ops endpoints** (`/ops/status`, `/ops/config`, `/ops/activity/events`, `/ops/activity/llm`), read-only, admin-gated.
- [x] **X4.3 Status panel:** liveness, readiness, per-service pass/fail with real errors (FR-UI-002).
- [x] **X4.4 Configuration panel:** `.env` variable presence by name only, active parameters (FR-UI-003).
- [x] **X4.5 Activity feed** from `events` and LLM ledger (FR-UI-005/006).
- [ ] **X4.6 Accounts and entitlements panel** (FR-UI-009).
- [ ] **X4.7 Parameter-form component** reused by every feature runner (windows etc.).

**Gate X4:** an admin can sign in and watch real LLM calls and events appear live.

## X5: Indian market data and Feature 1 statistics

- [ ] **X5.1 Pull script** (FR-MKT-002/003) for the sources chosen in X1.4 and X1.6 into Supabase with manifests. *Accept:* re-runnable; manifest has source, time, range, row counts; each pull logs events.
- [ ] **X5.2 `PriceStore` loader and validator** (FR-MKT-004/005) on real data, tracking price type (price vs TRI, adjusted vs not). *Accept:* real anomalies reported, not repaired; corporate-action artifacts caught.
- [ ] **X5.3 Finalize universe and `config/episodes.yaml`** with the advisor before tuning (T4, Appendix D). Do not adjust windows afterward. Include negative controls.
- [ ] **X5.4 Reference checks on real data (V2)** against an independent implementation.
- [ ] **X5.5 No-lookahead test (V4)** on real data.
- [ ] **X5.6 Full F1 statistics pipeline** (FR-F1-001..009) with configurable windows over the real sample. *Accept:* changing `W` changes results consistently and is recorded in the output.
- [ ] **X5.7 Bootstrap behavior check on real data;** pick the multiple-testing control (T10).
- [ ] **X5.8 Regime flag and calibration** (§5.7): tune on some episodes, evaluate on held-out ones, report flag frequency and negative-control results (FR-F1-014).
- [ ] **X5.9 Replay report (V5).** *Human review with the advisor:* do flags line up with episodes, are controls quiet, is there lead time? Record the verdict and the final wording ("early warning" vs "regime detection").
- [ ] **X5.10 Cluster and factor attribution** producing the real `EvidencePack` (FR-F1-009).
- [ ] **X5.11 Routes:** `POST /f1/scan` (with parameter overrides), `GET /f1/episodes`, `GET /f1/episodes/{id}`, gated by `contagion`.
- [ ] **X5.12 Ops panels:** data panel (FR-UI-004) and the F1 runner with parameter form, heatmap, AR timeline and flags table (FR-UI-007).

## X6: Indian filings data  *(may run in parallel with X5)*

- [ ] **X6.1 Exchange filings client** (FR-FIL-007) with identifying user agent, conservative throttle and disk cache. *Accept (live):* a real burst never exceeds the chosen limit; a real request for a nonexistent filing surfaces the real error.
- [ ] **X6.2 Results XBRL retrieval** (FR-FIL-001/002) for the chosen companies (T6).
- [ ] **X6.3 XBRL parser and normalizer** (FR-FIL-003, §7.2), standalone and consolidated kept separate. *Accept:* hand-checked against the published results for at least 3 companies.
- [ ] **X6.4 Press release, presentation and transcript retrieval** (FR-FIL-004), PDF-to-text with offsets and quality recorded (FR-FIL-005).
- [ ] **X6.5 Fiscal-period mapping** across all documents (FR-FIL-006).
- [ ] **X6.6 Human task: hand-label** 15-20 company-periods into `data/labels/` (Appendix C). Agents must not label.
- [ ] **X6.7 Ops panel:** filings and documents status in the data panel.

## X7: Feature 1 explanation layer

- [ ] **X7.1 Tavily client** (FR-F1-010) with per-run credit cap and cache. *Accept (live):* a real search returns real results.
- [ ] **X7.2 News-query builder** from the evidence pack (India-aware: RBI, FPI, rupee, crude, global events).
- [ ] **X7.3 Hypothesis generation** on `deep` (PROJECT.md §9) using the mechanism taxonomy in `finance/03`.
- [ ] **X7.4 Validators** (FR-F1-012). *Accept (live):* real model output is validated; real rejections are logged and examined.
- [ ] **X7.5 Run on every episode and control** with real Ultra and real Tavily. *Accept:* every hypothesis cites only evidence IDs and URLs from its inputs.
- [ ] **X7.6 Route** `POST /f1/explain`; ops panel shows explanations with citations.

## X8: Feature 2 pipeline

- [ ] **X8.1 Chunking real documents** with offsets.
- [ ] **X8.2 Claim extraction** on `fast` including `basis` (FR-F2-002/003). *Accept (live):* every kept quote is an exact substring at its offsets.
- [ ] **X8.3 Matching and rules** (FR-F2-004) on real claims and metrics, standalone/consolidated aligned.
- [ ] **X8.4 Adjusted-figure guard** (FR-F2-005) using Indian terminology.
- [ ] **X8.5 Adjudicator** on `deep` (FR-F2-006).
- [ ] **X8.6 Verifier** (FR-F2-007). *Accept:* every flag from real runs passes it; real rejections examined.
- [ ] **X8.7 Precision filter and ranking** (FR-F2-008/009).
- [ ] **X8.8 Evaluation** against hand labels (V6); record precision and recall in `DECISIONS.md`. Proposed target precision ≥ 0.80.
- [ ] **X8.9 Tuning** of lexicon, thresholds and guard from real false positives, with advisor review of rule definitions.
- [ ] **X8.10 Route** `POST /f2/analyze` (retail plans, free quota) and `GET /f2/companies`; ops panel F2 runner.

**→ G-F3 gate here.**

## X9: Feature 3 on real logs (both scopes)

- [x] **X9.1 Parser and `fast` column mapper with confirmation** (FR-F3-001/002) on real broker exports.
- [ ] **X9.2 Corporate-action adjustment** (FR-F3-003) from real action records.
- [x] **X9.3 Position ledger and XIRR on real logs** (FR-F3-004). *Accept:* XIRR matches an independent reference on the real log.
- [x] **X9.4 Benchmark replay** against real index and total-return series and an Indian short-term rate (FR-F3-005).
- [x] **X9.5 Process metrics** (FR-F3-006).
- [x] **X9.6 Institutional scope metrics** (FR-F3-007) per advisor-confirmed definitions, plus limits from `plans.yaml`.
- [ ] **X9.7 Review generation** on `deep` (FR-F3-008/010) with validators: no buy/sell/hold or target language, cites only provided metrics, disclaimer present.
- [x] **X9.8 Consent-aware retention** (FR-F3-009) and `Portfolio` output (FR-F3-012).
- [x] **X9.9 Route** `POST /f3/review` with segment-aware scope and quotas; ops panel F3 runner.

## X10: Agent orchestrator

- [x] **X10.1 Tool registry** (FR-AGT-001/002) over the real feature code; tools hidden from segments that cannot use them.
- [x] **X10.2 Entitlement-aware execution** (FR-ENT-006). *Accept (live):* a `demo-retail` agent session cannot reach F1; a `demo-institutional` session reaches F2 only within retail-free quotas.
- [x] **X10.3 Orchestrator loop** on `mid` (FR-AGT-003) using the mechanism chosen in X3.7, with refusal for advice-seeking questions.
- [ ] **X10.4 SSE step streaming** (FR-AGT-004) and ops-console agent trace (FR-UI-008).
- [ ] **X10.5 Portfolio linkage** from F3 into F1 exposure (optional) and F2 company lists.
- [x] **X10.6 Route** `POST /agent/ask` with rate limits.

## X11: Payments

- [ ] **X11.1 Gateway integration** (FR-PAY-001/002) in test mode: plan listing by segment, monthly order or subscription creation, and institutional purchase blocked until admin approval of the registration number (FR-AUTH-006).
- [ ] **X11.2 Webhook endpoint** (FR-PAY-003/004) with signature verification and idempotency. *Accept (live, test mode):* a real successful payment upgrades the plan; a failed payment does not; a replayed webhook changes nothing; a bad signature is rejected.
- [ ] **X11.3 Payment records** (FR-PAY-005) and segment-restricted purchasing (FR-PAY-006).
- [ ] **X11.4 Lapse and downgrade handling** (FR-PAY-007, D-08) and monthly-only billing (FR-PAY-011).
- [ ] **X11.5 GST and invoice handling** per advisor (FR-PAY-008).
- [ ] **X11.6 Confirm judges and demo accounts never need payment** (FR-PAY-010).
- [ ] **X11.7 Ops panel:** recent payment events (no card data).

## X12: Precompute, budget, deploy, submit

- [ ] **X12.1 Precompute job** (FR-CAC-001) for every demo path, including F1 episodes, F2 company-periods and consented F3 logs. *Accept:* demo endpoints answer in under 1 s, labeled `cached` with `computed_at`.
- [ ] **X12.2 Cost report on real usage** (FR-CAC-004). *Accept:* projected spend through the end of judging fits remaining credits; per-account limits tuned.
- [ ] **X12.3 Entitlement matrix and payments tests (V7, V8)** against the deployed app with real accounts.
- [ ] **X12.4 Deploy** the Docker image to the chosen host (T14) with secrets injected as environment variables; keep-alive or paid plan for Supabase and the host so nothing sleeps during judging.
- [ ] **X12.5 Final README:** setup (including creating `.env` from `.env.example`), Nemotron usage per model, where Token Factory and Tavily are called, license badge. No credentials.
- [ ] **X12.6 Judging credentials note** for the Devpost testing-instructions field, kept out of the repo; plan to rotate or disable after judging.
- [ ] **X12.7 Feedback section** compiled from `FEEDBACK.md`.
- [ ] **X12.8 End-to-end acceptance (V10)** by a person using `demo-retail`, `demo-institutional` and `judge`.

**Final gate:** backend deployed, stable, and the ops console shows every service green.

---

## Human-only checkpoints

X1 (accounts, keys, feasibility decisions, real logs, advisor engagement), X5.3 and X5.9 (universe, episodes and replay review with the advisor), X6.6 (hand labels), the G-F3 gate, X8.9 (rule review), X12.8 (acceptance).

## Blockers log

| # | Task | Blocker | Owner | Resolution |
|---|---|---|---|---|
| | | | | |

## Change log

| # | Task(s) | Branch | Notes |
|---|---|---|---|
| 1 | n/a | n/a | Docs created. |
| 2 | n/a | n/a | Restructured: India focus; retail/institutional segments; Supabase; auth, payments and ops frontend in scope; dates removed; `finance/` folder added. |
| 3 | n/a | n/a | Owner decisions recorded in `finance/11_decisions_log.md`: monthly billing, institutional paid-only with retail-level free access, SEBI-registration verification, Terms of Service and liability framework (`finance/12`), `institutional_free` plan, rule R0, Benjamini-Hochberg control. |
| 4 | A0.3 | n/a | Environment variable template .env.example verified against Appendix A. |
| 5 | A0.2 | n/a | Environment registry, settings loader, validation by enabled groups, and secret redaction filter implemented and tested with real temp files. |
| 6 | A0.2 | n/a | Audit fixes: traceback and argument redaction, strict runtime.yaml validation without fallback, and core defaults not required when group enabled. |
| 7 | A1 | n/a | Pure entitlement and quota decision logic implemented, plans.yaml aligned to PROJECT.md §4.3 with daily quotas and configurable UTC reset rule, known-answer test matrix green. |
| 8 | A2.1, A2.11 | n/a | Pure daily return calculation, multi-series Indian trading calendar alignment with gap rejection, and canonical fiscal-period parsing and boundary mapping implemented. |
| 9 | X9 (partial, no LLM), Frontend | n/a | Contracts defined (TradeLog, Portfolio, DecisionReview, ColumnMapping), F3 parsing/XIRR/replay pipeline built and tested, plain HTML/CSS/JS frontend delivered in frontend/app/. |
| 10 | X10.6, X12.5 | n/a | Generated README environment variable reference grouped by runtime group with zero-drift test, and guaranteed 503 ErrorEnvelope on /agent/ask and /llm/runtime_call when provider is unconfigured in production. |
| 11 | Frontend Web | n/a | Built Next.js (TypeScript, App Router) frontend in frontend/web/ covering all features, in-memory auth context, proxy rewrites, comprehensive render and audit tests, and Next.js production build. |
| 12 | Frontend Web (/agent & Tavily) | n/a | Converted /agent into focused chat with flat 2px radius blocks, honest cancel, expandable steps, and closed model call; delivered shared responsive TavilyRail on /contagion with real states and https validation. |
| 13 | Frontend Web Refinements | n/a | Repositioned /agent chips to compact clickable chips above input hidden on thread messages, positioned Tavily full-width between sections on /contagion, implemented /filings dynamic search and quarter selector with live lookup gap notice (D-66), and configured /admin group-aware config states with SMTP hidden. |
| 14 | Stage 1 & Stage 2 | n/a | Delivered model tiering (fast, balanced, deep), model & search verification scripts, Agent model tier & attachment reference, plain prose output validator, auth refresh endpoint, safe file extraction, live yfinance caching, live NSE equity & XBRL lookup with annual-only rules (R5, R6, DSO), live Tavily search, and canonical fiscal period normalization. |
| 15 | Frontend Web Session & Origin Hardening | n/a | Resolved sign-in flow by guarding client-side auth redirects with sessionChecked, validating token payload fields, enforcing strict Origin vs Host check (with loopback config list), making cookie Secure flag adapt to request https or production, and surfacing explicit status and error codes. |
| 16 | Frontend Hardening & Feature Polish | n/a | Completed Stage 2 items A-J and Stage 3 verification: eliminated legacy unrequested components and alias dropdowns, unified /agent single chat with model tier picker and markdown code folding, unified /contagion context and hypotheses, removed payments and unified 402 messaging, sanitized third-party vendor strings, verified clean build, dev server routing, and full test suites. |
| 17 | Mock/Demo Elimination & Production Hardening | n/a | Removed default price fallback (503 price_not_set), eliminated legacy frontend/app and demo endpoints (D-82), applied provider injection across modules, enforced 502 on LLM upstream errors, added live /f1/scan and /f2/companies with NSE cache, updated entitlements test for live endpoints, set finite judge quotas, and verified full test suite. |
| 18 | Filings Search, Nifty 50, and Calendar Picker | n/a | Added live Nifty 50 top group (/f2/top50) from NSE archives, server-side equity search (/f2/search), calendar-style fiscal quarter picker from FY01 with month labels, and missing-quarter notices with machine-readable disclaimer (D-83). |
| 19 | Routing Without Prices & Filings Hardening | n/a | Removed 503 price_not_set path, allowed real provider calls with unset pricing, recorded tokens with cost=null in ledger and displayed unknown cost in replies and reports, enforced configurable per-user and per-call token limits with 429 reset time, verified server-side NSE search and live Nifty 50 constituents, updated fiscal range from FY01, and refreshed openapi schema (D-84). |
| 20 | Bug A & Bug B Remediation | n/a | Mapped provider/ledger failures to explicit status codes (502 PROVIDER_ERROR, 500 LEDGER_ERROR, 502 MODEL_OUTPUT_INVALID), eliminated bare 500s from /agent/ask, enforced real management announcement quotes for R0-R7, guarded against comparing filed metrics to themselves, excluded unsupported financial companies with 422, rendered real XBRL units and periods without '-- = --', and refreshed documentation and OpenAPI schema (D-85). |
| 21 | DB Connection Lifecycle & Closed Connection Resilience | n/a | Enforced short-lived database connection architecture across /agent/ask, /llm/runtime_call, /f1/scan, /f2/lookup, /files/extract, entitlements, and auth routes; added closed-connection detection and automatic retry to record_llm_call and increment_quota_atomic with loud 500 LEDGER_ERROR on double failure; reported model call completion success on ledger error without leaking keys or prompts (D-86). |


