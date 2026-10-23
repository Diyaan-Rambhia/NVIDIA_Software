# Technical Architecture and Implementation Stack

This document specifies the technical architecture, backend services, frontend application, and deployment specifications for FinInsight.
The platform runs on a modern Python and TypeScript stack.
All financial parameters operate as provisional baselines without human financial advisor review.

## 1. System Architecture and Layout

FinInsight uses a modular service architecture.
The architecture enforces strict separation between deterministic calculations and language model generation.
Language models never calculate financial numbers directly.
Mathematical algorithms execute in pure Python using NumPy, SciPy, and scikit-learn.
Language models summarize and explain the verified mathematical findings.

The codebase layout follows standard conventions:
```
├── backend/
│   ├── app/                 # FastAPI core application and services
│   └── tests/               # Unit and live verification test suites
├── config/                  # Declarative YAML registries
├── data/                    # Market data cache and raw filings (gitignored)
├── demo_data/               # Precomputed demo fixtures
├── docs/
│   ├── contracts/           # JSON Schema contract specifications
│   └── openapi.json         # Committed OpenAPI schema
├── frontend/
│   └── web/                 # Next.js TypeScript web application
├── migrations/              # Database migration SQL definitions
├── private/                 # Private keys and execution logs (gitignored)
├── project_docs/            # Normative project documentation
└── scripts/                 # Maintenance and verification scripts
```

## 2. Backend Module Directory

The backend codebase under `backend/app` contains the following modules:

| Module Path | Core Function |
|---|---|
| `app/__init__.py` | Backend module |
| `app/admin/router.py` | Admin verification review endpoints |
| `app/agent/__init__.py` | Agent loop and tool calling orchestrator |
| `app/agent/orchestrator.py` | Agent loop and tool calling orchestrator |
| `app/agent/router.py` | Agent loop and tool calling orchestrator |
| `app/agent/tools.py` | Agent loop and tool calling orchestrator |
| `app/auth/__init__.py` | Supabase JWT verification with ES256 JWKS |
| `app/auth/dependencies.py` | Supabase JWT verification with ES256 JWKS |
| `app/auth/exceptions.py` | Supabase JWT verification with ES256 JWKS |
| `app/auth/jwt.py` | Supabase JWT verification with ES256 JWKS |
| `app/auth/models.py` | Supabase JWT verification with ES256 JWKS |
| `app/auth/router.py` | Supabase JWT verification with ES256 JWKS |
| `app/config/__init__.py` | Backend module |
| `app/config/env.py` | Environment variable registry and loading |
| `app/config/loader.py` | YAML configuration loading and validation |
| `app/config/models.py` | Pydantic settings and config models |
| `app/contracts/__init__.py` | Strict Pydantic contract transfer schemas |
| `app/contracts/agent.py` | Agent loop and tool calling orchestrator |
| `app/contracts/common.py` | Strict Pydantic contract transfer schemas |
| `app/contracts/contagion.py` | Strict Pydantic contract transfer schemas |
| `app/contracts/filings.py` | Strict Pydantic contract transfer schemas |
| `app/contracts/portfolio.py` | Strict Pydantic contract transfer schemas |
| `app/data/__init__.py` | Backend module |
| `app/data/fiscal.py` | Indian fiscal calendar calculations |
| `app/data/returns.py` | Daily price returns and calendar alignment |
| `app/db/__init__.py` | PostgreSQL connection and migration runner |
| `app/db/connection.py` | PostgreSQL connection and migration runner |
| `app/db/migrate.py` | PostgreSQL connection and migration runner |
| `app/entitlements/__init__.py` | Role checks and atomic quota decrements |
| `app/entitlements/atomic.py` | Role checks and atomic quota decrements |
| `app/entitlements/decision.py` | Role checks and atomic quota decrements |
| `app/entitlements/guard.py` | Role checks and atomic quota decrements |
| `app/entitlements/router.py` | Role checks and atomic quota decrements |
| `app/features/__init__.py` | Backend module |
| `app/features/f1_contagion/__init__.py` | Contagion covariance and absorption ratio |
| `app/features/f1_contagion/bootstrap.py` | Contagion covariance and absorption ratio |
| `app/features/f1_contagion/estimators.py` | Contagion covariance and absorption ratio |
| `app/features/f1_contagion/explanation.py` | Contagion covariance and absorption ratio |
| `app/features/f1_contagion/pipeline.py` | Contagion covariance and absorption ratio |
| `app/features/f1_contagion/router.py` | Contagion covariance and absorption ratio |
| `app/features/f2_filings/__init__.py` | XBRL parser, metrics, and rules R0-R7 |
| `app/features/f2_filings/adjudication.py` | XBRL parser, metrics, and rules R0-R7 |
| `app/features/f2_filings/derived_metrics.py` | XBRL parser, metrics, and rules R0-R7 |
| `app/features/f2_filings/quote_verifier.py` | XBRL parser, metrics, and rules R0-R7 |
| `app/features/f2_filings/router.py` | XBRL parser, metrics, and rules R0-R7 |
| `app/features/f2_filings/rules.py` | XBRL parser, metrics, and rules R0-R7 |
| `app/features/f2_filings/text_chunker.py` | XBRL parser, metrics, and rules R0-R7 |
| `app/features/f2_filings/xbrl_parser.py` | XBRL parser, metrics, and rules R0-R7 |
| `app/features/f3_log/__init__.py` | Trade log ingestion, XIRR, and replay |
| `app/features/f3_log/institutional_metrics.py` | Trade log ingestion, XIRR, and replay |
| `app/features/f3_log/pipeline.py` | Trade log ingestion, XIRR, and replay |
| `app/features/f3_log/process_metrics.py` | Trade log ingestion, XIRR, and replay |
| `app/features/f3_log/review_llm.py` | Trade log ingestion, XIRR, and replay |
| `app/features/f3_log/router.py` | Trade log ingestion, XIRR, and replay |
| `app/features/f3_log/xirr.py` | Trade log ingestion, XIRR, and replay |
| `app/infra/__init__.py` | Backend module |
| `app/infra/budget_guard.py` | LLM daily dollar budget ceiling |
| `app/infra/cache_key.py` | SHA-256 prompt response caching key |
| `app/infra/cost_report.py` | Token and spend aggregation |
| `app/llm/__init__.py` | Token Factory client, tools, and ledger |
| `app/llm/cache.py` | Token Factory client, tools, and ledger |
| `app/llm/client.py` | Token Factory client, tools, and ledger |
| `app/llm/exceptions.py` | Token Factory client, tools, and ledger |
| `app/llm/guard.py` | Token Factory client, tools, and ledger |
| `app/llm/ledger.py` | Token Factory client, tools, and ledger |
| `app/llm/placeholder.py` | Token Factory client, tools, and ledger |
| `app/llm/registry.py` | Token Factory client, tools, and ledger |
| `app/llm/router.py` | Token Factory client, tools, and ledger |
| `app/llm/structured.py` | Token Factory client, tools, and ledger |
| `app/llm/tools.py` | Token Factory client, tools, and ledger |
| `app/logging.py` | JSON logging with 6-char secret redaction |
| `app/main.py` | FastAPI application entry and middleware setup |
| `app/ops/__init__.py` | Operational health and activity endpoints |
| `app/ops/routes.py` | Operational health and activity endpoints |
| `app/payments/__init__.py` | Payment contracts and webhook validation |
| `app/version.py` | Git hash code version discovery |

## 3. Configuration System

FinInsight manages configuration through environment variables and declarative YAML files.

### 3.1 Environment Registry and Group Validation
The system registers all supported environment variables in `backend/app/config/env.py`.
Variables belong to functional groups: core, supabase, llm, search, market_data, filings, payments, oauth, and seed.
Operational variables `APP_ENV` and `LOG_LEVEL` provide safe defaults.
Secret variables never receive default values.

### 3.2 Runtime Group Enablement
The file `config/runtime.yaml` specifies active functional groups.
Startup validation checks variables only for enabled groups.
This enables local test execution without external service credentials.

### 3.3 Declarative YAML Files
All analytical settings reside in declarative YAML files under `config/`:
- `parameters.yaml`: Contains 44 financial and window parameters.
- `thresholds.yaml`: Contains 11 sector growth baselines and audit tolerances.
- `plans.yaml`: Defines 5 subscription tiers and daily feature execution quotas.
- `universe.yaml`: Declares Indian market sectors and equity constituents.
- `episodes.yaml`: Defines historical market stress episodes.
- `lexicon.yaml`: Catalogs financial tone keywords and prohibited advice terms.
- `accounts.yaml`: Declares seeded evaluation accounts.
- `models.yaml`: Declares model aliases for Nebius Token Factory endpoints.

## 4. Data Contracts and Schemas

Contracts enforce strict data validation between services.
All contracts inherit from `StrictContractModel` (`extra="forbid"`).
The system exports JSON Schemas to `docs/contracts/`:

| Contract Model | Primary Fields | Provisional Fields |
|---|---|---|
| `AgentStep` | `duration_ms, est_cost_usd, input_summary, output_summary, status, ...` | None |
| `Claim` | `basis, descriptor, direction, end, metric, ...` | None |
| `ColumnMapping` | `charges, date, exchange, fees, marker, ...` | None |
| `CorrelationScan` | `absorption_ratio, ar_delta_std, as_of, code_version, episodes_status, ...` | Thresholds and solver bounds |
| `DecisionReview` | `benchmark_replays, disclaimer, institutional_metrics, is_synthetic_demo, parameters_used, ...` | Thresholds and solver bounds |
| `ErrorDetail` | `code, message, request_id, reset_time, upgrade_targets, ...` | None |
| `ErrorEnvelope` | `error` | None |
| `EvidenceItem` | `description, id, kind, source, values` | None |
| `EvidencePack` | `as_of, code_version, items, parameters_used, seed, ...` | None |
| `FilingMetric` | `basis, company, derived, fiscal_period, isin, ...` | Tolerance thresholds |
| `Hypothesis` | `evidence_supporting, evidence_weakening, mechanism_class, plausible_mechanism, retrieved_urls` | None |
| `Inconsistency` | `claim_quote, difference_value, explanation, filed_value, is_placeholder, ...` | Tolerance thresholds |
| `Portfolio` | `cash_balance, positions, total_cost, total_market_value, total_realized_pnl, ...` | None |
| `Trade` | `charges, date, exchange, fees, marker, ...` | None |
| `TradeLog` | `consent_given, end_date, is_retained, is_synthetic_demo, start_date, ...` | Thresholds and solver bounds |
| `WindowRange` | `baseline, current` | None |

## 5. API Endpoint Catalog

The backend exposes HTTP API endpoints documented in `docs/openapi.json`:

| Endpoint Path | Method | Auth Required | Operation Summary |
|---|---|---|---|
| `/` | `GET` | No | Root Redirect |
| `/agent/ask` | `POST` | No | Ask Agent |
| `/api/admin/verifications/{verification_id}/review` | `POST` | No | Review Verification |
| `/api/auth/me` | `GET` | No | Get Me |
| `/api/auth/refresh` | `POST` | No | Refresh Token |
| `/api/auth/signup` | `POST` | No | Signup |
| `/api/auth/token` | `POST` | No | Login |
| `/api/entitlements` | `GET` | No | Get User Entitlements |
| `/api/verifications` | `POST` | No | Submit Verification |
| `/console` | `GET` | No | Console Index |
| `/console/` | `GET` | No | Console Index |
| `/console/config.html` | `GET` | No | Console Config |
| `/console/index.html` | `GET` | No | Console Index |
| `/f1/scan` | `GET` | Yes | Systemic Contagion Scan |
| `/f2/companies` | `GET` | Yes | List NSE Companies |
| `/f2/lookup` | `GET` | Yes | Live Company Filing Lookup |
| `/f3/review` | `POST` | Yes | Review Trade Log |
| `/files/extract` | `POST` | Yes | Safe Document Extraction |
| `/health` | `GET` | No | Health |
| `/llm/runtime_call` | `POST` | No | Call Nemotron Runtime |
| `/llm/tavily_search` | `POST` | No | Search Tavily |
| `/ops/activity/events` | `GET` | No | Get Ops Activity Events |
| `/ops/activity/llm` | `GET` | No | Get Ops Activity Llm |
| `/ops/config` | `GET` | No | Get Ops Config |
| `/ops/parameters` | `GET` | No | Get Ops Parameters |
| `/ops/status` | `GET` | No | Get Ops Status |
| `/ready` | `GET` | No | Ready |

## 6. Authentication and Identity

FinInsight implements user authentication through Supabase Auth.
Users register and sign in using email and password credentials.
The backend validates Supabase JSON Web Tokens (JWT) using the ES256 algorithm.
Cryptographic validation uses Supabase JSON Web Key Sets (JWKS).
Administrative privileges read strictly from the `app_metadata` JWT claim.
User-controlled metadata cannot grant administrative access.

## 7. Database Tables and Row Level Security

The platform uses PostgreSQL hosted on Supabase.
All 9 operational tables enforce Row Level Security (RLS) policies:

| Table Name | Storage Scope | Row Level Security Rule |
|---|---|---|
| `plans` | Operational table for plans | Public read. Writes restricted to service role. |
| `profiles` | Operational table for profiles | Users read and update own profile. |
| `usage` | Operational table for usage | Users read own usage. Mutations restricted to backend. |
| `institutional_verifications` | Operational table for institutional_verifications | Users read and create own verification. Admin reviews. |
| `subscriptions` | Operational table for subscriptions | Users read own subscriptions. Admin and billing mutate. |
| `payments` | Operational table for payments | Users read own payments. Mutations restricted to webhook. |
| `llm_ledger` | Operational table for llm_ledger | Append-only by service role. Admin read access. |
| `results` | Operational table for results | Users read own results. Service role writes. |
| `events` | Operational table for events | System audit log. Service role writes. Admin reads. |

## 8. Entitlements and Quotas

FinInsight enforces plan entitlements before invoking feature logic:
- **Feature 1 (Contagion):** Available to `institutional_paid` and `judge_all`. Retail plans return HTTP 403 `denied`. Free institutional plans return HTTP 402 `upgrade_required`.
- **Feature 2 (Filings):** Available across plans up to daily quota limits.
- **Feature 3 (Trade Log):** Available across plans up to daily quota limits.

Daily quotas increment atomically in PostgreSQL using an upsert query:
```sql
INSERT INTO public.usage (user_id, feature, utc_date, count)
VALUES ($1, $2, CURRENT_DATE, 1)
ON CONFLICT (user_id, feature, utc_date)
DO UPDATE SET count = usage.count + 1
WHERE usage.count < $3;
```
If usage reaches the quota limit, zero rows update.
The endpoint immediately returns HTTP 429 `quota_exceeded` with reset timestamp.

## 9. LLM Gateway and Inference Infrastructure

The LLM gateway provides a controlled interface to AI inference.

### 9.1 Provider Routing and Endpoints
The gateway connects to Nebius Token Factory.
It targets NVIDIA Nemotron models through OpenAI-compatible interfaces.
If unconfigured in production, the gateway returns HTTP 503 `service_unavailable`.

### 9.2 Response Cache Key
The gateway computes a deterministic SHA-256 hash to cache responses:
$$\text{CacheKey} = \text{SHA256}(\text{Model} + \text{Prompt} + \text{Temperature} + \text{Tools})$$

### 9.3 Budget Guard and Cost Ledger
The budget guard enforces a daily expenditure ceiling in USD (`DAILY_LLM_BUDGET_USD`).
Every generation records token counts and cost in `public.llm_ledger`.
When cumulative daily cost exceeds the budget, further generation requests fail loud.

### 9.4 Placeholder Provider
A deterministic rule-based placeholder provider exists for offline testing.
The placeholder returns contract-compliant mock responses.
The system prohibits placeholder initialization when `APP_ENV=production`.

### 9.5 Multi-Step Agent Loop
The orchestrator in `backend/app/agent/orchestrator.py` runs multi-turn tool loops:
1. Receives user query.
2. Formulates tool-calling request to Nemotron model.
3. Validates tool arguments against strict Pydantic schemas.
4. Executes requested tool in local execution sandbox.
5. Feeds tool execution results back to model.
6. Terminates when model yields final answer or step limit is reached.

## 10. Frontend Web Application

The frontend application resides in `frontend/web/`.
It is built with Next.js 15, React 19, and TypeScript using App Router.

### 10.1 Proxy Architecture
All client communication routes through the prefix `/backend/:path*`.
Next.js rewrites this prefix server-side to `BACKEND_URL/:path*` (default `http://127.0.0.1:8000`).
This shields internal backend URLs from public exposure.

### 10.2 Page Catalog
- `/`: Static public landing page making zero backend calls.
- `/login`: Email and password login page.
- `/signup`: User registration and verification page.
- `/dashboard`: Overview of available tools and active plan.
- `/contagion`: Interactive sector contagion and absorption ratio view with full-width Tavily macro block situated between headline metrics and shifted asset pairs table.
- `/filings`: XBRL filing consistency audit interface featuring top company search field, quarter selector, Show button, dynamic demo population, match suggestions, and hosted demo live lookup gap notice (D-66).
- `/trade-log`: Trade history ingestion, XIRR analysis, and process metrics view.
- `/agent`: Focused chat interface with memory-only thread, bottom-anchored input, and compact clickable starter question chips positioned above the input box (hidden when messages exist).
- `/admin`: Administrative review panel with group-aware configuration variable display (muted when not enabled, warn when missing in enabled group, and SMTP variables hidden).
- `/account`: User subscription management and tier display.

### 10.3 Design System and Architecture Decisions
The UI applies a clean dark theme:
- Surface background: `#0d1117`.
- Panels and cards: `#161b22`.
- Positive indicators: `#238636`.
- Audit flags: `#da3633`.
- Typography: Self-hosted local Inter font loaded through `next/font/local`.
- Shared `TavilyRail` component renders external macro news context full width between metrics and shifted asset pairs on `/contagion` (D-64).
- External Tavily search integration is scoped exclusively to Feature 1 (D-65).
- Search on `/filings` dynamically extracts entities and fiscal periods from `/f2/demo` without hardcoded lists (D-66).

### 10.4 In-Memory Token Security
Supabase JWT access tokens reside exclusively in React runtime memory (`AuthContext`).
Tokens never touch `localStorage`, `sessionStorage`, cookies, or browser URLs.
Reloading or closing the browser tab immediately clears the session from memory.

## 11. Testing and Verification

FinInsight maintains automated verification across all layers:
- **Known-Answer Tests (394 tests):** Test pure algorithms, edge cases, Pydantic contracts, and rule evaluations against hand-computed fixtures. These run in under one minute without network access.
- **Live Integration Tests (22 tests):** Test live Supabase authentication, database RLS, and end-to-end API workflows.
  - 17 live tests pass cleanly.
  - 5 tests skip cleanly when optional upstream Token Factory keys remain unconfigured.
- **Documentation Verification:** `scripts/docs_check.py` verifies that all environment variables, endpoints, decisions, parameters, tables, contracts, and FR IDs appear in documentation.

## 12. Run, Docker and Deploy

### 12.1 Local Execution
Start backend services:
```bash
make install
cp .env.example .env
make run
```

Start frontend web application:
```bash
cd frontend/web
npm install
npm run dev
```

### 12.2 Docker Containerization
The repository includes a multi-stage `Dockerfile`:
```bash
docker build -t fininsight:latest .
docker run -p 8000:8000 --env-file .env fininsight:latest
```
The container runs as an unprivileged user (`appuser`).

### 12.3 Deployment Notes
- Secrets inject as environment variables at container startup.
- Host environments must provide network access to Supabase and Nebius Token Factory.
- Production deployments set `APP_ENV=production` to disable interactive docs and placeholder providers.

## 13. Environment Variables

The table below catalogs all 28 registered environment variables:

| Variable Name | Group | Secret | Required |
|---|---|---|---|
| `APP_ENV` | `core` | No | No |
| `LOG_LEVEL` | `core` | No | No |
| `NEBIUS_API_KEY` | `llm` | Yes | Yes |
| `NEBIUS_BASE_URL` | `llm` | No | Yes |
| `TAVILY_API_KEY` | `search` | Yes | Yes |
| `SUPABASE_URL` | `supabase` | No | Yes |
| `SUPABASE_ANON_KEY` | `supabase` | Yes | Yes |
| `SUPABASE_SERVICE_ROLE_KEY` | `supabase` | Yes | Yes |
| `SUPABASE_JWT_SECRET` | `supabase` | Yes | Yes |
| `DATABASE_URL` | `supabase` | Yes | Yes |
| `SUPABASE_PASSWORD` | `supabase` | Yes | Yes |
| `PRICE_API_KEY` | `market_data` | Yes | Yes |
| `FRED_API_KEY` | `market_data` | Yes | Yes |
| `HTTP_USER_AGENT` | `filings` | No | Yes |
| `PAYMENT_KEY_ID` | `payments` | Yes | Yes |
| `PAYMENT_KEY_SECRET` | `payments` | Yes | Yes |
| `PAYMENT_WEBHOOK_SECRET` | `payments` | Yes | Yes |
| `GOOGLE_OAUTH_CLIENT_ID` | `oauth` | No | Yes |
| `GOOGLE_OAUTH_CLIENT_SECRET` | `oauth` | Yes | Yes |
| `JUDGE_PASSWORD` | `accounts_seed` | Yes | Yes |
| `DEMO_RETAIL_PASSWORD` | `accounts_seed` | Yes | Yes |
| `DEMO_INSTITUTIONAL_PASSWORD` | `accounts_seed` | Yes | Yes |
| `DAILY_LLM_BUDGET_USD` | `budget` | No | Yes |
| `TEST_DAILY_LLM_BUDGET_USD` | `budget` | No | Yes |
| `PINECONE_API_KEY` | `optional` | Yes | No |
| `SMTP_HOST` | `optional` | No | No |
| `SMTP_USER` | `optional` | No | No |
| `SMTP_PASSWORD` | `optional` | Yes | No |

## 14. Policies and Work Process

FinInsight enforces strict engineering policies:
1. **Real-Data Policy:** No mocks, fakes, or synthetic fixtures standing in for live external services.
2. **Secrets & Storage:** Secrets live in `.env`. Logs and market data live in `private/` and `data/`.
3. **No Dates Anywhere:** Never write dates, timestamps, or release dates in code, comments, or documentation.
4. **Filesystem Paths:** Use Python's `pathlib` module exclusively. Do not use `os.path`.
5. **Dependencies:** Do not add dependencies without recording a rationale in `DECISIONS.md`.
6. **Loud Failures:** Surface upstream errors with their real status and message. No silent fallbacks.
7. **India Market Context:** Instruments, exchanges (NSE/BSE), currency (INR), fiscal calendar, and SEBI apply.
8. **Configurability:** Analytical thresholds and parameters must come from configuration, never hardcoded.
9. **Secret Redaction:** Redact any secret of 6 or more characters in logs.
10. **Pre-commit Scanning:** `scripts/precommit_check.py` blocks staging secrets or gitignored directories.

## 15. Architecture Decisions Index

The table below indexes all 63 decisions recorded in `DECISIONS.md`:

| Decision ID | Summary Title |
|---|---|
| `DECISIONS.md D-01` | Minimal package skeleton for Phase A0 |
| `DECISIONS.md D-02` | Core and development dependencies |
| `DECISIONS.md D-03` | Pre-commit secret scanning policy |
| `DECISIONS.md D-04` | Strict Pathlib usage |
| `DECISIONS.md D-05` | Staged configuration validation and secret redaction |
| `DECISIONS.md D-06` | Default values for core non-secret operational variables |
| `DECISIONS.md D-07` | Static configuration loading and parameter resolution (A0.4) |
| `DECISIONS.md D-08` | Deferral of contract model definitions pending batch implementation (A0.5) |
| `DECISIONS.md D-09` | Filesystem git hash lookup with explicit fallback for code version (A0.6) |
| `DECISIONS.md D-10` | Interim development environment guard for ops console (A0.8) |
| `DECISIONS.md D-11` | Alignment of plans configuration with project_docs/01_project.md specifications (A1) |
| `DECISIONS.md D-12` | Transition to daily quotas and configurable reset cadence (A1) |
| `DECISIONS.md D-13` | Canonical Indian fiscal period format and trading calendar alignment policy (A2.1) |
| `DECISIONS.md D-14` | NumPy dependency for array and matrix computations (A2.2) |
| `DECISIONS.md D-15` | SciPy dependency for rank correlation and statistics (A2.2) |
| `DECISIONS.md D-16` | scikit-learn dependency for Ledoit-Wolf covariance shrinkage (A2.2) |
| `DECISIONS.md D-17` | Pure estimator conventions, parameters, and pending values (A2.2) |
| `DECISIONS.md D-18` | Standard day-count basis named constant for XIRR (A2.3) |
| `DECISIONS.md D-19` | Moving-block bootstrap algorithm and output conventions (A2.3) |
| `DECISIONS.md D-20` | XIRR solver parameters, multiple roots handling, and pending values (A2.3) |
| `DECISIONS.md D-21` | Process metrics definitions and conventions (A2.4) |
| `DECISIONS.md D-22` | Institutional performance metrics and pending parameters (A2.4) |
| `DECISIONS.md D-23` | Derived filing metrics and validation constraints (A2.4) |
| `DECISIONS.md D-24` | Text chunker, verbatim-quote check, and rule engine R0-R7 (A2.5) |
| `DECISIONS.md D-25` | Infrastructure logic (response-cache key, budget guard, cost report, Dockerfile) (A3) |
| `DECISIONS.md D-26` | Resolution of provisional configuration parameters |
| `DECISIONS.md D-27` | Feasibility evaluation of external data sources (X1 feasibility) |
| `DECISIONS.md D-28` | Price data scope - yfinance only (unofficial, demo only) |
| `DECISIONS.md D-29` | Institutional flow data scope - omission from macro factor attribution |
| `DECISIONS.md D-30` | Feature 2 quarterly XBRL scope - limited to revenue and profit checks |
| `DECISIONS.md D-31` | Feature 2 commentary text source - claims sourced from announcement PDFs |
| `DECISIONS.md D-32` | Risk-free rate configuration - required config entry with null value |
| `DECISIONS.md D-33` | Broker API price source evaluation (Zerodha, Upstox, Angel One, Fyers) |
| `DECISIONS.md D-34` | Separation of SUPABASE_PASSWORD from DATABASE_URL in environment registry |
| `DECISIONS.md D-35` | Risk-free rate configuration entry and RBI 91-day T-bill benchmark |
| `DECISIONS.md D-36` | PostgreSQL database driver dependency selection (psycopg) |
| `DECISIONS.md D-37` | Plans database table duplication of plans.yaml |
| `DECISIONS.md D-38` | Deferral of subscriptions and payments mutation to X11 |
| `DECISIONS.md D-39` | Deferral of Google OAuth due to card requirement |
| `DECISIONS.md D-40` | JWT signature verification via Supabase JWKS public keys (ES256) |
| `DECISIONS.md D-41` | Email verification enforcement returning 403 email_not_verified |
| `DECISIONS.md D-42` | Admin authorization read strictly from app_metadata |
| `DECISIONS.md D-43` | Atomic database quota increment via PostgreSQL conditional upsert |
| `DECISIONS.md D-44` | Provisional seed accounts configuration and credentials lifecycle |
| `DECISIONS.md D-45` | Production admin authorization guard superseding D-10 interim guard (X4) |
| `DECISIONS.md D-46` | CorrelationScan contract definition, market data caching, and XBRL filings ingestion (X5/X6) |
| `DECISIONS.md D-47` | Feature 3 pending contracts definition (ColumnMapping, TradeLog, Portfolio, DecisionReview) |
| `DECISIONS.md D-48` | Frontend technology selection: Plain HTML/CSS/JS without framework or CDN |
| `DECISIONS.md D-49` | Feature 3 trade log processing and benchmark replay pipeline |
| `DECISIONS.md D-50` | Owner-approved exception for synthetic demo trade log |
| `DECISIONS.md D-51` | Owner-approved exception for rule-based placeholder LLM provider |
| `DECISIONS.md D-52` | Inconsistency contract definition for Feature 2 adjudication |
| `DECISIONS.md D-53` | Unauthenticated /console/ static asset serving and /app root redirect |
| `DECISIONS.md D-54` | Initial render unauthenticated state and in-panel error reporting for /app/ and /console/ |
| `DECISIONS.md D-55` | Production guard for administrative role elevation script |
| `DECISIONS.md D-56` | Multi-step agent orchestrator loop, tool registry, and entitlement guards (Batch X10) |
| `DECISIONS.md D-57` | Hosted demo mode for Feature 3 benchmark isolation |
| `DECISIONS.md D-58` | Unconfigured LLM provider in production HTTP 503 response and README env drift enforcement |
| `DECISIONS.md D-59` | Frontend web application architecture and proxy prefix |
| `DECISIONS.md D-60` | In-memory token storage lifecycle |
| `DECISIONS.md D-61` | Frontend development dependencies |
| `DECISIONS.md D-62` | Admin verification queue manual UUID entry and backend endpoint gap |
| `DECISIONS.md D-63` | Self-hosted local font loading via next/font/local |
| `DECISIONS.md D-64` | Feature 1 Tavily news integration gap in precomputed demo and TavilyRail component |
| `DECISIONS.md D-65` | Tavily scope restriction to Feature 1 |
| `DECISIONS.md D-66` | Hosted demo filings search and live company lookup backend gap |
| `DECISIONS.md D-67` | openpyxl dependency addition for spreadsheet extraction |
| `DECISIONS.md D-68` | python-docx dependency addition for Word document extraction |
| `DECISIONS.md D-69` | pypdf dependency addition for PDF report extraction |
| `DECISIONS.md D-70` | yfinance dependency addition for live market and benchmark prices |
| `DECISIONS.md D-71` | Contract change: AgentAskRequest model tier and reference text |
| `DECISIONS.md D-72` | Contract change: Authentication refresh token and endpoint |
| `DECISIONS.md D-73` | Live NSE corporate filing lookup, rate limiting, and caching |
| `DECISIONS.md D-74` | Annual-only rule restriction for operating cash flow and working capital |
| `DECISIONS.md D-75` | File extraction safety, macro rejection, and zip bomb defenses |
| `DECISIONS.md D-76` | Feature 3 trade log upload in hosted mode |
| `DECISIONS.md D-77` | react-markdown dependency addition for safe plain-prose formatting |
| `DECISIONS.md D-78` | Session management via httpOnly cookies with 5-hour idle timeout |
| `DECISIONS.md D-79` | Model tier catalog endpoint gap |
| `DECISIONS.md D-80` | Request origin verification with Host comparison and protocol-aware cookie flags |
| `DECISIONS.md D-81` | Intentional frontend deprecation of legacy LLM endpoints |
| `DECISIONS.md D-82` | Deletion of legacy plain HTML screens (frontend/app) and demo endpoints |

## 16. Technical Glossary

- **ES256:** Asymmetric cryptographic algorithm using NIST P-256 curve and SHA-256.
- **FastAPI:** Asynchronous web framework for Python.
- **JWKS:** JSON Web Key Set containing public cryptographic keys.
- **JWT:** JSON Web Token for transmitting secure claims.
- **Ledger:** Append-only database table tracking LLM token consumption and dollar cost.
- **Nebius Token Factory:** Cloud AI inference service providing NVIDIA Nemotron models.
- **Next.js:** React framework for production web applications.
- **OpenAPI:** Standard specification format for RESTful HTTP APIs.
- **Proxy Rewrite:** Server-side redirection of client requests to backend API endpoints.
- **Pydantic v2:** Data validation library using Python type annotations.
- **RLS:** Row Level Security in PostgreSQL controlling per-user row visibility.
- **Supabase:** Cloud platform providing PostgreSQL database and authentication.
- **Upsert:** Atomic database operation that inserts or updates an existing row on conflict.

