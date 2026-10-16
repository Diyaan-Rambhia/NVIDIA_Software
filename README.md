# FinInsight

FinInsight is a forensic financial intelligence and audit platform for Indian equities (NSE/BSE). It assists analysts and investors in detecting systemic market contagion, cross-checking company disclosures against XBRL filings, and reviewing personal investment logs for behavioral pitfalls.

**Disclaimer: Educational and research use only.** FinInsight is strictly an analytical and educational research tool. It does not provide investment recommendations, financial advice, price targets, or buy/sell/hold calls. It is not registered as a SEBI Research Analyst or Investment Adviser.

---

## What It Is

The system provides three integrated features:
1. **Feature 1 — Market Contagion & Systemic Stress:** Estimates systemic absorption ratio (AR), Forbes-Rigobon volatility-adjusted correlation shifts, and moving-block bootstrap significance across Indian equity sectors.
2. **Feature 2 — XBRL Filing Consistency:** Audits management press releases and disclosure claims against official Ind AS quarterly XBRL filings, flagging discrepancies with deterministic rule checks (R0-R7).
3. **Feature 3 — Investment Log Forensics:** Analyzes trade execution history, calculates portfolio XIRR against benchmark replays (NIFTY 50, SENSEX), and evaluates behavioral process metrics (concentration HHI, portfolio turnover, disposition effect PGR/PLR, and maximum drawdown).

---

## Setup & Local Run

### Prerequisites

- Python 3.11+
- Git

### Installation

```bash
make install
```

Configure pre-commit hooks:

```bash
git config core.hooksPath .githooks
```

Copy the environment template:

```bash
cp .env.example .env
```

Fill in required operational variables in `.env` (kept strictly gitignored).

### Environment Variables

<!-- ENV_VARS_START -->
#### Always Needed on a Host
- `APP_ENV`
- `LOG_LEVEL`

#### Needed per Group
##### Supabase
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `DATABASE_URL`
- `SUPABASE_PASSWORD`

##### LLM
- `NEBIUS_API_KEY`
- `NEBIUS_BASE_URL`

##### Search
- `TAVILY_API_KEY`

##### Budget
- `DAILY_LLM_BUDGET_USD`
- `TEST_DAILY_LLM_BUDGET_USD`

#### Seed-Script Only
- `JUDGE_PASSWORD`
- `DEMO_RETAIL_PASSWORD`
- `DEMO_INSTITUTIONAL_PASSWORD`

#### Not Used Yet
##### Payments
- `PAYMENT_KEY_ID`
- `PAYMENT_KEY_SECRET`
- `PAYMENT_WEBHOOK_SECRET`

##### OAuth
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`

##### Market Data
- `PRICE_API_KEY`
- `FRED_API_KEY`

##### Filings
- `HTTP_USER_AGENT`

##### Optional
- `PINECONE_API_KEY`
- `SMTP_HOST`
- `SMTP_USER`
- `SMTP_PASSWORD`
<!-- ENV_VARS_END -->

### Running Locally

Run development server:

```bash
make run
```

Run test suite:

```bash
make test
```

Check configuration and secrets:

```bash
make check-env
```

---

## Architecture: Verified vs Unverified Boundary

FinInsight is designed with strict mathematical isolation between deterministic audit pipelines and semi-agentic language models:

- **Verified (Deterministic Core):**
  - Contagion math: PCA absorption ratio, Forbes-Rigobon adjustment, moving-block bootstrap.
  - Accounting checks: XBRL XML extraction, metric normalization, tolerance-bound rules R0-R7.
  - Performance math: Newton-Raphson / bisection XIRR solver, benchmark time-series alignment, HHI concentration, turnover, disposition effect.
  - Security & access: HMAC/JWT verification, role and tier entitlement enforcement, atomic quota decrements, secret redaction filter.
  - Guardrails: Prohibited financial advice filter (lexicon-backed), budget cap enforcement, response caching.

- **Unverified (Pending Upstream Verification):**
  - **Nemotron runtime output:** Live generation via Nebius Token Factory inference endpoints.
  - **Tool calling on Token Factory:** Upstream function-calling mechanics for Nemotron models.
  - **JSON schema structured output:** Native structured output enforcement on Token Factory.
  - **Tavily search:** Live external news retrieval (fails cleanly with explicit error when key is unconfigured).
  - **Live external database:** Production Supabase Postgres instance under sustained concurrency.

---

## Data Limitations

1. **Unofficial price sources:** Daily equity and benchmark prices are sourced via `yfinance` for development and demo mode. This relies on unofficial endpoints that are subject to schema changes, unannounced rate limiting, and Terms of Service constraints prohibiting commercial use.
2. **No institutional flow data:** Programmatic feeds for FII/DII and FPI net investment flows from NSDL and NSE are unavailable; institutional flow factors are omitted from contagion macro factor attribution.
3. **Provisional risk-free rate:** The risk-free rate configuration entry in `config/parameters.yaml` is provisional with a null value and pending status. Calculations requiring sovereign yield use explicit fallback parameter configuration.
4. **Revenue and profit checks only:** Automated quarterly filing consistency checks (Feature 2) are scoped exclusively to revenue from operations and profit metrics (PBT, PAT, EPS) from quarterly Ind AS XBRL filings. Balance sheet receivables and cash flow statement metrics are not present in quarterly filings.
5. **Google login and payments not implemented:** Google OAuth authentication and live payment gateway processing are not implemented; authentication is scoped to Supabase email signup with email verification, and payments are mocked/stub-free with judge accounts granted free access.
6. **Synthetic demo log:** Generated by `scripts/make_demo_trade_log.py` using real trading dates and close prices from `data/yfinance/` to evaluate Feature 3 pipeline mechanics without collecting real investor data. Explicitly labeled `SYNTHETIC_DEMO` on every row and marked in pipeline results; rejected under real-log retention consent.

---

## Provisional Parameters, Not Reviewed by a Finance Professional

Educational only. The following values are provisional working parameters pending formal financial advisor review (DECISIONS.md D-26):
1. **Absorption ratio component count:** `k_fraction` 0.20 in `config/parameters.yaml` (`k` derived as `max(1, ceil(N * 0.20))`).
2. **Institutional performance metrics:** Daily return frequency, annualisation factor 252, and risk-free series "91-day T-bill yield".
3. **XIRR solver configuration:** Bracket `[-0.99, 10.0]`, tolerance `1e-9`, max iterations 200, grid points 1000.
4. **Quotas:** `institutional_paid` Feature 3 daily quota set to 5 (5x the `institutional_free` daily quota).
5. **Sector growth thresholds:** Conservative YoY strong-growth baseline floors in `config/thresholds.yaml` (FMCG 6%, IT services 8%, Autos 10%, Capital goods 12%, Metals 10%, Energy 8%, Telecom 8%, Consumer durables 10%, Other 8%), with provisional threshold labelling applied to candidate flags.
6. **Text chunker parameters:** `chunk_size` 1200 and `chunk_overlap` 150 in `config/parameters.yaml` (DECISIONS.md D-26).

---

## Frontend Web Application

A Next.js (TypeScript, App Router) frontend is located in `frontend/web/`.

### Architecture & Security
- **In-Memory Token Lifecycle:** Supabase JWT session tokens are held exclusively in React runtime memory (`AuthContext`). Tokens are never written to `localStorage`, `sessionStorage`, cookies, URLs, or console logs. Reloading the page clears the session by design.
- **Backend API Proxy:** All API communication uses the single prefix `/backend/:path*`, rewritten server-side in `next.config.ts` to `BACKEND_URL/:path*` (default `http://127.0.0.1:8000`).
- **Zero-Backend Landing Page:** The landing page makes no backend calls and renders purely static educational and overview content.
- **Navigation:** All internal navigation uses `next/link` to preserve in-memory token state across views.

### Running Frontend Locally

```bash
cd frontend/web
npm install
npm run dev
```

### Verification & Testing

```bash
cd frontend/web
npm run typecheck
npm run lint
npm run test
npm run build
```

