# PROJECT.md: Project Description and Software Requirements Specification (SRS)

| Field | Value |
|---|---|
| Project | India-focused financial intelligence platform for retail and institutional investors (working title TBD; code slug `fininsight`) |
| Document version | 0.4 (draft) |
| Status | Backend specification, plus a basic always-on ops frontend. The final production frontend is specified later. |
| Companion files | `PROGRESS.md` (task order, status, gates) and `finance/` (all finance detail for the advisor; owner decisions are recorded in `finance/11_decisions_log.md`; liability and terms framework in `finance/12_terms_and_liability_framework.md`) |
| Audience | The team, a finance advisor, and the coding agents that implement the backend |

**Requirement language.** "Shall" is mandatory. "Should" is strongly preferred. "May" is optional. IDs such as `FR-F1-004` trace to tasks in `PROGRESS.md`. This document contains no schedule and no dates other than historical market episodes; order of work is defined only by the sequence in `PROGRESS.md`.

**Finance note.** The team is strong in software and not in finance. Every finance-specific choice (universe, benchmarks, thresholds, rule definitions, regulatory framing) is a **proposal** until the finance advisor confirms it. These items are tracked in `finance/09_open_questions_for_advisor.md` and `finance/10_parameters_register.md`.

---

## 1. Introduction

### 1.1 Purpose

This document states what the system is, who it serves, and exactly what it must do. It is the single source of truth for the backend. Where a value is not yet known it is marked **TBD** and listed in Section 14.

### 1.2 Problem statement

Indian market participants face three information gaps.

1. **Systemic risk is invisible until it is too late (institutions).** Portfolio construction assumes historical correlations between asset classes stay stable. When normally weakly related assets (Indian equities, government bonds, gold, the rupee, crude-linked assets) start moving together, diversification fails when it is needed. Institutions (asset managers, PMS and AIF managers, insurers, treasury desks, family offices) need an early, defensible signal and a plausible, evidenced explanation of *why* the linkage changed.
2. **Company disclosures are hard to cross-check (retail).** Listed Indian companies publish numeric results (filed in XBRL on NSE and BSE) and separate management commentary (press releases, investor presentations, earnings-call recordings and transcripts). A phrase like "strong growth" next to revenue that grew 2% is easy to miss. Retail investors rarely cross-reference these by hand.
3. **Investors rarely get an honest review of their own decisions (both).** Outcomes are mistaken for decision quality. "What else could I have done with this money?" is rarely answered rigorously, and luck and skill look identical in hindsight.

### 1.3 Product summary

The system is **semi-agentic**. Language and judgment tasks (extracting claims, adjudicating contradictions, writing hypotheses, reviewing decisions, orchestrating tools) use NVIDIA Nemotron models served through Nebius Token Factory. Statistics, arithmetic, matching rules, verification and access control are deterministic code. The LLM never produces a number that did not come from deterministic code.

| Feature | Audience | Summary |
|---|---|---|
| **F1 Contagion Detector** | **Institutional only** | Detects when normally weakly related Indian-market assets start moving together, tests whether the shift is real or merely volatility-driven, and explains the plausible mechanism with cited evidence. Parameters (windows, thresholds, universe) are configurable. |
| **F2 Filing Consistency Checker** | **Retail** (institutions may use it only at retail free-tier limits) | Cross-checks a listed company's numeric results against management's language for the same fiscal period, and flags verifiable contradictions. Explicitly not sentiment analysis. |
| **F3 Investment Log Advisor** | **Both** | Reviews a real trade log or portfolio against same-cash-flow alternatives and process metrics. The retail scope focuses on personal decision quality. The institutional scope adds benchmark-relative statistics and higher volume limits. |

**Access is segment-based, not just price-based.** A retail account cannot buy F1. Institutional accounts start with the same free tier as retail (F2 and F3 at retail-free limits); F1 and the institutional scope of F3 require the paid institutional plan, which has no free trial. An institution cannot buy full F2. Billing is monthly. Institutional pricing is higher (amounts provisional, see `finance/08_pricing_and_tiers.md`).

### 1.4 Scope

**In scope:**
- Configuration and secrets handling (`.env`).
- Accounts: sign-up, login, email verification, Google OAuth, sessions.
- Entitlements and quotas by segment and plan.
- Payments through a payment gateway: checkout, subscription, webhooks and plan changes (Indian gateway; sandbox/test mode during development).
- Supabase as the datastore (Postgres, Auth, optional vector search).
- An LLM gateway to Nebius Token Factory.
- Indian market, macro and filings data ingestion.
- The three feature pipelines and the agent orchestrator.
- Caching, precomputation, cost tracking.
- A **basic ops frontend that exists at all times** (Section 4.13), kept simple until the final frontend is built.
- Deployment packaging, and test and evaluation harnesses.

**Deferred (planned for later, not in the current build):** real-time and intraday market data.

**Out of scope:** trade execution; brokerage integrations; mobile apps; the final production frontend (a basic ops frontend is in scope); and any form of personalized investment advice.

### 1.5 Definitions and acronyms

| Term | Meaning |
|---|---|
| NSE / BSE | National Stock Exchange of India / BSE Limited (formerly Bombay Stock Exchange). |
| SEBI | Securities and Exchange Board of India, the capital-markets regulator. |
| LODR | SEBI (Listing Obligations and Disclosure Requirements) Regulations, 2015. |
| Ind AS | Indian Accounting Standards (converged with IFRS), used by most listed companies. |
| FY | Indian fiscal year, April to March. FY27 = April 2026 to March 2027. Q1 = April-June. |
| XBRL | eXtensible Business Reporting Language: structured tags in filings. |
| G-sec | Government of India securities. |
| FPI / DII | Foreign Portfolio Investors / Domestic Institutional Investors. |
| INR, USD/INR | Indian rupee, and its exchange rate to the US dollar. |
| Nifty 50, Sensex | Headline NSE and BSE large-cap indices. TRI = total return index (includes dividends). |
| RBI, MPC, repo | Reserve Bank of India, its Monetary Policy Committee, and its policy rate. |
| DPDP Act | Digital Personal Data Protection Act, 2023 (India). |
| GST | Goods and Services Tax. |
| Absorption ratio (AR) | Share of return variance explained by the first k principal components. High means tight coupling. |
| Forbes-Rigobon (FR) adjustment | Correction for correlation inflated by higher volatility. |
| XIRR | IRR for cash flows on irregular dates (money-weighted return). |
| Token Factory / Nemotron | Nebius's hosted inference API / NVIDIA's open model family (Nano, Super, Ultra). |
| Tavily | Web-search API for agents. |
| Supabase | Hosted Postgres with Auth, Storage and pgvector. |
| Evidence pack | The ID-labeled set of computed facts the LLM may cite. |
| Episode | A named historical stress period used for replay and validation. |
| Real-data policy | The rule that no mocks, fakes, stubs or synthetic data are used (Section 2.7). |

### 1.6 References

1. Nebius x NVIDIA Global AI Hackathon, Devpost page and Official Rules.
2. Kritzman, Li, Page, Rigobon, "Principal Components as a Measure of Systemic Risk".
3. Forbes and Rigobon, "No Contagion, Only Interdependence".
4. SEBI LODR Regulations, 2015, including Regulation 33 (financial results) and Regulation 46(2)(oa) (earnings-call recordings and transcripts).
5. SEBI (Investment Advisers) Regulations, 2013 and SEBI (Research Analysts) Regulations, 2014.
6. NSE and BSE XBRL filing information pages.
7. Nebius Token Factory documentation; Supabase documentation; chosen payment gateway documentation (TBD); Tavily documentation.
8. Odean (1998), "Are Investors Reluctant to Realize Their Losses?".

---

## 2. Overall description

### 2.1 Product perspective

```
        Browser (ops console now, final frontend later)
                      | HTTPS (JSON, SSE)
        +-------------v----------------------------------------+
        | FastAPI backend                                       |
        |  auth verify (Supabase JWT) | entitlements | quotas   |
        |  payments | agent orchestrator (Nemotron Super)       |
        |  F1 engine | F2 pipeline | F3 engine | ops endpoints  |
        |  LLM gateway | data services | cache | ledger         |
        +--+-------+--------+---------+---------+---------+----+
           |       |        |         |         |         |
     Nebius      Tavily   Supabase   NSE/BSE   Price &   Payment
     Token                (Postgres  filings   macro     gateway
     Factory              + Auth)    + calls   sources
```

### 2.2 Product functions (summary)

1. Sign up, verify email, log in (email/password or Google), belong to a segment and plan.
2. Purchase or change a plan through the payment gateway (F1 for institutional; F2 for retail; F3 for both).
3. Scan an Indian-market universe for correlation regime shifts with volatility-bias correction, significance testing and an absorption-ratio signal, with user-configurable parameters (F1).
4. Explain a flagged shift as 2-4 ranked, cited, hedged mechanism hypotheses (F1).
5. Compare a company's reported results against management language for the same fiscal period and flag verifiable contradictions (F2).
6. Review a real trade log against same-cash-flow alternatives and process metrics (F3).
7. Answer natural-language questions by orchestrating tools in an agent loop, streaming each step (Agent).
8. Serve precomputed, provenance-stamped results for the demo path (Cache).
9. Track every LLM call's cost and enforce a budget (Ledger).
10. Show what the system is doing and what changed, at all times, in a basic ops frontend (Ops).

### 2.3 User classes

| Class | Segment | Description | Access |
|---|---|---|---|
| Retail free | retail | Individual investor, no payment | F2 limited, F3 (retail scope) limited; F1 not available |
| Retail paid | retail | Individual investor on a paid plan | F2 full, F3 (retail scope) full; F1 not available |
| Institutional free | institutional | Any verified or unverified institutional-segment account without a paid plan | Retail-level free tier: F2 limited, F3 (retail scope) limited; F1 locked with upgrade offered |
| Institutional paid | institutional | Asset manager, PMS/AIF, insurer, treasury, family office, FPI, or similar; paid only, no free trial | F1 full, F3 (institutional scope) full with heavier quotas; F2 only at retail-free limits |
| Judge | internal | Hackathon evaluator; credentials only in the Devpost testing-instructions field | Plan `judge_all`: every feature and both F3 scopes, no payment, no restriction |
| Demo operator | internal | Team member recording the video | `demo-retail` and `demo-institutional` accounts, plus `judge_all` |
| Administrator | internal | Team member | Admin role: ops console, CLI tools for plan assignment, account disable and usage |

Institutional paid status requires verification: the institution supplies its SEBI registration number (or, if regulated by another body such as IRDAI or RBI, that regulator's registration ID) and an administrator approves it manually (decision D-03 in `finance/11_decisions_log.md`).

### 2.4 Operating environment

- Python 3.11 or newer, FastAPI, Uvicorn. One Docker image.
- Datastore: Supabase (Postgres, Auth). Large artifacts and caches on local disk or Supabase Storage.
- Hosting: TBD. It must stay reachable through the end of the judging period.
- Developer machines: Linux, macOS or Windows (`pathlib` for all paths).
- All timestamps are stored in UTC and shown in IST (Asia/Kolkata). Market calendars, currency (INR) and fiscal periods (April-March) are Indian by default.

### 2.5 Design and implementation constraints

1. **Hackathon rules** (Section 12) are binding.
2. **Zero budget** beyond free tiers and hackathon credits.
3. **All API keys, tokens, secrets, service endpoints, webhook secrets and any other values obtained from external sources are stored in the `.env` file** (Section 2.8). No such value shall appear in code, YAML configuration, logs, the database or the repository.
4. **No healthcare framing** anywhere in the product or materials. Healthcare or pharmaceutical sector indices shall not be featured in the universe or examples.
5. **Everything is for India.** The universe, macro factors, filings, calendars, currency, benchmarks, regulation and examples are Indian. US-market data and sources are not used, except global macro drivers of Indian markets (Section 5.8).
6. **Real-data policy** (Section 2.7).
7. **Regulatory posture:** educational analytics only, never personalized advice (Section 8.6 and `finance/06_regulatory_and_compliance_india.md`).

### 2.6 Assumptions and dependencies

- Nebius Token Factory serves Nemotron 3 Nano, Super and Ultra. At review time, prices per million input/output tokens were Ultra $1.00/$3.00, Super $0.30/$0.90, Nano $0.06/$0.24.
- Supabase's free plan is sufficient for development. It was listed at 500 MB database, 50,000 monthly active users, and automatic pausing after a week of inactivity. The pause is a risk for the judging period (Section 13).
- **Indian price data has no single official free API.** Candidate routes are unofficial (yfinance NSE/BSE tickers), exchange and index-provider downloads, and limited free tiers of commercial APIs. This is **unverified** and is the first thing checked in Phase X.
- **Indian filings have no SEC-style bulk JSON API.** NSE and BSE publish individual filings in XBRL for download. Complete data series are sold by subscription. Programmatic access routes and their terms are **unverified**.
- SEBI LODR requires listed companies to publish earnings-call recordings (within 24 hours) and transcripts (within five working days) on their websites and the exchanges, so transcripts are public. Format, completeness and ease of retrieval vary by company and are **unverified**.
- Nemotron models support the needed tool calling and JSON-schema output on Token Factory. **Unverified.**
- A suitable payment gateway offers a test mode usable without business KYC. **Unverified.**
- Real, consented trade logs can be obtained (Section 4.8).

### 2.7 Engineering policies (apply to every task)

**P-1 Real-data policy.** The project uses **no mocks, fakes, stubs, simulated services, injected faults, synthetic datasets, or recorded fixtures standing in for a live service**. Such stand-ins hide integration defects.
- Anything needing an external service is built and tested against the real service.
- Tests that touch real services are marked `live`, use real keys from `.env`, and draw from a test budget.
- Failure handling is verified against real failures (invalid key, nonexistent model, unknown symbol, a real rate-limit response). Faults are never injected.
- Feature 3 uses real trade logs, never generated ones.
- **Payments use the real gateway in its own test mode** (a real service, not a mock). Live-money mode is not used during the hackathon.
- There are no placeholder plan or checkout screens.

**P-1a Permitted exception: known-answer tests.** Pure arithmetic with analytically known results may be tested on tiny hand-computable inputs (identity-matrix absorption ratio; XIRR of -100 then +110 a year later). These test a formula, not a system.

**P-2 Loud failures.** Upstream errors surface with the upstream status and message. No silent fallback. The only substitution allowed is the explicit serving of precomputed results (Section 4.10), labeled `cached: true` with `computed_at`.

**P-3 Determinism where defensibility matters.** Numbers, thresholds, matching, verification and access control are deterministic.

**P-4 Every LLM output is validated** (schema, citations, forbidden language) before reaching a user.

**P-5 Contracts are frozen** after the first batch. Changes need an entry in `DECISIONS.md`.

**P-6 Provenance.** Every derived result carries source, retrieval time, parameters and code version.

**P-7 Reproducibility.** Random procedures use a recorded seed.

**P-8 Configurable, not hardcoded.** Every analytical parameter (windows, thresholds, universe, weights) has a default in `config/` and is validated against bounds. Where a parameter is user-relevant (for example the correlation window), it can be overridden per request within those bounds, and the value used is recorded in the result.

### 2.8 Secrets and configuration location (normative)

All API keys and secrets live in a standard `.env` file at the **repository root** (`<repo>/.env`), which is **gitignored** and never committed.

- **Path:** `<repo root>/.env`, resolved with `pathlib`.
- **Template:** `<repo root>/.env.example` is committed and lists variable *names* with no values.
- **Private data:** `<repo root>/private/` (gitignored) holds data that must never be committed, such as real trade logs (`private/logs/`) and downloaded raw exchange data.
- **Precedence:** real process environment variables override `.env`, so a host can inject secrets without a file.
- **Startup:** fail fast, naming every missing required variable; never print values.
- **Repo hygiene:** `.gitignore` excludes `.env`, `.env.*` (except `.env.example`), `private/`, and `data/`. A pre-commit check should refuse staged secrets.
- **Non-secret configuration** (universe, thresholds, lexicon, plans, episodes) lives in versioned YAML in `config/`.

The variable list is in Appendix A.

---

## 3. System architecture

### 3.1 Components

| Component | Responsibility | Type |
|---|---|---|
| Config loader | Reads `.env` and validates YAML | Deterministic |
| Auth verification | Verifies Supabase-issued JWTs; maps users to profiles | Deterministic |
| Entitlement and quota layer | `require_feature(name)`, segment rules, quotas, rate limits | Deterministic |
| Payment service | Orders/subscriptions, webhook verification, plan changes | Deterministic (gateway-backed) |
| LLM gateway | Token Factory client, model aliases, structured output, tool loop, ledger, budget guard | Wrapper |
| Market data service | Pulls, stores, validates Indian prices, indices, macro series | Deterministic |
| F1 engine | Correlation, adjustment, AR, bootstrap, flags, evidence pack | Deterministic |
| F1 explainer | News retrieval and hypotheses with validation | LLM + validation |
| Exchange filings service | NSE/BSE results (XBRL), announcements, press releases, transcripts | Deterministic |
| F2 pipeline | Chunking, claim extraction, matching, adjudication, verification | LLM at two steps |
| F3 engine | Log parsing, XIRR, counterfactuals, process metrics, review | LLM at mapping and narrative |
| Agent orchestrator | Tool-using loop with step streaming | LLM (Super) + tools |
| Result store and cache | Provenance-stamped precomputed results | Deterministic |
| Cost ledger | Per-call tokens and estimated cost; budget guard | Deterministic |
| Ops service and console | Read-only operational endpoints and a basic web UI | Deterministic |

### 3.2 Data flow by feature

**F1.** Index/ETF and macro snapshots → aligned returns → estimators (configurable windows) → FR adjustment, rank correlation, AR, bootstrap → flag logic → `CorrelationScan` → cluster and factor attribution → `EvidencePack` → Tavily news for the window → Ultra writes `Hypothesis` objects → validators → result.

**F2.** NSE/BSE XBRL results → normalized `FilingMetric`. Press release, investor presentation or transcript for the same fiscal period → chunks with offsets → Nano extracts `Claim` records → rules match claims to metrics → non-GAAP/adjusted-figure guard → Ultra adjudicates candidates → verifier → precision filter.

**F3.** Real log → parser (Nano maps unfamiliar columns) → corporate-action adjustment → position ledger → XIRR → benchmark replays → process metrics (and institutional metrics where applicable) → Ultra writes the review → validators.

**Agent.** Question → Super chooses tools → code executes each tool with the user's entitlements enforced → results return → answer streams with every step visible.

### 3.3 Technology stack

- **Backend:** Python, FastAPI, Pydantic v2, pydantic-settings, Uvicorn.
- **Datastore:** Supabase Postgres (primary). Supabase Auth for identity. pgvector inside Supabase if retrieval over documents is needed. **Pinecone is not planned**: it is a vector index without relational data or auth, so it could only ever supplement Supabase. It is listed as an optional, undecided item (T2).
- **Numerics:** numpy, pandas, scipy, scikit-learn, statsmodels. pyarrow for local snapshots.
- **LLM access:** the `openai` Python SDK pointed at the Token Factory base URL. This is only an HTTP client for an OpenAI-compatible API format; the models served are Nemotron.
- **Payments:** gateway SDK (candidate: Razorpay, TBD).
- **Frontend (basic ops console):** a minimal React + Vite single-page app in `frontend/`, evolving into the final frontend.
- **Packaging/tooling:** Docker, pytest, ruff, mypy.

### 3.4 Repository layout (normative)

```
backend/app/{config,auth,entitlements,payments,llm,agent,data,db,ops,features/{f1_contagion,f2_filings,f3_log}}
backend/tests/{known_answer,live}
frontend/                (basic ops console, grows into the final frontend)
config/{universe.yaml,episodes.yaml,plans.yaml,lexicon.yaml,thresholds.yaml,parameters.yaml}
finance/                 (finance documentation for the advisor)
docs/contracts/
scripts/
data/                    (gitignored: downloaded market and filings data)
private/                 (gitignored: real trade logs, raw exchange data)
.env                     (gitignored: all secrets)
.env.example             (committed: names only)
AGENTS.md  DECISIONS.md  FEEDBACK.md  PROJECT.md  PROGRESS.md  LICENSE  README.md
```

Raw exchange and index data is **not committed** to the public repository, because exchange data may carry redistribution restrictions (Section 7.5). The repository holds the scripts that pull it.

---

## 4. Functional requirements

Priority: **M** must, **S** should, **C** may/stretch.

### 4.1 Configuration and secrets (FR-CFG)

| ID | Requirement | Pri |
|---|---|---|
| FR-CFG-001 | Load secrets from `<repo>/.env` (Section 2.8). | M |
| FR-CFG-002 | Process environment variables override `.env`. | M |
| FR-CFG-003 | Validate required variables at startup; fail naming each missing one; never print values. | M |
| FR-CFG-004 | Secrets never appear in logs, errors, the database, the cache, or the ops console. | M |
| FR-CFG-005 | Read universe, thresholds, lexicon, plans, episodes and parameters from validated YAML in `config/`. | M |
| FR-CFG-006 | No analytical threshold or window length appears inline in algorithm code. | M |
| FR-CFG-007 | Each parameter in `config/parameters.yaml` declares a default, a minimum, a maximum, and whether per-request override is allowed. Out-of-bounds requests are rejected with a clear error. | M |
| FR-CFG-008 | Every result records the parameter values actually used. | M |

### 4.2 Accounts, authentication (FR-AUTH)

| ID | Requirement | Pri |
|---|---|---|
| FR-AUTH-001 | Use Supabase Auth for identity: email/password sign-up and login. | M |
| FR-AUTH-002 | Email verification is required before access to any analytical feature. | M |
| FR-AUTH-003 | Google OAuth login is supported. | M |
| FR-AUTH-004 | The backend verifies the Supabase JWT on every request (signature, expiry, audience) and loads the user's profile (segment, plan, role). | M |
| FR-AUTH-005 | A `profiles` table stores segment (`retail` or `institutional`), plan, role and status. Row-level security restricts each user to their own rows. | M |
| FR-AUTH-006 | Sign-up asks for segment. Institutional accounts start on `institutional_free`. The `institutional_paid` plan can be purchased only after an administrator approves a submitted regulator registration number (SEBI, or the institution's own regulator). | M |
| FR-AUTH-007 | State-changing requests validate the `Origin` header. | M |
| FR-AUTH-008 | Authentication and sign-up endpoints are rate limited. | M |
| FR-AUTH-010 | Sign-up requires acceptance of the Terms of Service and the educational-use disclaimer. The acceptance, its version and its time are stored and re-requested when the terms change. | M |
| FR-AUTH-009 | Verification emails use Supabase's built-in sender during development and a custom SMTP provider before real users if the built-in sender's limits are too low (TBD). | S |

### 4.3 Entitlements and quotas (FR-ENT, FR-QUO)

Plans are defined in `config/plans.yaml`:

| Plan | Segment | F1 | F2 | F3 |
|---|---|---|---|---|
| `retail_free` | retail | not available | limited | limited, retail scope |
| `retail_paid` | retail | not available | full | full, retail scope |
| `institutional_free` | institutional | locked (upgrade available) | limited (same as `retail_free`) | limited, retail scope (same as `retail_free`) |
| `institutional_paid` | institutional | full | limited (retail-free level; full F2 is not purchasable) | full, institutional scope, heavier quotas |
| `judge_all` (internal) | internal | full | full | full, both scopes |

There is no institutional free trial; institutions use the retail-level free tier until they pay. Billing is monthly. Prices are provisional test-mode amounts in `plans.yaml` (D-09).

| ID | Requirement | Pri |
|---|---|---|
| FR-ENT-001 | Plans, features and per-feature quotas are defined in `config/plans.yaml` and validated at startup. | M |
| FR-ENT-002 | Every feature route is guarded by `require_feature(name)`. | M |
| FR-ENT-003 | Where a **plan upgrade within the user's segment** would unlock the feature, respond HTTP **402** with a machine-readable payload (feature, current plan, plans that unlock it). | M |
| FR-ENT-004 | Where the feature is unavailable to the account's segment at any price (F1 for retail accounts), respond HTTP **403** with `error.code = "segment_restricted"` and no upgrade offer. A retail account shall not be able to unlock F1 by paying. An institutional account that exceeds its F2 quota receives HTTP 429 with a message that full F2 is a retail plan, not an upgrade offer. | M |
| FR-ENT-005 | `GET /api/entitlements` returns each feature's state (`allowed`, `limited`, `upgrade_available`, `segment_restricted`) and remaining quota. | M |
| FR-ENT-006 | Agent tool calls pass through the same checks inside the tool layer. | M |
| FR-ENT-007 | Plan changes are made only by (a) a verified payment webhook or (b) a local administrator CLI. No other path changes a plan. | M |
| FR-ENT-008 | `judge_all` is not purchasable and cannot be assigned through payment flows. | M |
| FR-QUO-001 | Quotas are enforced per account per UTC day, per feature, from `plans.yaml`. Initial `retail_free` quotas (proposed): F2 = 3 analyses per day; F3 = 1 log per day, up to 20 trades. | M |
| FR-QUO-002 | Exceeding a quota returns HTTP 429 with the reset time. | M |
| FR-QUO-003 | LLM-backed routes also enforce per-minute rate limits per account. | M |
| FR-QUO-004 | `judge_all` quotas are high enough that judging cannot be blocked, but remain subject to the budget guard. | M |
| FR-QUO-005 | A seed command creates `judge` and the two demo accounts (by Supabase Auth admin API), with passwords from `.env`. It is idempotent and never prints passwords. | M |

### 4.4 Payments (FR-PAY)

| ID | Requirement | Pri |
|---|---|---|
| FR-PAY-001 | Use an Indian payment gateway (candidate: Razorpay; TBD) via its server SDK. Amounts are in INR. | M |
| FR-PAY-002 | The backend creates orders or subscriptions for a plan and returns what the frontend needs to open checkout. | M |
| FR-PAY-003 | Plan changes happen only after the gateway's **webhook** is verified by signature using the webhook secret from `.env`. A client-side success callback alone shall never change a plan. | M |
| FR-PAY-004 | Webhook handling is idempotent: replays and out-of-order events cannot double-apply or corrupt state. | M |
| FR-PAY-005 | Payment records (gateway IDs, amount, currency, status, plan, timestamps) are stored. Card or bank details are never stored. | M |
| FR-PAY-006 | Retail users can only purchase retail plans; institutional users only institutional plans. | M |
| FR-PAY-007 | Subscription lapse or cancellation downgrades the account per this rule: at the end of a period without a successful renewal the account returns to its segment's free plan; no data is deleted; there is no grace period (D-08, provisional). | M |
| FR-PAY-008 | GST handling and invoice requirements are specified with the advisor (`finance/08_pricing_and_tiers.md`). | S |
| FR-PAY-009 | During the hackathon the gateway runs in its test mode. Live-money mode is out of the current build. | M |
| FR-PAY-010 | Judges and demo accounts never need to pay. | M |
| FR-PAY-011 | Plans are billed monthly. Annual billing is deferred. | M |

### 4.5 LLM gateway (FR-LLM)

| ID | Requirement | Pri |
|---|---|---|
| FR-LLM-001 | All LLM calls go through one gateway using the Token Factory OpenAI-compatible API. | M |
| FR-LLM-002 | Resolve aliases `fast` (Nano), `mid` (Super), `deep` (Ultra) to real model IDs from the live model list at startup. Unresolvable alias is a startup error. | M |
| FR-LLM-003 | Connect timeout 10 s; read timeout up to 120 s for `deep`; up to 3 retries with exponential backoff on 429 and 5xx only. | M |
| FR-LLM-004 | Structured-output helper: request JSON, validate against a Pydantic model, retry up to N times with the validation error fed back. | M |
| FR-LLM-005 | Tool-call loop: the model proposes calls and only our code executes them, with a step cap and token cap. | M |
| FR-LLM-006 | Ledger rows for every call: time, user, route, alias, model ID, input and output tokens (from API usage fields), estimated cost, cache hit. | M |
| FR-LLM-007 | Response cache keyed by hash of (model, messages, parameters), bypassable with `NO_CACHE`. | M |
| FR-LLM-008 | External text (filings, transcripts, news, uploads) is placed in delimited blocks and treated as data, never instructions. | M |
| FR-LLM-009 | Enforce a daily budget from `.env`. When exhausted, new uncached calls fail clearly while precomputed results keep serving. | M |
| FR-LLM-010 | Handle reasoning content separately from the final answer once the live format is confirmed. | S |

### 4.6 Market data service (FR-MKT)

| ID | Requirement | Pri |
|---|---|---|
| FR-MKT-001 | The universe is defined in `config/universe.yaml` (Section 5.1), as an asset set (returns analyzed) and a macro-factor set (explanatory). | M |
| FR-MKT-002 | A pull script fetches daily series from the sources chosen in the first Phase X feasibility check, and writes them to the datastore with a manifest (source, retrieval time, date range, row counts). | M |
| FR-MKT-003 | The pull script is the only code contacting price and macro providers. The application reads stored data only. | M |
| FR-MKT-004 | A `PriceStore` loads aligned series on the Indian trading calendar and validates them: gaps, duplicates, non-positive values, unadjusted splits or bonuses, outlier returns. Failures are reported, not silently repaired. | M |
| FR-MKT-005 | Each series records price type (price index vs total return, adjusted vs unadjusted) so analyses never mix them. | M |
| FR-MKT-006 | Real-time and intraday data are not supported in this build. | n/a |

### 4.7 Feature 1: Contagion Detector (FR-F1): institutional only

| ID | Requirement | Pri |
|---|---|---|
| FR-F1-001 | Compute rolling or EWMA correlation matrices using only data available at or before each date (no lookahead). | M |
| FR-F1-002 | Use Ledoit-Wolf shrinkage in covariance estimates. | M |
| FR-F1-003 | **All window lengths are configurable** (estimation window `W`, baseline `B`, gap `G`, current `C`, AR window `T`, EWMA decay, bootstrap block length and count). Defaults live in `config/parameters.yaml`; the scan request may override each within bounds (FR-CFG-007). | M |
| FR-F1-004 | Compare current against baseline for every pair and report the change. | M |
| FR-F1-005 | Apply the Forbes-Rigobon adjustment (5.3) and compute Spearman rank correlation as a robustness check. | M |
| FR-F1-006 | Compute the absorption ratio and its standardized shift (5.5). | M |
| FR-F1-007 | Test significance with a block bootstrap using a recorded seed (5.6). | M |
| FR-F1-008 | Combine signals into a regime flag with severity tiers from configuration (5.7), producing `CorrelationScan`. | M |
| FR-F1-009 | Identify the driving cluster and attribute the common component to macro factors (5.8), producing an `EvidencePack` with stable IDs. | M |
| FR-F1-010 | Retrieve news through Tavily for the flagged window with queries built from the evidence pack, under a per-run credit cap. | M |
| FR-F1-011 | Generate 2-4 ranked `Hypothesis` objects with `deep`. Each cites at least one evidence ID, cites only retrieved URLs, and is worded as a plausible mechanism, never an established cause. | M |
| FR-F1-012 | Validators reject invented evidence IDs, invented URLs, numbers not in the pack, and definitive causal wording; one retry follows a rejection. | M |
| FR-F1-013 | Support replay of named episodes (Appendix D), using only data available up to each date. | M |
| FR-F1-014 | Report the fraction of all days in the sample on which a flag fires, and include **negative-control periods** (calm periods and idiosyncratic shocks) beside episode results. | M |
| FR-F1-015 | Overlay a portfolio's exposure on a flagged cluster when a `Portfolio` is available. | C |
| FR-F1-016 | Allow an arbitrary as-of date. | C |
| FR-F1-017 | Reachable only through `require_feature("contagion")`. | M |

### 4.8 Exchange filings service (FR-FIL)

| ID | Requirement | Pri |
|---|---|---|
| FR-FIL-001 | Retrieve, for each chosen company and fiscal period, the financial-results XBRL filed under SEBI LODR Regulation 33 from the NSE or BSE, by a method confirmed in the Phase X feasibility check (official download links, documented endpoints, or a subscription if the team chooses). | M |
| FR-FIL-002 | Identify the correct result format. NSE publishes distinct formats for Ind AS (non-bank), banks, NBFCs and insurers; the MVP scope covers Ind AS non-financial companies only (T6). | M |
| FR-FIL-003 | Parse XBRL into normalized `FilingMetric` records (7.2) with standalone vs consolidated labelled explicitly. | M |
| FR-FIL-004 | Retrieve, for the same fiscal period, management-commentary text: the earnings press release, the investor presentation, and the earnings-call transcript where published under Regulation 46(2)(oa). | M |
| FR-FIL-005 | Convert PDF documents to text with page and offset tracking, and record conversion quality. | M |
| FR-FIL-006 | Identify fiscal periods in Indian form (for example "Q1 FY27" = April-June 2026) and map them to period-end dates. | M |
| FR-FIL-007 | Fetch politely: identify the client, throttle conservatively, honor the site's terms, cache every response on disk with URL and retrieval time. Rate limits are TBD. | M |
| FR-FIL-008 | Extraction failures (blocked request, malformed filing, missing transcript) surface as explicit errors per P-2. | M |

### 4.9 Feature 2: Filing Consistency Checker (FR-F2): retail, institutions at free-tier limits

| ID | Requirement | Pri |
|---|---|---|
| FR-F2-001 | Chunk source documents into sections with stable character offsets. | M |
| FR-F2-002 | The `fast` model extracts `Claim` records: `(metric, descriptor, direction, verbatim quote, start offset, end offset, period, basis)` where `basis` is reported, adjusted, constant-currency or unspecified. A claim whose quote is not an exact substring at its offsets is dropped. | M |
| FR-F2-003 | A claim's fiscal period comes from document metadata and must equal the filing's fiscal period. Mismatches are rejected. | M |
| FR-F2-004 | A matcher joins claims to normalized metrics (same period, same standalone/consolidated basis) and applies the rules in 5.10 using `config/lexicon.yaml` and `config/thresholds.yaml`. | M |
| FR-F2-005 | An adjusted-figure guard downgrades or suppresses a candidate when the claim or its context uses adjusted, normalized, exceptional-item-excluded, or constant-currency language, unless the reconciliation shows the same direction on the reported figure. | M |
| FR-F2-006 | `deep` adjudicates each candidate (confirm, downgrade, reject) with a rationale and a "benign explanation considered" field. It cannot create candidates. | M |
| FR-F2-007 | A verifier rejects any flag unless (a) the quote appears verbatim at the cited offsets, (b) each cited number equals the normalized value, (c) the periods and the standalone/consolidated basis match. | M |
| FR-F2-008 | Favor precision. Show only flags at or above a configured confidence, capped per document. | M |
| FR-F2-009 | Each flag shows the quote, the filing metric with period and basis, the rule that fired, severity, and the rationale. | M |
| FR-F2-010 | An evaluation harness computes precision and recall against human labels in `data/labels/`. | M |
| FR-F2-011 | Reachable only through `require_feature("filings")`; retail paid plans have full quotas, and all other plans have the free quota in FR-QUO-001. | M |
| FR-F2-012 | Live ingestion of a newly reported quarter is supported. | C |

### 4.10 Feature 3: Investment Log Advisor (FR-F3): both segments

**Data source policy.** Feature 3 is developed and demonstrated only with real trade logs: (a) broker exports or consolidated statements provided by team members or volunteers, with written consent and identifiers removed; (b) where useful, real public disclosures of trades. Real logs live in `private/logs/` and are never committed. A log shown in public material requires the owner's explicit consent. Handling of personal data follows `finance/06_regulatory_and_compliance_india.md`.

| ID | Requirement | Pri |
|---|---|---|
| FR-F3-001 | Parse a log with required fields `date, symbol, side, quantity, price` and optional `fees, charges, exchange, segment`. | M |
| FR-F3-002 | For unfamiliar layouts, `fast` proposes a column mapping that the user must confirm before processing. | M |
| FR-F3-003 | Adjust historical quantities and prices for corporate actions (splits, bonus issues, rights, dividends where relevant) using the data source's action records; unresolved actions are reported. | M |
| FR-F3-004 | Build a position ledger (lots, realized and unrealized results) and compute XIRR (5.11). | M |
| FR-F3-005 | Replay identical cash flows into benchmarks (Nifty 50 total return, a sector or style index chosen from holdings, and a risk-free proxy) and report terminal value and XIRR for each. | M |
| FR-F3-006 | Compute process metrics (5.11): concentration, holding periods, entry-after-run-up, drawdown, turnover, disposition effect. | M |
| FR-F3-007 | **Institutional scope** additionally computes benchmark-relative statistics (alpha, beta, tracking error, information ratio) and supports larger logs (limits in `plans.yaml`). Metric definitions are advisor-confirmed (T5). | M |
| FR-F3-008 | `deep` writes a `DecisionReview` that separates outcome from process, cites only computed metrics, avoids hindsight framing, and carries the educational-use disclaimer. | M |
| FR-F3-009 | Uploaded logs are processed without persistence by default; retention requires explicit user action and consent text. | M |
| FR-F3-010 | The review never says to buy, sell or hold any security and never gives a price target. | M |
| FR-F3-011 | Reachable through `require_feature("log_advisor")`; scope (retail or institutional) follows the account's segment. | M |
| FR-F3-012 | Expose the resulting `Portfolio` for use by F1 and F2. | S |
| FR-F3-013 | Browser upload route. | C |

### 4.11 Agent orchestrator (FR-AGT)

| ID | Requirement | Pri |
|---|---|---|
| FR-AGT-001 | A `mid` loop answers questions using tools `scan_correlations`, `get_filing_facts`, `find_inconsistencies`, `search_news`, `compare_alternatives`. Tools a user's segment cannot use are not offered to the model. | M |
| FR-AGT-002 | Each tool has a schema from the contract models and runs real code on real data. | M |
| FR-AGT-003 | Step cap (default 8), token budget, and a refusal path for out-of-scope questions or requests for advice. | M |
| FR-AGT-004 | Stream `AgentStep` events over SSE. | M |
| FR-AGT-005 | The final answer states which computed results it relied on. | S |
| FR-AGT-006 | Agent routes are rate limited per FR-QUO-003. | M |

### 4.12 Precomputation, caching, observability (FR-CAC, FR-OBS)

| ID | Requirement | Pri |
|---|---|---|
| FR-CAC-001 | A precompute job runs the real pipelines for every demo path and stores results with provenance (inputs, parameters, model IDs, seed, code version, `computed_at`). | M |
| FR-CAC-002 | Demo endpoints serve stored results in under one second, labeled `cached: true` with `computed_at`. | M |
| FR-CAC-003 | If a live call fails, return the error. Never silently substitute stored output. | M |
| FR-CAC-004 | A cost-report command summarizes ledger spend and projects spend through the end of the judging period. | M |
| FR-OBS-001 | Structured logs with request IDs, never containing secrets or uploaded-log contents. | M |
| FR-OBS-002 | `GET /health` (liveness) and `GET /ready` (Supabase reachable, aliases resolved). | M |
| FR-OBS-003 | One error envelope: `{error: {code, message, request_id, upstream?}}`. | M |
| FR-OBS-004 | Every significant operation (data pull, pipeline run, LLM call batch, payment event, plan change, cache write) writes a row to an `events` table, which feeds the ops console. | M |

### 4.13 Basic ops frontend (FR-UI): present at all times

A basic frontend exists from the start of the build and grows with it. Its purpose is to let the team see what is happening and what is being updated. It is deliberately plain.

| ID | Requirement | Pri |
|---|---|---|
| FR-UI-001 | A single-page app in `frontend/`, sign-in with Supabase Auth, restricted to admin role in production. | M |
| FR-UI-002 | **Status panel:** liveness and readiness, and a pass/fail line for each external service (Token Factory, Tavily, Supabase, price source, filings source, payment gateway) with last-checked time and the real error text on failure. | M |
| FR-UI-003 | **Configuration panel:** which required `.env` variables are present (names only, never values), and the active parameter set. | M |
| FR-UI-004 | **Data panel:** each stored series and filing set with source, last update, date range, row counts and validation results. | M |
| FR-UI-005 | **Activity feed:** a live (SSE) stream of `events` showing what is running or just changed, with timestamps, inputs, duration and outcome. | M |
| FR-UI-006 | **Cost panel:** LLM spend today versus budget, by alias and route, plus cache hit rate. | M |
| FR-UI-007 | **Feature runners:** one form per feature with all configurable parameters (including the correlation windows), showing raw JSON output and simple tables or charts (heatmap, AR timeline, flags table, benchmark comparison). | M |
| FR-UI-008 | **Agent trace:** a chat box that shows each agent step as it streams. | M |
| FR-UI-009 | **Accounts and entitlements panel:** users, segments, plans, quotas used, recent payment events (no card data). | S |
| FR-UI-010 | Each backend batch in `PROGRESS.md` includes the task that adds its panel or view, so the console never falls behind the backend. | M |
| FR-UI-011 | The console contains no hidden logic. It only calls documented API routes. | M |

---

## 5. Algorithm specifications

All algorithms are deterministic. Defaults are **starting values** stored in `config/parameters.yaml` and `config/thresholds.yaml`, to be tuned on real data and confirmed with the advisor. Financial rationale for each is in `finance/`.

### 5.1 Universe and returns

Two sets, both in `config/universe.yaml`. Final contents are **TBD** pending data coverage and advisor review (`finance/03_feature1_contagion_finance.md`).

- **Asset set (returns analyzed), candidates:** Nifty 50, Nifty Next 50, Nifty Midcap, Nifty Smallcap, Nifty Bank, Nifty IT, Nifty FMCG, Nifty Metal, Nifty Realty, Nifty Energy; a government-securities index or benchmark-yield series; gold (INR); USD/INR; Brent crude (INR-converted or USD); a US large-cap index as the foreign-equity linkage. Healthcare and pharmaceutical indices are excluded.
- **Macro-factor set (explanatory), candidates:** RBI repo rate and 10-year G-sec yield, India VIX, US 10-year yield, broad US dollar index, Brent crude, FPI net flows, system liquidity, a corporate-bond spread if obtainable.

Daily log return `r_t = ln(P_t / P_{t-1})`, aligned on the intersection of Indian trading dates. Price and total-return series are never mixed within a calculation.

### 5.2 Correlation and covariance estimators

All window lengths below are **parameters** (FR-F1-003), not constants.

| Parameter | Meaning | Default (to tune) | Bounds |
|---|---|---|---|
| `W` | Estimation window: number of trading days used to estimate a correlation matrix | 60 | 20-500 |
| `lambda` | EWMA decay | 0.94 | 0.80-0.99 |
| `B` | Baseline window (the "normal" period compared against) | 250 | 60-1000 |
| `G` | Gap between baseline end and current window start | 20 | 0-250 |
| `C` | Current window | 20 | 5-250 |
| `T` | AR covariance window | 250 | 60-1000 |
| `AR_short`, `AR_long` | AR averaging windows | 15, 250 | 5-60, 60-1000 |
| `block_len`, `n_boot` | Bootstrap block length and replicates | 10, 1000 | 2-60, 200-5000 |
| `fdr_q` | False-discovery-rate level for the Benjamini-Hochberg control across pairs | 0.10 | 0.01-0.25 |
| `us_series_lag_days` | Days by which US series are lagged against Indian series (India closes before the US opens) | 1 | 0-2 |

- **Rolling:** correlation over the last `W` trading days.
- **EWMA:** `Σ_t = λ Σ_{t-1} + (1 − λ) r_t r_tᵀ`, initialized from the first `W` observations.
- **Shrinkage:** Ledoit-Wolf on the sample covariance in each window before converting to correlation.
- **Baseline vs current:** baseline window `B` ends `G` days before the current window `C`. No data later than the as-of date is used.
- **Validation:** the system rejects parameter sets that cannot be satisfied by the available history (for example `B + G + C` longer than the series).

### 5.3 Volatility-bias adjustment (Forbes-Rigobon)

For a pair (x, y) with x the market treated as the source of the shock, let `ρ` be the correlation in the high-volatility window and `δ = σ²_x,high / σ²_x,low − 1`, where `σ²_x,low` is x's variance over the baseline. Then

```
ρ* = ρ / sqrt( 1 + δ · (1 − ρ²) )
```

If `δ ≤ 0` the adjustment is the identity. The adjustment assumes no omitted variables, no endogeneity and a stable relationship; published critiques show these often fail, so it is never the only signal. It is combined with rank correlation (5.4) and the absorption ratio (5.5).

### 5.4 Rank correlation

Spearman correlation over the same windows, as a robustness signal less sensitive to volatility and outliers.

### 5.5 Absorption ratio

With eigenvalues `λ_1 ≥ … ≥ λ_N` of the correlation matrix over window `T`, and `k = ceil(N / 5)` (the Kritzman et al. convention; confirm during implementation):

```
AR = ( Σ_{i=1..k} λ_i ) / ( Σ_{i=1..N} λ_i )
ΔAR = ( mean AR over AR_short − mean AR over AR_long ) / std of AR over AR_long
```

Known-answer checks: the identity matrix gives `AR = k/N`; a rank-one matrix gives `AR = 1`.

### 5.6 Block bootstrap significance

Across all pairs, apply Benjamini-Hochberg false-discovery-rate control at `fdr_q` (D-18). Resample the baseline window's paired returns with a moving-block bootstrap (`block_len`, `n_boot`) to build a null distribution of correlation on a window of length `C`. The p-value is the share of bootstrap values at or above the observed current-window correlation. Record the seed.

### 5.7 Regime flag logic

Three signals per as-of date:
- **S1:** the share of pairs whose FR-adjusted correlation change is significant (p < α, default 0.05, with multiple-testing control, T10) exceeds a configured level.
- **S2:** `ΔAR` exceeds a configured z-threshold (default 1.0).
- **S3:** the mean Spearman shift across pairs exceeds a configured threshold.

Flag when at least two of three agree. Severity tiers (watch, elevated, severe) follow signal count and `ΔAR`. **Calibration protocol:** tune thresholds on some episodes and evaluate on held-out ones; report the full-sample flag frequency and the negative-control results (FR-F1-014); report misses honestly. Episode windows are fixed before any tuning and never adjusted afterward.

### 5.8 Cluster and factor attribution

1. **Cluster:** rank pairs by contribution to the rise in average correlation; take the connected set covering the top share of the increase.
2. **Common component:** first principal component of current-window returns, with per-asset loadings.
3. **Macro association:** correlate PC1 scores (or the cluster's equal-weighted return) with daily changes in macro series over the current window. Candidate series, IDs and sources **TBD**: RBI repo and 10-year G-sec yield, India VIX, USD/INR, Brent, US 10-year yield, broad dollar index, FPI flows.
4. **Output:** an `EvidencePack` of moved pairs (before/after), AR values, PC1 loadings and ranked macro associations, each with an ID.

These associations are descriptive, never proof of causation.

```
EvidencePack { as_of, parameters_used, window:{baseline:[d0,d1], current:[d2,d3]},
  items:[{id:"E1", kind:"pair_shift|ar|pc1_loading|macro_assoc",
          description, values:{name:number}, source}], seed, code_version }
```

### 5.9 Hypothesis constraints

Hypotheses draw only on evidence-pack items and Tavily results. They state a mechanism class (for example global risk-off and FPI outflow; domestic liquidity squeeze; rate shock; currency stress; commodity shock; policy or event shock), the evidence supporting it, and the evidence that would weaken it. See the mechanism taxonomy in `finance/03_feature1_contagion_finance.md`.

### 5.10 Feature 2 metrics and rules

Metrics (from normalized quarterly data, with fiscal periods in April-March form): YoY growth `g = (v_t − v_{t−4Q}) / |v_{t−4Q}|`, QoQ growth, margins as metric ÷ revenue from operations, DSO = (receivables ÷ revenue) × days, operating-cash-flow conversion. Standalone and consolidated figures are never mixed. Q4 is derived as full year minus the nine-month cumulative where the filing gives only cumulative figures.

| Rule | Claim says | Numbers show | Base severity |
|---|---|---|---|
| R0 Stated number | Management states a specific figure ("grew 12%", "double-digit") on a reported basis | The filed figure differs by more than the tolerance, or falls outside the stated band | High |
| R1 Direction | Metric increased or grew | YoY or QoQ change ≤ 0 (or reverse for "declined") | High |
| R2 Magnitude | Strong-intensity word ("strong", "robust", "record", "all-time high") on growth | Growth below the strong threshold | Medium |
| R3 Trend | "Accelerating", "improving momentum", "sequential improvement" | Growth lower than previous period's | Medium |
| R4 Profitability | Margin expansion or improved profitability | Margin down YoY | High |
| R5 Cash quality | "Strong cash generation" | Operating cash flow down YoY or conversion below threshold | Medium |
| R6 Working capital | "Disciplined" inventory or "healthy" collections | Inventory growth well above revenue growth, or DSO up materially | Low-Medium |
| R7 Understatement | Cautious word on a metric that improved strongly | Metric up well above the strong threshold | Low (optional) |

The descriptor lexicon (`config/lexicon.yaml`) maps words and phrases to categories and metric families, and must include the phrasing common in Indian management commentary. The adjusted-figure guard (FR-F2-005) uses terms such as adjusted EBITDA, exceptional items, normalized, constant currency and ex-one-offs. The adjudicator may confirm, downgrade or reject candidates, never add one. Rule definitions and thresholds are advisor-confirmed (`finance/04_feature2_filings_finance.md`).

### 5.11 Feature 3 algorithms

**XIRR.** Find `r` with `Σ_i CF_i / (1 + r)^((d_i − d_0)/365) = 0` using a bracketed root-finder (Brent). Buys are negative, sells positive, plus a terminal flow equal to the market value of holdings at the as-of date. If no root exists, report that rather than a number.

**Benchmark replay.** For each buy outflow `A` on date `d`, buy `A / P_d` benchmark units; for each sell inflow `S`, sell `S / P_d` units. A sale larger than units held is recorded as a shortfall and the replay flagged `partial`. Use a **total return** benchmark where available. The risk-free proxy accrues from an Indian short-term rate series (source TBD).

**Process metrics (both scopes):** concentration (Herfindahl-Hirschman index of weights), holding-period distribution, entry-after-run-up (share of buys where trailing `N`-day return, default 20, is in the top decile of the asset's own history), maximum drawdown, turnover, and the disposition effect (Odean): `PGR = realized gains ÷ (realized gains + paper gains)`, `PLR` analogous for losses, measured on sale days.

**Institutional metrics (added in that scope; definitions advisor-confirmed):** beta and alpha versus a chosen benchmark, tracking error, information ratio, sector-level contribution, turnover and implementation-cost estimates from supplied charges.

**Ex-ante framing:** judge a decision only with information available on its date (position size, diversification, volatility, momentum at entry). Later prices alone are never used to call a past decision good or bad.

### 5.12 Agent loop

```
messages = [system, user]
for step in 1..MAX_STEPS:
    reply = model(messages, tools_allowed_for_segment)
    if tool calls: check entitlement; run real tool; append result; emit AgentStep
    else: emit final answer; stop
if cap reached: emit explicit "step limit reached" answer
```

---

## 6. External interface requirements

### 6.1 User interface

The basic ops console (Section 4.13) is built first and grows. The final frontend is specified later and shall support: sign-in and plan selection; an F1 view (heatmap, AR timeline, parameter controls, hypotheses with citations, episode selector); an F2 view (company and fiscal-period picker, flags with quote beside filing number and verifier status); an F3 view (log input, benchmark comparison, review); an agent chat with a step trace; locked-feature screens driven by 402 and 403 payloads; and an educational-use banner on every analytical output.

### 6.2 HTTP API

JSON with the error envelope (FR-OBS-003). "Gate" is the entitlement checked.

| Method and path | Auth | Gate | Purpose |
|---|---|---|---|
| `GET /health`, `GET /ready` | none | none | Liveness, readiness |
| `GET /auth/me` | JWT | none | Account, segment, plan |
| `GET /api/entitlements` | JWT | none | Feature states and quotas |
| `GET /payments/plans` | JWT | none | Plans purchasable by the user's segment |
| `POST /payments/checkout` | JWT | none | Create an order or subscription |
| `POST /payments/webhook` | gateway signature | none | Verified plan changes |
| `GET /f1/episodes`, `GET /f1/episodes/{id}` | JWT | contagion | Episodes; precomputed result (`cached`) |
| `POST /f1/scan` | JWT | contagion | Live scan with parameter overrides |
| `POST /f1/explain` | JWT | contagion | Live explanation |
| `GET /f2/companies` | JWT | filings | Available companies and fiscal periods |
| `POST /f2/analyze` | JWT | filings (quota) | Analysis for a company-period |
| `POST /f3/review` | JWT | log_advisor (quota) | Parse, confirm mapping, review |
| `POST /agent/ask` | JWT | per tool | SSE agent stream |
| `GET /ops/status`, `/ops/config`, `/ops/data`, `/ops/cost`, `/ops/accounts` | JWT (admin) | role | Ops console data (read-only) |
| `GET /ops/events` | JWT (admin) | role | SSE activity feed |

Plan assignment for internal accounts uses a CLI only.

### 6.3 External services

| Service | Used for | Notes |
|---|---|---|
| Nebius Token Factory | All LLM calls | Base URL from `.env`; OpenAI-compatible; model-list endpoint; rate limits TBD |
| Tavily | News retrieval (F1) | Free tier 1,000 credits per month; runtime call qualifies for the Tavily bonus |
| Supabase | Postgres, Auth, optional pgvector | Free tier pauses after a week idle |
| NSE / BSE | Filings, announcements, corporate actions | Individual XBRL downloadable; bulk series by subscription; access method TBD |
| Index and price sources | Daily prices, indices, TRI, India VIX | Candidates in 6.5; all TBD |
| RBI / FBIL, FRED | Rates, G-sec yields, FX, global factors | FRED needs a free key; RBI/FBIL access method TBD |
| Payment gateway | Checkout and webhooks | Candidate Razorpay; test mode; TBD |
| Google OAuth | Login | Configured in Supabase |
| Email sender | Verification emails | Supabase built-in or custom SMTP, TBD |

### 6.4 Communications

HTTPS in production, SSE for streaming, explicit timeouts and TLS for all outbound calls.

### 6.5 Data source register

Every external source the system may use. "Status" reflects what is verified; everything not verified is checked in Phase X before reliance.

| # | Source | Used for | Feature | Credential in `.env` | Status |
|---|---|---|---|---|---|
| 1 | Nebius Token Factory (Nemotron Nano, Super, Ultra) | All LLM calls | All | `NEBIUS_API_KEY`, `NEBIUS_BASE_URL` | Required by hackathon; models and prices seen; tool calling unverified |
| 2 | Tavily Search API | News for F1 hypotheses | F1, agent | `TAVILY_API_KEY` | Free tier 1,000 credits/month seen |
| 3 | Supabase (Postgres, Auth, pgvector) | Datastore, identity, optional retrieval | All | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `DATABASE_URL` | Free-tier limits seen |
| 4 | Pinecone | Vector index, only if retrieval needs it | optional | `PINECONE_API_KEY` | Not planned |
| 5 | NSE/BSE daily price source (candidates: yfinance NSE/BSE tickers, Alpha Vantage, Twelve Data, exchange archives) | Daily prices for indices and ETFs | F1, F3 | `PRICE_API_KEY` if a keyed source is chosen | Unverified; yfinance is unofficial |
| 6 | NSE Indices (niftyindices.com) | Historical index series, total-return indices, India VIX | F1, F3 | none | Unverified; terms to check |
| 7 | NSE/BSE financial-results XBRL | Reported numbers | F2 | none (identifying user agent in `.env`) | Individual filings downloadable; bulk is subscription; method unverified |
| 8 | NSE/BSE announcements and company IR sites | Press releases, presentations, call transcripts and recordings | F2 | none | Publication mandated by SEBI LODR; retrieval unverified |
| 9 | NSE/BSE corporate-actions records | Splits, bonus, dividends | F3 | none | Unverified |
| 10 | RBI (DBIE) and FBIL | Repo, G-sec yields, T-bill rates, INR reference rate, MIBOR | F1, F3 | none | Unverified |
| 11 | FRED | US yields, dollar index, Brent/WTI, global VIX | F1 | `FRED_API_KEY` | Unverified terms and series IDs |
| 12 | NSDL FPI data / NSE FII-DII statistics | Foreign and domestic institutional flows | F1 | none | Unverified |
| 13 | AMFI NAV and consolidated account statements | Mutual-fund NAVs and holdings | F3 | none | Optional; unverified |
| 14 | Real trade logs (broker exports) | F3 inputs | F3 | none (stored in `private/logs/`) | Must be obtained with consent |
| 15 | Payment gateway (candidate Razorpay) | Checkout, subscriptions, webhooks | Payments | `PAYMENT_KEY_ID`, `PAYMENT_KEY_SECRET`, `PAYMENT_WEBHOOK_SECRET` | Unverified; test mode needed |
| 16 | Email sender (Supabase built-in or SMTP) | Verification emails | Auth | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` if custom | Unverified limits |
| 17 | Google OAuth client | Google sign-in | Auth | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | Configured in Supabase |
| 18 | Hosting provider | Running the app through judging | Deployment | provider token if needed | TBD |

---

## 7. Data requirements

### 7.1 Database (Supabase Postgres)

| Table | Key columns |
|---|---|
| `profiles` | user_id (Supabase auth id), segment, plan, role, status, created_at |
| `subscriptions` | id, user_id, plan, status, current_period_end, gateway_ref |
| `payments` | id, user_id, gateway_ids, amount_inr, currency, status, plan, created_at |
| `usage` | user_id, feature, utc_date, count |
| `llm_ledger` | id, ts, user_id, route, alias, model_id, input_tokens, output_tokens, est_cost_usd, cache_hit |
| `results` | key, kind, payload_json, provenance_json, computed_at |
| `events` | id, ts, kind, subject, status, duration_ms, details_json |
| `series_meta`, `series_values` | series id, name, source, price type, adjusted flag; date, value |
| `filing_metrics` | company, symbol, fiscal period, period end, basis (standalone/consolidated), metric, value, unit, source ref, retrieval time |
| `documents` | id, company, fiscal period, kind (press release, presentation, transcript), url, text, conversion quality |

Row-level security applies to every user-owned table. The database is small by design to fit the free tier's size limit.

### 7.2 Normalized filing metrics

Each `FilingMetric` records: company, symbol, ISIN where available, fiscal period (April-March), period end date, basis (standalone or consolidated), metric, value, unit (INR crore or lakh, as reported), source filing reference, `derived` flag, retrieval time. Initial metrics: revenue from operations, total income, EBITDA (company-reported and our derived value, labelled separately), profit before tax, profit after tax, diluted EPS, operating cash flow, receivables, inventory.

### 7.3 Files and contracts

- `data/` (gitignored): downloaded raw data and caches.
- `data/labels/*.json`: human F2 labels (Appendix C).
- `private/logs/`: real trade logs.
- Frozen contract models (`docs/contracts/`): `Portfolio`, `CorrelationScan`, `EvidencePack`, `Hypothesis`, `Claim`, `FilingMetric`, `Inconsistency`, `TradeLog`, `DecisionReview`, `AgentStep`, `ColumnMapping`, the error envelope.

### 7.4 Privacy and retention

Trade logs are personal financial data of Indian users and fall under the DPDP Act. Logs are processed without persistence by default (FR-F3-009). If retained, consent text, purpose and deletion on request are required. Ledgers store token counts, not prompt text. Logs and results never contain full account numbers. Public use of a real log requires the owner's consent. Details in `finance/06_regulatory_and_compliance_india.md`.

### 7.5 Data licensing

Exchange and index-provider data may carry redistribution limits, so raw data is not committed to the public repository (Section 3.4) and no raw dataset is exposed through the API. Derived analytics are shown with attribution. Company-published transcripts and presentations are used for analysis, stored as extracts only, and attributed. Tavily and any price API terms are read and followed. These questions go to the advisor (`finance/06_regulatory_and_compliance_india.md`).

---

## 8. Non-functional requirements

### 8.1 Performance

| ID | Requirement |
|---|---|
| NFR-PERF-001 | Precomputed demo endpoints respond within 1 s at p95. |
| NFR-PERF-002 | A live F1 scan (statistics only) completes within 20 s; a live explanation within 90 s. |
| NFR-PERF-003 | A live F2 analysis for one company-period completes within 90 s. |
| NFR-PERF-004 | A live F3 review for up to 200 trades completes within 90 s. |
| NFR-PERF-005 | Agent step events begin streaming within 3 s. |
| NFR-PERF-006 | Ops console events appear within 2 s of occurring. |

### 8.2 Security

| ID | Requirement |
|---|---|
| NFR-SEC-001 | Secrets only in the gitignored `.env` or the process environment. |
| NFR-SEC-002 | JWTs verified on every request; Supabase row-level security on user-owned tables; the service-role key is used only server-side and never reaches the browser. |
| NFR-SEC-003 | Payment webhooks verified by signature; replays handled idempotently; no card data stored. |
| NFR-SEC-004 | All input validated by schemas; uploads limited in size and type. |
| NFR-SEC-005 | Prompt-injection defense: external text delimited and treated as data; the model has no authority beyond allowed tools; entitlements enforced in code; outputs validated. |
| NFR-SEC-006 | Rate limits on auth, payments and LLM-backed routes. |
| NFR-SEC-007 | Pinned dependencies; no secrets in the repository history. |
| NFR-SEC-008 | Judge credentials appear only in the Devpost testing-instructions field and are rotated or disabled after judging. |

### 8.3 Reliability and availability

| ID | Requirement |
|---|---|
| NFR-REL-001 | The hosted app and the Supabase project remain reachable through the end of the judging period. Because the free Supabase plan pauses after about a week of inactivity, a keep-alive or a paid plan is required. |
| NFR-REL-002 | Upstream failures produce explicit errors (P-2). |
| NFR-REL-003 | The budget guard prevents credit exhaustion from blocking precomputed results. |

### 8.4 Usability

Outputs explain findings in plain language with the evidence shown; locked features explain what is locked and why (402 vs 403 wording differs); every analytical view shows the educational-use disclaimer.

### 8.5 Maintainability and portability

Type hints throughout; `ruff` and `mypy` clean; one module per feature behind a stable interface; runs from one Docker image or a local checkout on Linux, macOS and Windows.

### 8.6 Legal and compliance (India)

| ID | Requirement |
|---|---|
| NFR-LEG-001 | The product provides educational analysis only. It shall not recommend buying, selling or holding any security, give price targets, or give personalized advice. SEBI has acted against unregistered advisory dressed up as education, so this boundary is a hard design rule. |
| NFR-LEG-002 | Every analytical output carries an educational-use disclaimer. |
| NFR-LEG-003 | The repository carries an OSI-approved license (MIT or Apache-2.0) visible at the top of the repository page. |
| NFR-LEG-004 | No healthcare framing. |
| NFR-LEG-005 | DPDP Act obligations for personal data are met (notice, consent, purpose limitation, deletion). Specific obligations are advisor-confirmed. |
| NFR-LEG-006 | GST and payment-gateway obligations are handled as specified with the advisor. |
| NFR-LEG-007 | The team's financial and legal exposure is limited by design: non-advisory outputs, a click-through Terms of Service with a liability cap and disclaimers, test-mode payments only until a legal entity exists and a lawyer has reviewed the terms. See `finance/12_terms_and_liability_framework.md`. |

### 8.7 Cost

LLM spend through the end of judging fits available credits per the cost report; Tavily use stays within the free allowance with a per-run cap and caching.

---

## 9. LLM call specifications

| Call | Alias | Input | Output | Validation | Temp |
|---|---|---|---|---|---|
| Claim extraction (F2) | fast | One chunk with fiscal-period metadata | `list[Claim]` | Quote is an exact substring at its offsets | 0.0 |
| Candidate adjudication (F2) | deep | Claim, matched metrics, rule fired, context | `Inconsistency` | Verdict in {confirm, downgrade, reject}; cannot add candidates; passes verifier | 0.2 |
| Column mapping (F3) | fast | Header plus 5 sample rows | `ColumnMapping` | Required fields mapped; user confirms | 0.0 |
| Decision review (F3) | deep | Computed metrics and benchmark results | `DecisionReview` | Cites only provided metric IDs; no buy/sell/hold or target language; disclaimer present | 0.3 |
| Mechanism hypotheses (F1) | deep | `EvidencePack` plus news items | `list[Hypothesis]` (2-4, ranked) | Citation, number and wording validators | 0.3 |
| Agent orchestration | mid | Conversation plus allowed tool schemas | Tool calls and final answer | Step cap; per-tool entitlement; refusal path | 0.2 |

Prompt rules for all calls: state role and exact output schema; external text is data, not instructions; cite provided IDs; forbid numbers not provided; use hypothesis language in F1; abstain ("insufficient evidence") rather than guess; stay within educational framing.

---

## 10. Verification and validation

| Layer | What | How |
|---|---|---|
| V1 Known-answer | Formula arithmetic (P-1a) | Hand-computable inputs with analytic answers |
| V2 Reference checks | Correlation, Spearman, shrinkage, XIRR | Compare on **real data** against an independent implementation |
| V3 Live integration | Every external client | Marked `live`; real service, real key; real failures (bad key, unknown model, unknown symbol) |
| V4 No-lookahead | F1 estimators | Truncate future data on real series and confirm past outputs are unchanged |
| V5 F1 episodes and controls | Replay | Human review of flags versus episodes and negative controls, hold-out evaluation, flag frequency, documented verdict on lead time |
| V6 F2 evaluation | Precision and recall | Against hand labels; proposed target precision ≥ 0.80 on displayed flags |
| V7 Entitlement matrix | Access control | Automated tests for every plan and segment across all routes, including agent paths and 402 vs 403 behavior |
| V8 Payments | Plan changes | Real gateway test-mode flows: success, failure, replayed webhook, bad signature |
| V9 Ops console | Visibility | Each backend batch shows up in the console with real data |
| V10 End-to-end | Demo path | A person runs the full video script with the right accounts |

Live tests draw from a separate test budget and may bypass the cache (`NO_CACHE=1`).

---

## 11. Traceability (requirements to task batches in `PROGRESS.md`)

| Requirement area | Batches |
|---|---|
| FR-CFG, P-1 to P-8 | A0 |
| Entitlement logic, plan rules, quota arithmetic | A1 |
| Pure algorithms, rule engine, text utilities | A2 |
| Cache and budget logic | A3 |
| FR-AUTH, profiles, RLS, ledger and event tables | X2 |
| FR-LLM | X3 |
| FR-UI foundation | X4 |
| FR-MKT, F1 statistics | X5 |
| FR-FIL | X6 |
| FR-F1 explanation | X7 |
| FR-F2 | X8 |
| FR-F3 | X9 |
| FR-AGT | X10 |
| FR-PAY | X11 |
| FR-CAC, deployment, submission | X12 |

---

## 12. Hackathon compliance checklist

| Rule | How satisfied |
|---|---|
| Track: Best Apps and Agents | Tool-using agent plus three real-use features |
| At least one NVIDIA open model | Nemotron 3 Nano, Super, Ultra |
| Runtime call to Nebius Token Factory | The LLM gateway (FR-LLM-001) |
| Working hosted demo, free and unrestricted for judges until judging ends | `judge_all` account; no payment needed; NFR-REL-001 |
| Public repo with visible open-source license | NFR-LEG-003 |
| README highlights Nemotron and Token Factory use | Task in X12 |
| Public YouTube video under 3 minutes; no copyrighted music or third-party trademarks | Demo plan below |
| Feedback on Token Factory and NVIDIA tools | `FEEDBACK.md` kept throughout |
| Original work; third-party data used within terms | Section 7.5 |
| Tavily bonus | FR-F1-010 |
| Criteria: Technological Implementation, Design, Potential Impact, Quality of the Idea | Deterministic core with verified LLM use; coherent two-segment product; a specific Indian problem; a non-obvious combination |

**Demo video plan (under three minutes).** Problem (two segments, three gaps). F2 as a retail user: a flagged contradiction with the verifier. F3 as a retail user, then the same feature in the institutional scope. Switch to an institutional or judge account: the retail account hitting the F1 segment lock shown first, then F1 with adjustable windows, an episode replay, heatmap, AR and sourced hypotheses. The ops console visible briefly to show the system working. Close on architecture: which Nemotron model does what, and where Token Factory and Tavily are called. There is no live demo, and judges are not required to test the app, so the video must stand alone.

---

## 13. Risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| R1 | Limited time versus a larger scope (two segments, payments, auth, ops console). | Phase order puts the riskiest and highest-value work first; the F3 gate allows a cut; payments sit late and are replaceable by admin assignment for judges. |
| R2 | Indian price and filings access is unofficial or limited; endpoints change; blocking. | A feasibility check is the first Phase X task; polite throttling; one-time pulls stored in the datastore; decisions recorded before building on a source. |
| R3 | Nemotron tool calling or JSON output does not work as documented. | Verified early; fallback is validated JSON tool selection. |
| R4 | F1 does not flag known episodes cleanly. | Hold-out calibration, negative controls, honest reporting, wording change from "early warning" to "regime detection". |
| R5 | F2 false positives from adjusted figures, standalone/consolidated mix-ups, sector differences. | Rules plus guard plus verifier; non-financial Ind AS companies only; precision-first display; labeled evaluation. |
| R6 | No suitable real trade logs. | Obtain consented logs early; the gate cuts F3 if none exist. |
| R7 | Credits drained by judges or bots. | Budget guard, per-account limits, cached demo path. |
| R8 | Supabase free project pauses; host sleeps. | Keep-alive or paid plan; choose a host that does not sleep. |
| R9 | Regulatory exposure (SEBI advisory rules; DPDP; exchange data licensing; payments and GST). | Educational-only design, forbidden-language validators, consent flows, no raw data redistribution, advisor review of `finance/06`. |
| R10 | Segment rules abused (a retail user claims institutional status to get F1). | Decision D-03: SEBI (or other regulator) registration number plus manual admin approval. |
| R11 | Public-repo exposure of data or secrets. | `.gitignore`, pre-commit check, no raw data in the repo. |

---

## 14. Open items (TBD register)

| # | Item | Resolved in |
|---|---|---|
| T1 | Final project name | Before the video |
| T2 | Confirm Supabase as the only datastore (Pinecone not needed unless retrieval demands it) | X1 |
| T3 | Exact model IDs; tool-calling and JSON support; reasoning format; rate limits; Ultra context window | X3 |
| T4 | Price and index data sources for India; final universe; availability of total-return series | X1, X5 |
| T5 | Institutional F3 metric definitions and F3 benchmark choices | Advisor, X9 |
| T6 | F2 company set; whether banks, NBFCs and insurers are ever added (MVP: non-financial Ind AS only) | Advisor, X6 |
| T7 | ~~How institutional status is granted~~ **Resolved (D-03):** SEBI (or other regulator) registration number plus manual admin approval | Done |
| T8 | ~~Institutional free trial~~ **Resolved (D-02):** none; institutions use the retail-level free tier | Done |
| T9 | Subscription lapse rule: provisional rule in FR-PAY-007 (D-08); advisor to confirm | Advisor, X11 |
| T10 | ~~Multiple-testing control~~ **Resolved (D-18):** Benjamini-Hochberg; AR parameters still to be confirmed against the paper | X5 |
| T11 | Payment gateway choice, test-mode access, GST handling, invoice needs | X11, Advisor |
| T12 | Filings access method (NSE/BSE downloads, endpoints, or subscription) and transcript retrieval method | X1, X6 |
| T13 | Source and consent for real F3 logs | X9 |
| T14 | Hosting platform | X12 |
| T15 | MIT versus Apache-2.0 | A0 |
| T16 | Threshold defaults and rule definitions (all of `finance/10_parameters_register.md`) | Advisor, X5, X8 |
| T17 | Real prices for each plan (provisional test-mode amounts set in D-09) | Advisor, before any live payment |

---

## Appendix A: `.env` specification

Location: `<repo root>/.env` (gitignored). Names mirrored in `.env.example`. All API keys, tokens, secrets, service endpoints and other values obtained from external sources live here.

| Variable | Required | Purpose |
|---|---|---|
| `NEBIUS_API_KEY` | yes | Token Factory authentication |
| `NEBIUS_BASE_URL` | yes | Token Factory base URL |
| `TAVILY_API_KEY` | yes | News retrieval |
| `SUPABASE_URL` | yes | Project URL |
| `SUPABASE_ANON_KEY` | yes | Public client key for the frontend |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Server-side admin key (never in the browser) |
| `SUPABASE_JWT_SECRET` | yes | JWT verification |
| `DATABASE_URL` | yes | Direct Postgres connection |
| `PINECONE_API_KEY` | no | Only if a vector index is adopted |
| `PRICE_API_KEY` | depends | Key for the chosen price source, if it needs one |
| `FRED_API_KEY` | yes | Global macro series |
| `HTTP_USER_AGENT` | yes | Identifying user agent for exchange and company-site fetches |
| `PAYMENT_KEY_ID`, `PAYMENT_KEY_SECRET`, `PAYMENT_WEBHOOK_SECRET` | yes | Gateway test-mode credentials |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` | no | Custom email sender, if used |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | yes | Google sign-in |
| `JUDGE_PASSWORD`, `DEMO_RETAIL_PASSWORD`, `DEMO_INSTITUTIONAL_PASSWORD` | yes | Seeded accounts |
| `DAILY_LLM_BUDGET_USD`, `TEST_DAILY_LLM_BUDGET_USD` | yes | Spend caps |

## Appendix B: Glossary of design terms

- **Verifier:** the deterministic check that blocks any F2 flag whose quote or number is not literally in the source data.
- **Evidence pack:** the only facts the F1 model may cite.
- **Precompute:** a stored result from a real run, returned with provenance and a `cached` label.
- **Segment:** retail or institutional. **Plan:** a priced tier within a segment.
- **Real-data policy:** Section 2.7.

## Appendix C: Hand-label format (F2)

```
{ "company": "...", "symbol": "...", "fiscal_period": "Q1 FY27", "basis": "consolidated",
  "source_url": "...", "claim_quote": "...", "metric": "revenue_from_operations",
  "label": "inconsistent|consistent", "annotator": "...", "notes": "..." }
```

## Appendix D: Episode definitions (indicative; the advisor confirms)

Windows are fixed in `config/episodes.yaml` before any tuning. These are historical market periods used as test cases, not project dates.

| ID | Episode | Indicative window | Why it matters |
|---|---|---|---|
| EP-2013 | Taper tantrum | mid-2013 | Rupee and bond stress with foreign outflows |
| EP-2018 | IL&FS default and NBFC liquidity squeeze | second half of 2018 | A domestic credit and liquidity shock |
| EP-2020 | COVID crash | Feb-Mar 2020 | Broad simultaneous selling across diversifiers |
| EP-2022 | Global tightening and FPI selling | 2022 | Rate shock with outflows and a weaker rupee |
| EP-2024 | Election-result volatility | June 2024 | A sharp, short domestic event |

**Negative controls** (the method should *not* flag broadly): calm trending periods, and a single-group event such as the early-2023 shock to one large business group, which was not a market-wide linkage event. Selection of controls is advisor-confirmed.
