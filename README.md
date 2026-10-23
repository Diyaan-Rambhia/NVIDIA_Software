# FinInsight

FinInsight is a forensic financial intelligence and audit platform for Indian equities.
The platform analyzes stocks on the National Stock Exchange (NSE) and Bombay Stock Exchange (BSE).
It helps investors detect market contagion, verify disclosures against XBRL filings, and review trade logs.

**Disclaimer: Educational and research use only.**
FinInsight is strictly an analytical research tool.
It does not provide investment advice or price targets.
It does not issue buy, sell, or hold recommendations.
The system is not registered as a SEBI Research Analyst or Investment Adviser.

---

## 1. System Features

The platform provides three integrated features:
1. **Feature 1 — Market Contagion Detector:**
Calculates the systemic absorption ratio (AR) across Indian equity sectors.
Computes Forbes-Rigobon volatility-adjusted correlation shifts.
Applies moving-block bootstrap tests for statistical significance.
2. **Feature 2 — XBRL Filing Consistency Checker:**
Audits management announcements against official Ind AS quarterly XBRL filings.
Flags discrepancies using deterministic audit rules R0 through R7.
3. **Feature 3 — Investment Log Forensics:**
Analyzes historical trade logs.
Calculates portfolio XIRR against NIFTY 50 and SENSEX benchmark replays.
Evaluates behavioral process metrics including concentration HHI, portfolio turnover, and disposition effect (PGR and PLR).

---

## 2. Documentation Architecture

Normative technical and financial specifications reside in `project_docs/`:
- [project.md](file:///c:/Users/diyaa/OneDrive/Desktop/Nebius%20x%20NVIDIA/project_docs/project.md): System purpose, user segments, plans, quotas, hackathon compliance, and requirements register.
- [tech_stack.md](file:///c:/Users/diyaa/OneDrive/Desktop/Nebius%20x%20NVIDIA/project_docs/tech_stack.md): Software architecture, backend modules, database schema, contracts, endpoints, frontend, and tests.
- [finance_stack.md](file:///c:/Users/diyaa/OneDrive/Desktop/Nebius%20x%20NVIDIA/project_docs/finance_stack.md): Mathematical formulas, arithmetic examples, parameter register, and audit rules.

---

## 3. Installation and Setup

### 3.1 Prerequisites
- Python 3.11 or newer
- Git

### 3.2 Installation Steps
1. Install Python dependencies:
   ```bash
   make install
   ```
2. Configure pre-commit verification hooks:
   ```bash
   git config core.hooksPath .githooks
   ```
3. Create local environment configuration:
   ```bash
   cp .env.example .env
   ```
4. Configure operational variables in `.env`.

---

## 4. Environment Variables

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

---

## 5. Running the Application

### 5.1 Local Development Server
Start the FastAPI development server:
```bash
make run
```

### 5.2 Test Suite Execution
Execute the test suite:
```bash
make test
```

### 5.3 Configuration Verification
Check environment variable configuration and secrets:
```bash
make check-env
```

---

## 6. Architecture Boundaries: Verified vs Unverified

FinInsight isolates deterministic calculations from language model generation:

### 6.1 Verified Deterministic Core
- Contagion mathematics: PCA absorption ratio, Forbes-Rigobon adjustment, and block bootstrap.
- Accounting audits: XBRL XML extraction and tolerance-bound rules R0 to R7.
- Performance analytics: XIRR solver, benchmark replay, concentration HHI, turnover, and disposition effect.
- Security and access: JWT authentication, role entitlements, atomic daily quotas, and secret redaction.
- Guardrails: Prohibited advice lexicon filter and daily LLM budget enforcement.

### 6.2 Unverified Inference Boundaries
- Natural language generation from Nebius Token Factory endpoints.
- External web search retrieval through Tavily.
- Live database persistence under sustained external concurrency.

---

## 7. Data Limitations

1. **Unofficial price sources:** Daily equity prices use `yfinance` for development and demo mode. This relies on unofficial endpoints.
2. **No institutional flow data:** Programmatic feeds for FII and DII net investment flows are unavailable.
3. **Provisional risk-free rate:** The risk-free rate is set to 5.7281 percent from RBI press release 2026-2027/1326.
4. **Revenue and profit checks only:** Quarterly filing checks are scoped to revenue and profit. Quarterly filings omit cash flow statements.
5. **Google login and payments deferred:** Authentication uses email and password. Live payments are deferred.
6. **Synthetic demo log:** Generated for pipeline testing. Every demo row is tagged `SYNTHETIC_DEMO`.

---

## 8. Provisional Parameters

Every finance parameter is provisional, no advisor review (DECISIONS.md D-26):
1. **Absorption ratio component fraction:** `k_fraction` set to 0.20 in `config/parameters.yaml`.
2. **Institutional performance metrics:** Annualization factor 252 and risk-free series set to 91-day T-bill.
3. **XIRR solver parameters:** Bracket `[-0.99, 10.0]`, tolerance `1e-9`, and max iterations 200.
4. **Quotas:** Daily usage limits configured in `config/plans.yaml`.
5. **Sector growth baselines:** Growth floors configured in `config/thresholds.yaml`.
6. **Text chunker parameters:** `chunk_size` 1200 and `chunk_overlap` 150.

---

## 9. Frontend Web Application

The frontend application is in `frontend/web/`.
It is built with Next.js 15, React 19, and TypeScript.

### 9.1 Security and Proxy Routing
- **In-Memory Token Lifecycle:** Supabase JWT tokens reside exclusively in React runtime memory (`AuthContext`). Tokens never enter `localStorage`, `sessionStorage`, or cookies. Closing the page evaporates the token.
- **Backend API Proxy:** All API requests route through the prefix `/backend/:path*`. Next.js rewrites this prefix server-side to `BACKEND_URL/:path*`.
- **Zero-Backend Landing Page:** The landing page makes no backend calls and renders static content.

### 9.2 Running Frontend Locally
```bash
cd frontend/web
npm install
npm run dev
```

---

## 10. Glossary

- **AR:** Absorption Ratio measuring the fraction of variance explained by top principal components.
- **BSE:** Bombay Stock Exchange.
- **HHI:** Herfindahl-Hirschman Index measuring portfolio concentration.
- **Ind AS:** Indian Accounting Standards converged with IFRS.
- **NSE:** National Stock Exchange of India.
- **PGR / PLR:** Proportion of Gains Realized and Proportion of Losses Realized.
- **Provisional:** Working value adopted in code without human financial advisor review.
- **SEBI:** Securities and Exchange Board of India.
- **XBRL:** Extensible Business Reporting Language for electronic regulatory filings.
- **XIRR:** Extended Internal Rate of Return for irregular cash flows.
