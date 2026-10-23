# Project Specification and Functional Requirements

FinInsight is a forensic financial intelligence and audit platform for Indian equities.
The platform operates as an educational and research tool.
No financial advisor review exists.
Every finance value is provisional, no advisor review.

## 1. Purpose and Problem

Indian financial markets feature growing retail participation and complex institutional linkages.
Investors face two critical challenges:
1. **Unverified Management Claims:** Corporate disclosures often highlight selective operational metrics that contradict official regulatory filings.
2. **Hidden Systemic Fragility:** Asset correlations spike abruptly during stress episodes, causing unexpected portfolio drawdowns.

FinInsight solves these problems through deterministic mathematical verification and automated filing cross-checking.

## 2. Users and the Two Segments

The platform serves two distinct user segments with dedicated access boundaries:

### 2.1 Retail Investors
- Individual market participants investing personal capital.
- Primary need: Auditing corporate management claims against official quarterly filings (Feature 2).
- Secondary need: Evaluating personal trading history and behavioral biases (Feature 3).

### 2.2 Institutional Asset Managers
- Portfolio managers, Alternative Investment Funds (AIF), family offices, and treasuries.
- Primary need: Monitoring systemic stress and sector contagion across Indian equities (Feature 1).
- Secondary need: Evaluating institutional performance metrics and benchmark tracking (Feature 3).

## 3. Core Feature Specifications

FinInsight provides three core features:

### 3.1 Feature 1: Market Contagion Detector (Institutional)
- **What it does:** Scans cross-sector Indian equities for systemic coupling and correlation breakdown.
- **Inputs:** Daily adjusted close price series for sector universe constituents.
- **Outputs:** Systemic absorption ratio, Forbes-Rigobon adjusted correlation shifts, and bootstrap p-values.
- **Operational limits:** Uses daily closing prices; intraday tick data is not supported.

### 3.2 Feature 2: Filing Consistency Checker (Retail)
- **What it does:** Cross-checks management announcements against official Ind AS quarterly XBRL filings.
- **Inputs:** Management press release PDF or text and official quarterly XBRL filing.
- **Outputs:** Inconsistency findings table with exact quote citations, rule tags (R0 to R7), and discrepancies.
- **Operational limits:** Scoped to revenue from operations and profit metrics; quarterly filings omit balance sheet cash flows.

### 3.3 Feature 3: Investment Log Advisor (Both Segments)
- **What it does:** Reviews trade execution logs to assess investment return and behavioral discipline.
- **Inputs:** Standardized trade log containing trade dates, ticker symbols, quantities, and execution prices.
- **Outputs:** Portfolio XIRR, benchmark replays (NIFTY 50 and SENSEX), and behavioral process metrics (HHI, turnover, disposition effect).
- **Operational limits:** Evaluates historical execution discipline only; does not predict future prices or provide trade advice.

## 4. Plans, Access Rules, and Quotas

FinInsight implements a multi-tier subscription model defined in `config/plans.yaml`:

| Plan Name | Segment | Feature 1 Quota | Feature 2 Quota | Feature 3 Quota |
|---|---|---|---|---|
| `institutional_free` | `institutional` | 0/day | 0/day | 0/day |
| `institutional_paid` | `institutional` | 0/day | 0/day | 0/day |
| `judge_all` | `internal` | 0/day | 0/day | 0/day |
| `retail_free` | `retail` | 0/day | 0/day | 0/day |
| `retail_paid` | `retail` | 0/day | 0/day | 0/day |

### 4.1 Daily Quotas and Reset Rules
Quotas enforce daily execution limits per user and feature.
All quotas reset automatically at midnight Coordinated Universal Time (00:00 UTC).
Usage tracking uses atomic PostgreSQL upsert queries.

### 4.2 Standard HTTP Error Codes
- **401 Unauthorized:** Missing, expired, or invalid Supabase JWT authentication token.
- **402 Payment Required:** Attempting to access paid features from a free tier (e.g., `institutional_free` on Feature 1). Returns upgrade targets.
- **403 Forbidden:** Segment violation (e.g., retail accounts attempting institutional Feature 1) or unverified email address.
- **429 Too Many Requests:** Exceeded daily feature execution quota. Response includes quota limit and UTC reset timestamp.
- **503 Service Unavailable:** Upstream AI inference provider unconfigured or unreachable.

## 5. Hackathon Rules and How We Meet Each

FinInsight satisfies every hackathon requirement:
1. **NVIDIA Nemotron Integration:** Employs Nemotron models via Nebius Token Factory for explanation and agent workflows.
2. **Open Source Licensing:** Repository published under the permissive MIT License.
3. **Reproducibility:** Single command setup (`make install`, `make test`) with automated verification scripts.
4. **No Synthetic Shortcuts:** Core mathematical models run exclusively on real market data and real XBRL filings.
5. **No Medical Framing:** Domain strictly limited to equities, macroeconomics, and accounting.

## 6. Data Sources (What Works, What is Cut, Why)

Phase X1 assessed the feasibility of live Indian market data sources:

| Data Domain | Target Source | Phase X1 Feasibility Finding | Adopted Approach |
|---|---|---|---|
| Daily Prices | NSE / BSE APIs | No public programmatic APIs exist without commercial redistributor licenses. | Fetched via yfinance for development and demo mode. |
| Corporate Filings | BSE / NSE Filings | Quarterly XBRL XML files are publicly accessible; cash flows omitted. | Parsed directly from official exchange XBRL XML files. |
| Sovereign Yields | RBI / CCIL Curves | No open REST API exists for real-time sovereign curves. | Configured manually from RBI press release 2026-2027/1326 (5.7281%). |
| Institutional Flows | NSDL / CDSL | FII/DII flow reports published as static HTML; real-time feed restricted. | Omitted from contagion macro factor attribution. |

Data quality protections enforce adjusted closing prices for corporate actions and original filing versions for restatements.

## 7. Honesty Labels and Limits

FinInsight separates verified deterministic logic from unverified language model inference:

### 7.1 Verified Deterministic Core
- Absorption ratio calculation, Forbes-Rigobon adjustments, and moving-block bootstrap.
- XBRL parsing, metric normalization, and deterministic rule checks R0 to R7.
- XIRR solver, benchmark cash-flow replay, and behavioral process metrics.
- Token verification, role entitlements, atomic quotas, and secret redaction.

### 7.2 Unverified Inference Boundaries
- Natural language explanations generated by language models.
- Tool-calling agent decision loops.
- Web search retrieval results from external news providers.

### 7.3 Synthetic Demo Data Tagging
Demo trade logs generated for testing carry explicit `SYNTHETIC_DEMO` tags on every record.
The system identifies and labels synthetic data in all generated reports.

## 8. Cut Scope

To ensure mathematical precision, the project eliminated non-core elements:
1. **Advisor Review Workflow:** The advisor review no longer exists; all parameters operate as provisional baselines.
2. **Live Yield API:** The value is taken by hand from RBI press releases and refreshed before submission (cut: no open REST API).
3. **Live FII/DII Flow:** Programmatic institutional flow attribution was cut (cut: no usable source).
4. **Razorpay Keys:** Payment gateway integration was deferred (cut: payments are not built).
5. **Real-Time Intraday Feeds:** Analysis standardizes on daily closes due to commercial licensing barriers.
6. **Google OAuth Login:** Deferred due to enterprise credit card verification barriers; email authentication used.
7. **Trade Execution & Brokerage:** Excluded to maintain strict educational non-advisory status under SEBI rules.

## 9. Current Implementation Status

Implementation status across system components:
- **Built:** FastAPI backend with 25 endpoints, Next.js 15 frontend, database migrations, and calculation library.
- **Verified:** 394 known-answer unit tests and 17 live integration tests passing cleanly.
- **Unverified:** Live generation output from upstream Nebius Token Factory inference endpoints.
- **Pending:** Upstream commercial payment gateway activation and exchange direct feeds.

## 10. What is Left

The remaining technical tasks for future releases include:
1. Connecting an official programmatic Reserve Bank of India sovereign yield data feed.
2. Establishing direct exchange connection agreements with NSE and BSE.
3. Completing commercial merchant registration for payment processing.

## 11. Risks and Mitigations

The project monitors key operational and regulatory risks:

| Risk Identified | Potential Impact | Implemented Mitigation |
|---|---|---|
| Regulatory Action | Allegation of providing unregistered financial advice. | Strict educational disclaimers and prohibited advice lexicon filter. |
| Provider Outage | LLM inference failure during user query. | Gateway returns clean HTTP 503; math remains fully operational. |
| Data Drift | Schema changes in exchange XBRL reporting. | Strict Pydantic schema validation and fallback tolerance rules. |
| Token Overrun | Excessive token consumption in agent loop. | Daily USD budget guard with hard stop enforcement. |

## 12. Requirements Register

The table below lists all functional requirements and their implementation status:

| Requirement ID | Name | Functional Scope | Status |
|---|---|---|---|
| `FR-CFG` | Configuration and Secrets | Validates runtime environment variables by group. Redacts secrets. | Verified |
| `FR-AUTH` | Accounts and Authentication | Supabase email signup and ES256 JWKS JWT verification. | Verified |
| `FR-ENT` | Entitlements and Roles | Role-based access control and plan-based feature permissions. | Verified |
| `FR-QUO` | Atomic Daily Quotas | PostgreSQL conditional upsert enforcing daily usage limits. | Verified |
| `FR-PAY` | Payments Integration | Payment intent and webhook schema defined; live gateway deferred. | Pending |
| `FR-LLM` | LLM Gateway and Budget | Routes to Token Factory with SHA-256 caching and USD daily ceiling. | Verified |
| `FR-MKT` | Market Data Pipeline | Fetches daily equity adjusted closes via yfinance with alignment. | Verified |
| `FR-F1` | Market Contagion Detector | Calculates absorption ratio, Forbes-Rigobon shift, and bootstrap. | Verified |
| `FR-FIL` | Exchange Filings Ingestion | Parses quarterly Ind AS XBRL disclosures from NSE and BSE. | Verified |
| `FR-F2` | Filing Consistency Checker | Audits management claims against XBRL facts using rules R0-R7. | Verified |
| `FR-F3` | Investment Log Advisor | Calculates portfolio XIRR, benchmark replays, and process metrics. | Verified |
| `FR-AGT` | Agent Orchestrator Loop | Multi-turn tool-calling loop using Nemotron inference. | Unverified |
| `FR-CAC` | Response Caching | Deterministic SHA-256 caching of prompt and tool responses. | Verified |
| `FR-OBS` | Observability and Auditing | Structured JSON logging and event auditing in PostgreSQL. | Verified |
| `FR-UI` | Web Application Interface | Next.js 15 interface with in-memory token security. | Verified |

## 13. Project Glossary

- **AIF:** Alternative Investment Fund regulated under SEBI regulations.
- **BSE:** Bombay Stock Exchange, located in Mumbai.
- **Contagion:** Rapid transmission of financial stress across equity sectors.
- **FR:** Functional Requirement identifier defining system capabilities.
- **Ind AS:** Indian Accounting Standards converged with IFRS.
- **IST:** Indian Standard Time (UTC+05:30).
- **NIFTY 50:** Benchmark stock market index of the National Stock Exchange of India.
- **NSE:** National Stock Exchange of India, located in Mumbai.
- **Provisional:** Working value adopted in code and configuration without human financial advisor review.
- **SEBI:** Securities and Exchange Board of India.
- **SENSEX:** Benchmark stock market index of the Bombay Stock Exchange.
- **XBRL:** Extensible Business Reporting Language for electronic regulatory filings.
- **XIRR:** Extended Internal Rate of Return for irregular cash flow series.

