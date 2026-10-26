# Architecture & Engineering Decisions

### D-01: Minimal package skeleton for Phase A0
- **Status:** Accepted
- **Context:** Initial repo layout requires non-implemented modules per project_docs/tech_stack.md §2.
- **Decision:** Include single-line docstrings in package `__init__.py` files without implementation logic or fake stubs.

### D-02: Core and development dependencies
- **Status:** Accepted
- **Context:** The scaffold requires FastAPI, Uvicorn, Pydantic v2, and development tooling.
- **Decision:** Include only explicitly approved dependencies (`fastapi`, `uvicorn[standard]`, `pydantic>=2`, `pydantic-settings>=2`, `pyyaml`) and dev tooling (`pytest`, `httpx`, `ruff`, `mypy`, `types-PyYAML`).

### D-03: Pre-commit secret scanning policy
- **Status:** Accepted
- **Context:** Prevent staging and accidental commits of secrets and raw data.
- **Decision:** Enforce git pre-commit hook via `scripts/precommit_check.py` to block staged `.env`, `.env.*`, `private/`, `data/`, and probable API keys/secrets. Output reports only filename and rule name, never matched sensitive text.

### D-04: Strict Pathlib usage
- **Status:** Accepted
- **Context:** Cross-platform path handling and consistency.
- **Decision:** Require `pathlib.Path` across all scripts and application modules; prohibit `os.path`.

### D-05: Staged configuration validation and secret redaction
- **Status:** Accepted
- **Context:** Features implement service integrations across incremental phases, requiring selective environment validation to avoid premature startup errors while preventing secret leaks.
- **Decision:** Use a single registry matching .env.example partitioned into groups. Validate only groups enabled in config/runtime.yaml, reporting all missing variable names with no values. Enforce secret redaction (6+ characters) in logging.

### D-06: Default values for core non-secret operational variables
- **Status:** Accepted
- **Context:** Operational parameters APP_ENV and LOG_LEVEL establish execution mode and logging verbosity before any external service setup.
- **Decision:** Assign default values in Settings (APP_ENV to 'production', LOG_LEVEL to 'INFO') and set required_when_group_enabled to False for both in the registry. Function presence() reports them as present through these defaults even when absent from .env or process environment. Secrets must never have defaults.

### D-07: Static configuration loading and parameter resolution (A0.4)
- **Status:** Accepted
- **Context:** Domain parameters, analytical thresholds, pricing tiers, sector universes, historical episodes, and financial lexicons must be completely configured via declarative YAML files, validated strictly with Pydantic v2 schemas (`extra="forbid"`), and avoid hardcoding in Python logic.
- **Decision:** Store all baseline parameters and thresholds under `config/` (`parameters.yaml`, `thresholds.yaml`, `plans.yaml`, `universe.yaml`, `episodes.yaml`, `lexicon.yaml`). Validate using Pydantic v2 models raising `ConfigError` naming file and field. Support run-time overrides via `resolve_parameters(overrides)` raising `ParameterError` for bound, mutability, or type violations, and cross-validate time windows with `validate_window_consistency()`. No new external dependencies added.

### D-08: Deferral of contract model definitions pending batch implementation (A0.5)
- **Status:** Accepted
- **Context:** project_docs/tech_stack.md §5 lists contract models by name (`Portfolio`, `CorrelationScan`, `EvidencePack`, `Hypothesis`, `Claim`, `FilingMetric`, `Inconsistency`, `TradeLog`, `DecisionReview`, `AgentStep`, `ColumnMapping`, error envelope) without defining explicit field names, types, or schemas in §7.3. Inventing or freezing speculative schemas ahead of batch requirements risks divergence and breaking changes.
- **Decision:** Mark contract models listed in project_docs/tech_stack.md §5 as "contract pending". Defer concrete model definitions until their respective consuming batches:
  - Error envelope: Batch A0.6 (App shell)
  - Entitlements / Plans: Batch A1
  - CorrelationScan, EvidencePack, Hypothesis: Batch X5 / X7 (Feature 1)
  - FilingMetric, Claim, Inconsistency: Batch X6 / X8 (Feature 2)
  - Portfolio, TradeLog, ColumnMapping, DecisionReview: Batch X9 (Feature 3)
  - AgentStep: Batch X10 (Agent)
  Each contract model will be formally defined, frozen, and exported to `docs/contracts/` via `scripts/export_contract_schemas.py` during the batch that implements it.

### D-09: Filesystem git hash lookup with explicit fallback for code version (A0.6)
- **Status:** Accepted
- **Context:** Provenance tracking requires reporting a short code version. However, running `git` commands is prohibited or git binaries may be unavailable in stripped runtime containers.
- **Decision:** Implement `get_code_version()` reading `.git/HEAD` and corresponding ref files directly using `pathlib.Path`. If the `.git` directory, HEAD file, or packed ref cannot be resolved, explicitly fall back to the string `"unknown"`. No subprocess or git command is invoked.

### D-10: Interim development environment guard for ops console (A0.8)
- **Status:** Accepted
- **Context:** The basic ops console and inspection endpoints (`/ops/*`, `/console/*`, `/` redirect) expose system environment presence and loaded configuration tables for internal developer visibility. In production, these should not be openly accessible before authentication and administrative RBAC are built.
- **Decision:** Guard `/ops/status`, `/ops/config`, `/ops/parameters`, the `/console` static mount, and the `/` redirect so they are active only when `APP_ENV=development`. In any other environment, requests return 404 with the standard `ErrorEnvelope`. Batch X4 replaces this interim environment guard with full Supabase admin role verification.

### D-11: Alignment of plans configuration with project_docs/project.md specifications (A1)
- **Status:** Accepted
- **Context:** `config/plans.yaml` previously deviated from project_docs/project.md §4: retail tiers configured limited/full access to Feature 1 contagion scan instead of hard segment restriction, and institutional_free lacked locked upgrade linkage.
- **Decision:** Correct `config/plans.yaml` to strictly match project_docs/project.md §4: Feature 1 is configured with `access: none` on `retail_free` and `retail_paid`, and `access: locked` with `unlocks_with: institutional_paid` on `institutional_free`. Feature 3 on `retail_free` and `institutional_free` is configured with `access: limited`.

### D-12: Transition to daily quotas and configurable reset cadence (A1)
- **Status:** Accepted (Accepted (provisional, no advisor review))
- **Context:** project_docs/project.md FR-QUO-001 and project_docs/project.md §4 specify daily quota enforcement with UTC boundary calculation, whereas initial schema defined monthly fields.
- **Decision:** Rename `quota_per_month` to `quota_per_day` across `FeatureRule` schema and `config/plans.yaml`. Discard all monthly figures. Use only daily values explicitly specified in project_docs/project.md:
  - `retail_free`: F2 = 3 analyses/day, F3 = 1 log/day (FR-QUO-001)
  - `institutional_free`: F2 = 3 analyses/day, F3 = 1 log/day (§4.3, same as retail_free)
  - `institutional_paid`: F3 quota is resolved by D-26 (5/day, provisional, no advisor review).
  Reset schedule is driven by `reset_rule: utc_calendar_day` in `config/plans.yaml` and loaded via `PlansConfig`, ensuring no hardcoded cadence in calculation logic.

### D-13: Canonical Indian fiscal period format and trading calendar alignment policy (A2.1)
- **Status:** Accepted
- **Context:** Project specifications (project_docs/project.md §4.1, §FR-FIL-006, and financial context notes) reference Indian quarterly periods using the pattern "Q1 FY27" (April-June 2026), while multi-asset alignment requires strict data integrity without silent dropping or forward-filling.
- **Decision:** Restrict fiscal period label parsing exclusively to the canonical format demonstrated across the specification: `Q[1-4] FY\d{2}` (e.g. `Q1 FY27`). All alternative or non-canonical formats are rejected with an explicit `ValueError`. Multi-series calendar alignment enforces an exact match against the provided trading calendar dates, surfacing missing data (gaps), dates outside the calendar, non-positive prices, and mixed naive/aware datetimes with loud failures.

### D-14: NumPy dependency for array and matrix computations (A2.2)
- **Status:** Accepted
- **Context:** Core statistical and correlation estimators require fast, vectorised array operations and eigenvalue decomposition.
- **Decision:** Add `numpy` to `pyproject.toml` dependencies.

### D-15: SciPy dependency for rank correlation and statistics (A2.2)
- **Status:** Accepted
- **Context:** Robustness check against volatility bias requires Spearman rank correlation per project_docs/finance_stack.md §6.
- **Decision:** Add `scipy` to `pyproject.toml` dependencies to provide `scipy.stats.spearmanr`.

### D-16: scikit-learn dependency for Ledoit-Wolf covariance shrinkage (A2.2)
- **Status:** Accepted
- **Context:** High-dimensional asset covariance matrices with limited sample length require Ledoit-Wolf shrinkage per project_docs/finance_stack.md §4.
- **Decision:** Add `scikit-learn` to `pyproject.toml` dependencies for `sklearn.covariance.ledoit_wolf`.

### D-17: Pure estimator conventions, parameters, and pending values (A2.2)
- **Status:** Accepted
- **Context:** Estimators require explicit definitions for EWMA initialization, Forbes-Rigobon variance calculation, absorption-ratio matrix representation, and component count parameterization.
- **Decision:**
  - **EWMA initialization:** project_docs/finance_stack.md §4 states initialization from the first W observations. Sample covariance of the first W observations (`ddof=1`) serves as initial matrix Σ_0, recursively updated via Σ_t = λ Σ_{t-1} + (1 - λ) r_t r_tᵀ with zero-mean returns (docs silent, standard choice).
  - **Forbes-Rigobon variance definition:** project_docs/finance_stack.md §5 defines relative variance shift δ = σ²_x,high / σ²_x,low - 1. Docs silent on sample variance degrees of freedom; standard choice: unbiased sample variance `ddof=1` (docs silent, standard choice).
  - **Absorption-ratio matrix choice:** project_docs/finance_stack.md §7 specifies correlation matrix, whereas parameter register notes advisor confirmation is pending; standard choice: correlation matrix (docs silent, standard choice).
  - **Absorption ratio component count k:** Window bounds and parameter defaults come strictly from configuration (`parameters.yaml`). Integer component count `k` is not specified as a static integer in config (which provides `k_fraction`), so `k` is a required argument with no default in `absorption_ratio` and is marked provisional, no advisor review.

### D-18: Standard day-count basis named constant for XIRR (A2.3)
- **Status:** Accepted
- **Context:** project_docs/project.md §5.11 and 10_parameters_register.md §5 establish standard spreadsheet convention of 365 days per year for XIRR cash flow discounting. Bare literals are forbidden in logic.
- **Decision:** Define named constant `DAYS_PER_YEAR = 365.0` in `backend/app/features/f3_log/xirr.py`.

### D-19: Moving-block bootstrap algorithm and output conventions (A2.3)
- **Status:** Accepted
- **Context:** project_docs/project.md §5.6 specifies moving-block bootstrap with recorded seed. Block wrapping, partial block handling, and output distribution format are not explicitly detailed in finance docs.
- **Decision:**
  - Block type: Moving (overlapping) blocks, docs silent, standard choice.
  - Final block truncation: When target length is not an integer multiple of block length, truncate the final sampled block, docs silent, standard choice.
  - Output contract: Return a frozen `BootstrapResult` containing the full replication distribution, seed, block length, resample count, and alpha, docs silent, standard choice.
  - Parameters: `block_len`, `n_boot`, and `alpha` are loaded from `config/parameters.yaml` when not explicitly supplied, and validated against configured bounds. Seed is a required argument with no default.

### D-20: XIRR solver parameters, multiple roots handling, and pending values (A2.3)
- **Status:** Accepted
- **Context:** Cash flow sequences may yield non-monotonic NPV curves with multiple internal rates of return or fail to bracket a root. Bare `ValueError` is prohibited, and literals in logic are forbidden.
- **Decision:**
  - Root solver: Bracketed Brent solver (`scipy.optimize.brentq`).
  - Cash flow requirements: Require at least one positive flow and at least one negative flow; the initial flow is not required to be negative.
  - Multi-root and convergence error handling: Subdivide search bracket into grid points to evaluate NPV signs. If more than one sign change occurs, raise `MultipleRootsError`. If no sign change occurs, raise `XIRRConvergenceError`. Non-convergence of Brent solver raises `XIRRConvergenceError`. Reuses `ParameterError` for invalid inputs.
  - Pending values: Solver search bracket `bracket`, convergence tolerance `tol`, maximum iterations `max_iter`, and sign check `grid_points` are required arguments with no defaults, pending configuration / advisor confirmation.

### D-21: Process metrics definitions and conventions (A2.4)
- **Status:** Accepted
- **Context:** Process metrics require standard financial definitions where docs are silent.
- **Decision:**
  - Turnover: One-way turnover formula `sum |V_traded| / (2 * avg_portfolio_value)` (docs silent, standard choice).
  - Concentration HHI: Scaled in `[0, 1]` as sum of squared fractional position weights `sum w_i^2` (docs silent, standard choice).
  - Disposition effect: Odean proportions of realized gains/losses with minimum sales threshold validation from configuration (docs silent, standard choice).

### D-22: Institutional performance metrics and pending parameters (A2.4)
- **Status:** Accepted
- **Context:** Alpha, beta, tracking error, and information ratio require degrees of freedom and annualisation specifications.
- **Decision:**
  - Degrees of freedom: Sample variance and standard deviation use `ddof=1` (docs silent, standard choice).
  - Zero tracking error: Raises `ParameterError`.
  - Pending parameters: `annualisation_factor` (required argument without default, provisional, no advisor review on return cadence) and risk-free series specification.

### D-23: Derived filing metrics and validation constraints (A2.4)
- **Status:** Accepted
- **Context:** Financial filing analysis requires strict period matching, non-zero denominator guards, dynamic calendar day counts, and unit consistency.
- **Decision:**
  - YoY and QoQ growth: Strict validation requiring matching prior fiscal quarter (`t - 4Q` for YoY, `t - 1Q` for QoQ); zero or negative base raises `ParameterError`.
  - DSO: Uses dynamic fiscal period calendar day count computed via A2.1 fiscal utilities (`fiscal_period_to_dates`). Non-positive revenue raises `ParameterError`.
  - Margins and OCF: Revenue from operations must be strictly positive; non-positive revenue or PAT raises `ParameterError`.
  - Q4 derivation: Subtraction of 9M cumulative from annual figure requires matching fiscal year and identical unit. Negative derived revenue raises `ParameterError`; negative derived profit (loss) is permitted; other negative types provisional, no advisor review.

### D-24: Text chunker, verbatim-quote check, and rule engine R0-R7 (A2.5)
- **Status:** Accepted
- **Context:** Text processing, verbatim verification, and deterministic filing rule engine R0-R7 implementations.
- **Decision:**
  - Character offsets: Character offsets (`start: int`, `end: int`) used throughout; chunk offsets round-trip exactly by slicing original text (`text[chunk.start:chunk.end] == chunk.text`) (chosen to unblock, advisor may override).
  - Chunk size & overlap: Configured in `parameters.yaml` (`chunk_size` default 1200, bounds [200, 5000]; `chunk_overlap` default 150, bounds [0, 500]) marked provisional; no numeric literals in Python logic (chosen to unblock, advisor may override).
  - Quote verification: Exact verbatim substring check only, no case folding, no fuzzy matching (chosen to unblock, advisor may override).
  - Unit/scale & alignment: Explicit fields on input; unit mismatch raises `ParameterError` with no auto-convert; fiscal period or reporting basis (standalone vs consolidated) mismatch raises `ParameterError` (chosen to unblock, advisor may override).
  - Rule results & ordering: Rules return structured `RuleResult` (`pass`, `flag`, `not_applicable`) with evidence; evaluated strictly in order R0 then R1-R7 (chosen to unblock, advisor may override).
  - Sector growth thresholds & pending values: Missing or unconfigured sector thresholds require explicit configuration; rules return `not_applicable` with reason "threshold pending" rather than guessing values (chosen to unblock, advisor may override).
  - Contracts & errors: Reuses existing `Claim` and `FilingMetric` contracts and `ParameterError` without altering contract fields or error hierarchy.

### D-25: Infrastructure logic (response-cache key, budget guard, cost report, Dockerfile) (A3)
- **Status:** Accepted
- **Context:** Core infrastructure logic without external services per PROGRESS.md A3.
- **Decision:**
  - Response-cache key: SHA-256 over canonical JSON (sorted keys, fixed compact separators) of model, prompt, parameters, and data_version; prompt is hashed as given without reformatting (chosen to unblock, advisor may override).
  - Budget reset rule: Follows UTC calendar day matching the A1 quota convention; reset rule parameterized from configuration, not hardcoded (chosen to unblock, advisor may override).
  - Budget selection & enforcement: Daily budget limit is a required parameter supplied by caller (e.g. production vs test limit); logic performs pure calculation without reading environment variables directly (chosen to unblock, advisor may override).
  - Limit error: Dedicated error subclass `BudgetExceededError` inheriting from `ParameterError`; refuses calls at or over the limit (chosen to unblock, advisor may override).
  - Token prices & pending values: Per-model token prices are marked pending; unpriced or pending models raise `UnknownModelPriceError`; no prices invented; tests supply hand-written prices (chosen to unblock, advisor may override).
  - Dockerfile & security: Container runs `uvicorn backend.app.main:create_app --factory`, excludes `.env`, `.env.*`, `private/`, `data/` via `.dockerignore`; no secrets baked into image (chosen to unblock, advisor may override).

### D-26: Resolution of provisional configuration parameters
- **Status:** Accepted (chosen, no advisor review, provisional)
- **Context:** Pinning pending domain values in configuration files to complete Phase A pure libraries.
- **Decision:**
  - 1. Absorption fraction: `k_fraction` set to 0.20 in `parameters.yaml`; component count `k` is derived as `max(1, ceil(N * k_fraction))` (chosen, no advisor review, provisional).
  - 2. Institutional metrics: Configured in `parameters.yaml` with `return_frequency="daily"`, `annualisation_factor=252`, and `risk_free_series="91-day T-bill yield (source decided in X1)"` (chosen, no advisor review, provisional).
  - 3. XIRR parameters: Configured in `parameters.yaml` with bracket `[-0.99, 10.0]`, tolerance `1.0e-9`, `max_iter=200`, and `grid_points=1000` (chosen, no advisor review, provisional).
  - 4. Institutional Paid F3 daily quota: Set in `plans.yaml` to 5 (5x the institutional_free quota of 1 per day) (chosen, no advisor review, provisional).
  - 5. Sector growth thresholds: Defined in `thresholds.yaml` with conservative values to flag rarely; any flag derived from a sector threshold includes the label "provisional threshold" (chosen, no advisor review, provisional):
    - `fmcg` (0.06): Mature consumer staple demand with low elasticity means 6% nominal growth represents genuine real volume expansion.
    - `it_services` (0.08): Mid-single digit global enterprise technology spend makes 8% a defensible floor for strong top-line growth.
    - `autos` (0.10): Cyclical volume recovery and replacement cycles require at least 10% YoY growth to separate normal cycle from strong momentum.
    - `capital_goods` (0.12): Long-cycle infrastructure capex execution requires 12% revenue growth before management can defensibly claim robust delivery.
    - `metals` (0.10): Highly volatile commodity realizations require 10% revenue expansion to filter price spikes from operational expansion.
    - `energy` (0.08): Fluctuating upstream realizations and refining spreads require 8% nominal growth to avoid false flags during steady throughput.
    - `telecom` (0.08): Gradual ARPU expansion and subscriber upgrades make 8% a conservative threshold for healthy top-line expansion.
    - `consumer_durables` (0.10): Seasonal discretionary consumption requires 10% YoY growth to separate festive promotional surges from robust expansion.
    - `other` (0.08): Standard broad-market baseline of 8% nominal growth for unclassified non-financial companies.
  - 6. Token prices: Left pending in configuration; no token prices invented.

### D-27: Feasibility evaluation of external data sources (X1 feasibility)
- **Status:** Accepted
- **Context:** project_docs/project.md §6.5 data register and PROGRESS.md X1.4-X1.6 require live connectivity checks and feasibility assessments of candidate Indian and macro data sources using throwaway scripts under `scripts/feasibility/`.
- **Decision & Source Verdicts:**
  1. **NSE/BSE direct downloads:** Unusable. Direct requests to NSE endpoints are rejected with 403/503 by Akamai WAF without browser session cookies, and BSE APIs return 403; terms not read, blocked only by 403.
  2. **NSE Indices downloads (niftyindices.com):** Unusable. The website returns HTTP 200 for presentation pages but programmatic data download endpoints redirect to HTML forms requiring ASP.NET session state and interactive viewstate tokens; terms not read, blocked only by 403.
  3. **yfinance NSE/BSE tickers:** Usable (development/research only, high risk for production). Real queries to Yahoo Finance chart endpoints return full daily OHLCV and split/dividend adjusted prices for NSE/BSE equities (`.NS`, `.BO`), Nifty 50 (`^NSEI`), Sensex (`^BSESN`), and India VIX (`^CRSLDX`). However, this relies on an unofficial endpoint that Yahoo terms of service prohibit for commercial/automated usage and is subject to unannounced rate limits and schema breakage.
  4. **RBI / FBIL:** Unusable. Both the Reserve Bank of India DBIE portal and FBIL benchmark portals run client-side JavaScript Single Page Applications protected by Google reCAPTCHA. Neither service provides an open public REST API for programmatic ingestion.
  5. **FRED:** Usable (needs key). FRED provides an official REST API with permissive developer terms. Series `INTGSBINM193N` contains Indian Government Bonds yield (not a 3-month or 91-day rate), alongside US Treasury yields and global macro series. Requires `FRED_API_KEY` in environment configuration (marked "needs key" when absent).
  6. **NSDL / NSE institutional flow data:** Unusable. NSE provides only a single-day snapshot via `/api/fiidiiTradeReact` without historical time series endpoints; terms not read, blocked only by 403. NSDL publishes flow reports as periodic web/Excel files with no public REST API.
  7. **NSE/BSE results XBRL:** Usable (via NSE corporate filings archive). Real Ind AS XBRL filings are retrievable from NSE XML archives (`nsearchives.nseindia.com`). Successfully verified on non-financial company V.S.T. Tillers Tractors Limited (`VSTTILLERS`) for a quarterly reporting period, extracting Revenue from Operations, Profit Before Tax, Profit After Tax, and EPS. BSE API endpoint returns 403.
  8. **Company transcripts & announcements:** Unusable as a structured API (partially usable via unstructured PDF extraction). Corporate announcements are reachable on NSE, including conference call outcomes mandated under SEBI LODR Regulation 30, but documents are hosted exclusively as unstructured PDF attachments without native text/JSON transcript feeds.

### D-28: Price data scope - yfinance only (unofficial, demo only)
- **Status:** Accepted
- **Context:** Connectivity tests confirmed direct exchange and index-provider endpoints fail or block programmatic access without sessions.
- **Decision:** Restrict price and benchmark data ingestion exclusively to yfinance for development and demo mode. Marked as unofficial and high-risk for commercial production.

### D-29: Institutional flow data scope - omission from macro factor attribution
- **Status:** Accepted
- **Context:** NSDL publishes reports as periodic manual files without an open REST API, and NSE institutional flow endpoints provide only single-day snapshots without historical series.
- **Decision:** Exclude institutional flow data (FII/DII / FPI) from Feature 1 macro factor attribution.

### D-30: Feature 2 quarterly XBRL scope - limited to revenue and profit checks
- **Status:** Accepted
- **Context:** Verification across five non-financial companies across distinct sectors confirmed quarterly Ind AS XBRL filings submitted under Regulation 33 contain only Profit & Loss figures (revenue, profit before tax, profit after tax, EPS); balance sheet receivables and operating cash flow statements are absent in quarterly filings.
- **Decision:** Scope Feature 2 quarterly automated filing consistency verification exclusively to revenue and profit metrics. Other filing consistency rules (such as cash quality and working capital) evaluate to not-applicable on quarterly filings.

### D-31: Feature 2 commentary text source - claims sourced from announcement PDFs
- **Status:** Accepted
- **Context:** No structured API exists for corporate earnings call transcripts or investor presentations; documents are published exclusively as unstructured PDF attachments under NSE corporate announcements.
- **Decision:** Ingest management commentary claims by extracting text from downloaded corporate announcement PDF attachments rather than expecting structured transcript feeds.

### D-32: Risk-free rate configuration - required config entry with null value
- **Status:** Accepted
- **Context:** Real-time Indian risk-free rate series (FBIL / RBI) lack public REST APIs, and FRED INTGSBINM193N reflects historical government bonds rather than active 3-month Treasury bills.
- **Decision:** Define `risk_free` as a required configuration entry in `config/parameters.yaml` with provisional status, null value, and required `source` and `as_of` fields. Any code attempting to consume the risk-free rate while its value is null must raise `ParameterError`.

### D-33: Broker API price source evaluation (Zerodha, Upstox, Angel One, Fyers)
- **Status:** Accepted
- **Context:** Docs-only evaluation of official Indian retail broker APIs as alternative candidates for NSE equity and index daily price data per project_docs/project.md §6.5.
- **Decision & Source Verdicts:**
  1. **Zerodha Kite Connect:** Not a candidate. Paid subscription (costs ₹500/month, violating zero-budget policy), requires a personal KYC trading account, and terms prohibit public display or redistribution of market data ("live market data obtained via Kite Connect cannot be displayed to the public at large", https://kite.trade/terms).
  2. **Upstox API:** Candidate for manual research extraction only; not a candidate for autonomous production service. Free (₹0 subscription), provides historical daily candle data spanning multiple decades for NSE equities and indices, but requires personal KYC broker account credentials with daily OAuth token refreshes.
  3. **Angel One SmartAPI:** Candidate for manual research extraction only; not a candidate for autonomous production service. Free (₹0 subscription), provides multi-year historical daily candle data for NSE equities and indices, but requires personal KYC broker account credentials and mandatory static IP binding for requests.
  4. **Fyers API:** Candidate for manual research extraction only; not a candidate for autonomous production service. Free (₹0 subscription), provides multi-year historical daily candle data for NSE equities and indices, but requires personal KYC broker account credentials with daily authentication.

### D-34: Separation of SUPABASE_PASSWORD from DATABASE_URL in environment registry
- **Status:** Accepted
- **Context:** Supabase database administration, CLI migrations, direct postgres connections, and pooler mode switches (such as Session pooler on port 5432 versus Transaction pooler on port 6543) require the raw database password as a distinct credential. Relying exclusively on `DATABASE_URL` introduces fragility when dynamically constructing connection strings, as parsing and URL-decoding passwords containing special characters from a composite URI string is prone to failure.
- **Decision:** Add `SUPABASE_PASSWORD` as a standalone required secret variable in the `supabase` group of the environment registry without a default value, maintained alongside `DATABASE_URL`.

### D-35: Risk-free rate configuration entry and RBI 91-day T-bill benchmark
- **Status:** Accepted
- **Context:** The risk-free rate required by Feature 3 institutional metrics was previously pending a confirmed Indian money market source. An unconfirmed figure of 5.49% without a verified primary source was rejected per the real-data policy.
- **Decision:** Set the `risk_free` configuration entry in `config/parameters.yaml` to `value: 5.7281`, `unit: "percent per annum"`, `status: "provisional, no advisor review"`, `source: "RBI 91-day T-bill auction cut-off yield (Treasury Bills: Full Auction Result, press release 2026-2027/1326)"`, and `as_of: "14 October 2026 auction"`. Note that 5.2624 from the August auction is replaced, and that the weighted average yield 5.6964 was not used in favor of the cut-off yield. The configured yield must be replaced with the latest auction cut-off from the RBI press release as new auction results are published. The `as_of` field is an explicit provenance exception to the no-dates rule to record auction vintage. The `unit` field is mandatory; application code must convert the percent figure to decimal (5.7281 -> 0.057281) explicitly and raise `ParameterError` if the unit is missing or unknown. Consuming code continues to raise `ParameterError` if the value is null. Every analytical result that uses the risk-free rate must include value, unit, source, and as_of in its recorded parameters.

### D-36: PostgreSQL database driver dependency selection (psycopg)
- **Status:** Accepted
- **Context:** Database connectivity to Supabase PostgreSQL for migrations, connection health checks, and data operations requires a native PostgreSQL driver in Python per project_docs/tech_stack.md §8 and PROGRESS.md X2.1.
- **Decision:** Add `psycopg[binary]>=3.2.0` as a production dependency in `pyproject.toml`. Psycopg 3 provides modern Python type hint support, binary protocol performance, connection pooling, client-side binding parameters, and SSL configuration required for remote Supabase connections.

### D-37: Plans database table duplication of plans.yaml
- **Status:** Accepted
- **Context:** In migration 001_initial_schema.sql, the `plans` reference table seed values (plan names, segments, and prices) were hand-copied from `config/plans.yaml`.
- **Decision:** Flag that `plans` in Postgres currently duplicates `config/plans.yaml` via static SQL seed inserts. Per verification constraints, do not redesign now; keep `plans.yaml` as the canonical analytical definition and retain the existing relational table for foreign key integrity on `profiles.plan`.

### D-38: Deferral of subscriptions and payments mutation to X11
- **Status:** Accepted
- **Context:** Tables `public.subscriptions` and `public.payments` were created in the initial schema per project_docs/tech_stack.md §8. Payment gateway integration and recurring billing lifecycles belong to batch X11.
- **Decision:** Confirm that `subscriptions` and `payments` remain empty in Supabase and that their RLS policies restrict all mutations exclusively to `service_role`. Runtime payment processing and state transitions are deferred to batch X11.

### D-39: Deferral of Google OAuth due to card requirement
- **Status:** Accepted
- **Context:** Google OAuth client configuration requires setting up a Google Cloud project with billing verification which is unavailable without a card.
- **Decision:** Google OAuth is out of scope for authentication. Leave the `oauth` group disabled in configuration, do not write Google OAuth integration code, rely solely on Supabase email signup with email verification, and record "Google login not implemented" in documentation.

### D-40: JWT signature verification via Supabase JWKS public keys (ES256)
- **Status:** chosen, no advisor review, provisional
- **Context:** Live testing against the Supabase project demonstrated that issued access tokens use asymmetric ECDSA ES256 signatures with key IDs (`kid`) rather than shared secret HS256 signatures.
- **Decision:** Verify incoming JWTs using the project's public keys fetched and cached from the Supabase JWKS endpoint (`/auth/v1/.well-known/jwks.json`), with standard fallback support for HS256 if configured.

### D-41: Email verification enforcement returning 403 email_not_verified
- **Status:** chosen, no advisor review, provisional
- **Context:** project_docs/project.md FR-AUTH-002 mandates that unverified accounts cannot access analytical features.
- **Decision:** Valid tokens for accounts where email is unverified return HTTP 403 with error code `email_not_verified`. Missing, invalid, or expired tokens return HTTP 401 via `ErrorEnvelope`. If the email verification field is absent from both token and database user record, raise an explicit error rather than assuming verified status.

### D-42: Admin authorization read strictly from app_metadata
- **Status:** chosen, no advisor review, provisional
- **Context:** Authorization privilege checks require clear separation between user-controlled profile fields and provider-managed roles.
- **Decision:** Read administrator status strictly from `app_metadata.role == 'admin'`, never from `user_metadata`. Admin endpoints return HTTP 403 for non-admins. Service role keys are never used to decide user admin standing.

### D-43: Atomic database quota increment via PostgreSQL conditional upsert
- **Status:** chosen, no advisor review, provisional
- **Context:** Per FR-QUO-001/002, concurrent requests must not exceed configured daily feature quotas, preventing race conditions at limit minus one.
- **Decision:** Enforce quotas server-side using PostgreSQL atomic conditional upserts (`INSERT ... ON CONFLICT (user_id, feature, utc_date) DO UPDATE SET count = usage.count + 1 WHERE usage.count < max_quota RETURNING count`). Parallel requests competing at the boundary are resolved atomically by row-level locking.

### D-44: Provisional seed accounts configuration and credentials lifecycle
- **Status:** chosen, no advisor review, provisional
- **Context:** Seed judge and demo accounts require deterministic identification and idempotent provisioning without leaking secrets.
- **Decision:** Store provisional email addresses in `config/accounts.yaml`. Provisioning via `scripts/seed_accounts.py` uses passwords solely from environment variables `JUDGE_PASSWORD`, `DEMO_RETAIL_PASSWORD`, and `DEMO_INSTITUTIONAL_PASSWORD`, creates pre-confirmed accounts via the Supabase Admin API, synchronizes database profiles, and never logs or prints credentials.

### D-45: Production admin authorization guard superseding D-10 interim guard (X4)
- **Status:** chosen, no advisor review, provisional
- **Context:** Decision D-10 established an interim `APP_ENV=development` check on `/ops/*`, `/console/`, and the `/` redirect. Production readiness requires operational inspection endpoints to be secured cryptographically by admin role authorization across all environments rather than suppressed by environment flags.
- **Decision:** Supersede D-10. Mount `/ops/*`, `/console/`, and `/` unconditionally across all environments, guarded strictly by `require_admin` (role read exclusively from `app_metadata.role == 'admin'`). Missing or invalid tokens return HTTP 401 with `ErrorEnvelope`; authenticated non-admins return HTTP 403 with `ErrorEnvelope`; admins receive HTTP 200 (or HTTP 307 redirect for `/`).
- **Console Session Architecture:** Because initial browser page loads cannot transmit Bearer headers, the frontend console operates an in-memory session model. A login view obtains a Supabase session via `/api/auth/token`, retaining the JWT exclusively in memory and injecting the `Authorization: Bearer <token>` header into all subsequent API requests. Tokens are strictly excluded from URLs, query parameters, web storage persistence, and browser logs.

### D-46: CorrelationScan contract definition, market data caching, and XBRL filings ingestion (X5/X6)
- **Status:** chosen, no advisor review, provisional
- **Context:** Combining X5 (Market Data & Feature 1 Statistics) and X6 (Filings & Feature 2 Consistency Engine) without LLM. Resolves D-08 pending contract fields.
- **Decision:**
  - `CorrelationScan` contract defined with fields: `as_of`, `source_label` ("unofficial source, demo only"), `parameters_used` (`W`, `B`, `G`, `C`, `lambda`, `seed`), `regime_flag` (`none`, `watch`, `warning`, `critical`), `absorption_ratio`, `ar_delta_std`, `significant_pairs_count`, `mean_correlation`, `top_shifted_pairs` (`pair`, `baseline_corr`, `current_corr`, `fr_adjusted_corr`, `p_value`, `q_value`), `matrix_summary`, `episodes_status` ("pending_scan_full_history"), `seed`, and `code_version`.
  - Market data from Yahoo Finance chart API fetched once and cached in `data/yproject_docs/` (gitignored). Candidate universe from `config/universe.yaml` yielded 79 successful tickers and 2 failed tickers reported explicitly with zero synthetic fill.
  - Feature 1 pipeline aligns returns on common trading days, runs Forbes-Rigobon volatility adjustment, computes systemic absorption ratio and moving-block bootstrap (200 iterations with recorded seed), generating `data/f1_scan_demo.json`.
  - Feature 2 engine parses 5 non-financial company XBRL XML filings (`INFY`, `ITC`, `MARUTI`, `RELIANCE`, `TATASTEEL`), derives operating metrics and margins, evaluates consistency rules R0-R7, and precomputes `data/f2_filings_demo.json` and per-company JSONs.

### D-47: Feature 3 pending contracts definition (ColumnMapping, TradeLog, Portfolio, DecisionReview)
- **Status:** chosen, no advisor review, provisional
- **Context:** project_docs/tech_stack.md §5 and FR-F3-001..012 require formal contract schemas for trade log ingestion, portfolio aggregation, and decision reviews. CorrelationScan was already added to contracts in D-46.
- **Decision:** Define minimal strict contract models:
  - `ColumnMapping`: explicit mapping from CSV headers to canonical fields (`date`, `symbol`, `side`, `quantity`, `price`, and optional `fees`, `charges`, `exchange`, `segment`).
  - `TradeLog`: container of parsed `Trade` items with `total_trades`, `symbols`, `start_date`, `end_date`, `consent_given`, and `is_retained`.
  - `Portfolio`: aggregated portfolio state with `positions` (`Position` per symbol), `cash_balance`, `total_cost`, `total_market_value`, `total_realized_pnl`, and `total_unrealized_pnl`.
  - `DecisionReview`: final review model containing `portfolio`, `portfolio_xirr`, `benchmark_replays` (`BenchmarkReplay`), `process_metrics` (`ProcessMetrics`), optional `institutional_metrics` (`InstitutionalMetrics`), `review_text`, educational `disclaimer`, and `parameters_used`.
  All models exported to `docs/contracts/` JSON schemas and validated via schema drift tests.

### D-48: Frontend technology selection: Plain HTML/CSS/JS without framework or CDN
- **Status:** Accepted
- **Context:** Basic ops frontend was initially envisioned with React. Running npm builds, managing node modules, and external CDN dependencies add build overhead and failure points.
- **Decision:** Cut React in favor of vanilla HTML, CSS, and JavaScript located in `frontend/app/`. The application requires no npm build step, no CDN, and no external frameworks. It is served directly by the FastAPI backend, retains auth tokens strictly in JavaScript memory, renders securely using textContent (preventing XSS from server data), and complies with dense technical dashboard aesthetics (#0F1318 palette, 13px monospace data, 2px border radius).

### D-49: Feature 3 trade log processing and benchmark replay pipeline
- **Status:** chosen, no advisor review, provisional
- **Context:** Feature 3 requires processing real trade logs on-the-fly, mapping columns explicitly, computing XIRR, replaying cash flows into Nifty 50 and matched sector indices using stored yfinance market data, and computing process and institutional metrics.
- **Decision:** Implement `backend/app/features/f3_log/pipeline.py`:
  - Enforce explicit column mapping; raise row-numbered errors for unmapped, missing, or malformed rows. Never skip invalid rows.
  - Compute portfolio cash flows, FIFO lot accounting for realized PnL, and XIRR using existing A2 Brent solver (`backend/app/features/f3_log/xirr.py`).
  - Replay exact cash flows into Nifty 50 (`^NSEI.json`) and matched sector index from `data/yproject_docs/`. Missing benchmark price data raises an explicit error.
  - Compute process metrics (concentration HHI, turnover, disposition effect PGR/PLR, max drawdown) and institutional metrics (beta, alpha, tracking error, information ratio) using existing A2 library functions.
  - Enforce zero persistence for uploaded logs unless `consent_given` is explicitly true.

### D-50: Owner-approved exception for synthetic demo trade log
- **Status:** chosen, no advisor review, provisional
- **Context:** project_docs/tech_stack.md §15 real-data policy prohibits synthetic data standing in for live services. To allow demonstration and automated end-to-end testing of Feature 3 pipeline mechanics without collecting or requiring real investor trade logs from external users, an owner-approved exception was granted.
- **Decision:**
  - `scripts/make_demo_trade_log.py` generates `private/logs/demo_synthetic_log.csv` using exclusively real trading dates and real close prices from `data/yproject_docs/`. Missing prices raise explicitly; no prices are invented.
  - Configuration in `config/parameters.yaml` controls trade count (`synthetic_log_trades`), quantity bounds (`synthetic_log_qty_min`, `synthetic_log_qty_max`), and deterministic seed (`synthetic_log_seed`).
  - The marker `SYNTHETIC_DEMO` is stamped on every row, recorded in the header metadata comment, and stored in the filename.
  - The ingestion pipeline detects `SYNTHETIC_DEMO`, flags `is_synthetic_demo = True`, rejects upload if `consent_given` is true (synthetic logs are never retained as real data), and sets explicit disclosure labels on `DecisionReview` ("SYNTHETIC DEMO LOG, not a real investor") and `ProcessMetrics` ("describes the generator, not a real investor").
  - The exception is recorded in `README.md` under Data limitations.

### D-51: Owner-approved exception for rule-based placeholder LLM provider
- **Status:** chosen, no advisor review, provisional
- **Context:** To develop and verify LLM-dependent pipeline interfaces (X7, X8, X9) on CPU-only machines without external Nebius API keys or database dependencies, an owner-approved exception was granted to implement a rule-based placeholder provider.
- **Decision:**
  - Implement `backend/app/llm/placeholder.py` matching the `LLMClient` gateway interface.
  - Active only when `APP_ENV` is `development` or `test`; strictly rejected in `production`.
  - Every output carries the prefix/marker `"PLACEHOLDER TEMPLATE, not Nemotron"`, is never written to precomputed demo JSON files, and is never displayed as real analysis.
  - Placeholder token pricing is configured as `0.0` under parameter `llm_placeholder_price_per_1m`; real model pricing remains pending.
  - Budget guard, cache keys, output financial advice guards, and ledger-shaped records execute identically to the production gateway.

### D-52: Inconsistency contract definition for Feature 2 adjudication
- **Status:** chosen, no advisor review, provisional
- **Context:** project_docs/project.md §5.10, §7.3, and §9 require a formal frozen contract schema for filing inconsistency findings produced by claim extraction, deterministic metric matching, and adjudicator verification.
- **Decision:**
  - Define `Inconsistency` contract in `backend/app/contracts/filings.py` with fields: `rule_id`, `verdict` (`confirm`, `downgrade`, `reject`), `severity` (`high`, `medium`, `low`), `metric`, `claim_quote`, `quote_start`, `quote_end`, `stated_value`, `filed_value`, `difference_value`, `explanation`, `is_placeholder`, and `placeholder_label`.
  - Export JSON schema to `docs/contracts/Inconsistency.json` and validate schema drift via `backend/tests/known_answer/test_contracts.py`.

### D-53: Unauthenticated /console/ static asset serving and /app root redirect
- **Status:** chosen, no advisor review, provisional
- **Context:** Mounting `require_admin` on static file routes for the ops console (`/console/`, `/console/index.html`, `/console/config.html`) prevented the browser from loading the console login form without an existing bearer token, returning a 401 error. Similarly, redirecting `/` to `/console/` under an admin guard caused unauthenticated visitors to receive a 401 response instead of reaching the application.
- **Decision:**
  - Serve `/console/` static HTML, CSS, and JS assets without token authentication. These static files contain no data and no secrets; they serve the client-side login form which acquires an in-memory token.
  - Retain `require_admin` strictly on all `/ops/*` operational inspection routes and admin data endpoints.
  - Redirect root path `/` directly to `/app` without requiring authentication, allowing browsers to access the demo application cleanly.

### D-54: Initial render unauthenticated state and in-panel error reporting for /app/ and /console/
- **Status:** chosen, no advisor review, provisional
- **Context:** `/app/` previously showed only the top header because `#screen-login` was missing the `.active` CSS display class while `#workspace` was hidden, and `app.js` lacked an initial DOM load initialization routine. `/console/` showed only the diagnostics panel because `#login-panel` defaulted to hidden with inline styles, and protected data panels rendered blank tables without informing unauthenticated operators that administrative credentials were required.
- **Decision:**
  - Mark `#screen-login` as active by default in `frontend/app/index.html` and invoke `initApp()` on `DOMContentLoaded` in `app.js` to ensure the login screen displays cleanly when unauthenticated.
  - Remove inline `style="display: none;"` from `#login-panel` across console HTML templates and trigger `showLogin()` when unauthenticated in `initConsole()`.
  - Render explicit in-panel "LOGIN REQUIRED: Admin authentication required" placeholder rows across `/console/` data tables (events, LLM usage, environment variables, system parameters) upon receiving HTTP 401 or 403 status codes.
  - Display status and detail messages within `/app/` metadata boxes and alert banners for HTTP 401, 402, 403, and 429 responses to prevent blank panels.
  - Add automated test `test_frontend_element_ids_and_login_forms_exist` asserting all JS-referenced element IDs exist in matching HTML templates and login forms are present.

### D-55: Production guard for administrative role elevation script
- **Status:** chosen, no advisor review, provisional
- **Context:** Granting administrative privileges directly alters authorization barriers, which in production allows access to system metrics, parameter configuration, event logs, and operational controls. Unintended elevation in production could compromise environment integrity.
- **Decision:**
  - `scripts/set_admin.py` strictly refuses execution when `APP_ENV=production` unless an explicit `--allow-production` flag is passed.
  - Role assignment modifies exclusively `app_metadata.role` via Supabase Admin API and never mutates `user_metadata` (keeping user-controlled claims separate from security-critical authorization).
  - Elevating a non-existent account terminates with an explicit error without creating the user.

### D-56: Multi-step agent orchestrator loop, tool registry, and entitlement guards (Batch X10)
- **Status:** chosen, no advisor review, provisional
- **Context:** An agent loop requires controlled execution across analytical tools wrapping Features 1, 2, and 3 without allowing unauthorized access or unconstrained token spend.
- **Decision:**
  - Wrap Feature 1 (`f1_contagion`), Feature 2 (`f2_filings`), and Feature 3 (`f3_portfolio`) with in-tool entitlement evaluation (`backend/app/agent/tools.py`). Feature denials are captured as explicit denied step outcomes rather than bypassed.
  - Define `AgentStep` contract in `backend/app/contracts/agent.py` with provisional fields: `step_number`, `tool_name`, `input_summary`, `output_summary`, `status`, `est_cost_usd`, and `duration_ms`.
  - Configure maximum steps (`agent_max_steps`), per-run budget (`agent_budget_usd`), and per-run timeout (`agent_timeout_seconds`) via `config/parameters.yaml`. Any violation terminates execution with a loud failure (`RuntimeError`, `BudgetExceededError`, `LLMTimeoutError`) without guessing.
  - Prohibit placeholder execution in production (`APP_ENV=production`); real Nemotron tool calling remains marked unverified until live credentials are provided.
  - Enforce financial advice guardrails (`assert_no_financial_advice`) on final answers and record step telemetry to `public.llm_ledger` without logging sensitive user data.

### D-57: Hosted demo mode for Feature 3 benchmark isolation
- **Status:** chosen, no advisor review, provisional
- **Context:** Raw benchmark price series live under `data/` and are gitignored and excluded by `.dockerignore`. In the hosted container image, raw benchmark prices are not shipped.
- **Decision:**
  - Introduce a configuration parameter `hosted_demo_mode` (boolean, default true) in `config/parameters.yaml`.
  - When `hosted_demo_mode` is enabled, POST `/f3/review` upload returns a clear HTTP 503 response: `"not available in the hosted demo: benchmark data is not shipped"`, while serving precomputed results via `/f3/demo`.
  - In local development mode (`hosted_demo_mode = false`), full trade log upload and custom benchmark replay calculations remain enabled.

### D-58: Unconfigured LLM provider in production HTTP 503 response and README env drift enforcement
- **Status:** chosen, no advisor review, provisional
- **Context:** In production (`APP_ENV=production`), when no verified LLM provider is configured (e.g. `NEBIUS_API_KEY` missing) or the placeholder provider is refused, requests to `/agent/ask` or `/llm/runtime_call` previously could return generic 500 errors. Upstream operational errors must be surfaced cleanly with appropriate HTTP semantics and standard error envelopes. Additionally, documentation of environment variables must not drift from code.
- **Decision:**
  - Introduce `ProviderNotConfiguredError` in `backend/app/llm/exceptions.py` mapped to HTTP 503 with error code `provider_not_configured`.
  - Both `/agent/ask` and `/llm/runtime_call` return HTTP 503 wrapped in `ErrorEnvelope` when no real provider is configured in production, never generic 500.
  - Automatically generate the README environment variable reference block from `backend.app.config.env.REGISTRY_BY_GROUP` via `scripts/generate_readme_env.py` and enforce zero-drift via automated test `test_readme_environment_variables_match_registry`.

### D-59: Frontend web application architecture and proxy prefix
- **Status:** Accepted
- **Context:** The frontend client requires access to the backend API without CORS complications or leaking direct backend addresses to the browser, while maintaining strict route isolation.
- **Decision:**
  - Use Next.js (TypeScript, App Router) in `frontend/web/`.
  - Enforce a single proxy prefix: `/backend/:path*` rewrites to `BACKEND_URL/:path*` (default `http://127.0.0.1:8000/:path*`).
  - No client-side rewrites for `/agent`, `/f1`, or other page routes.
  - Landing page makes zero backend calls.
  - Use `next/link` for internal navigation so that in-memory state survives transitions across pages.

### D-60: In-memory token storage lifecycle
- **Status:** Accepted
- **Context:** Web tokens (Supabase JWTs) must never be vulnerable to XSS exfiltration or persistent credential leaks.
- **Decision:**
  - Store JWT authentication tokens strictly in JavaScript runtime memory via React Context.
  - Never persist tokens to `localStorage`, `sessionStorage`, cookies, URLs, or console logs.
  - Page reloads intentionally clear the session, requiring re-authentication.

### D-61: Frontend development dependencies
- **Status:** Accepted
- **Context:** Component testing, DOM simulation, and structural state validation require dedicated lightweight test utilities without heavy browser automation dependencies.
- **Decision:**
  - Add `vitest` as the fast unit/integration test runner.
  - Add `jsdom` for DOM environment emulation in node.
  - Add `@testing-library/react` for React component render testing.
  - Prohibit Playwright, UI kits, Tailwind, 3D, and heavy chart libraries to maintain a lightweight, CPU-friendly build.

### D-62: Admin verification queue manual UUID entry and backend endpoint gap
- **Status:** Accepted
- **Context:** The backend exposes `POST /api/admin/verifications/{verification_id}/review`, but lacks a `GET /api/admin/verifications` list endpoint to fetch pending verification applications.
- **Decision:**
  - Log the absence of `GET /api/admin/verifications` as a backend gap without modifying backend code.
  - Frontend admin panel implements manual UUID entry for verification reviews.

### D-63: Self-hosted local font loading via next/font/local
- **Status:** Accepted
- **Context:** next/font/google attempts to fetch font assets from remote Google Fonts CDN endpoints during build, resulting in fallback to system fonts under offline, firewalled, or restricted network environments.
- **Decision:**
  - Self-host Newsreader (serif for headings), Source Sans 3 (sans for body text), and JetBrains Mono (monospace for numbers/code) locally within frontend/web/src/app/fonts/.
  - Place accompanying Open Font License (OFL) files alongside each font file.
  - Load fonts using next/font/local, eliminating all runtime and external font host requests.

### D-64: Feature 1 Tavily news integration gap in precomputed demo and TavilyRail component
- **Status:** Accepted
- **Context:** Feature 1 correlation scan precomputed demo endpoint `/f1/demo` returns quantitative statistical metrics and shifted pairs from `demo_data/f1_scan_demo.json` without news queries, results, or macro context citations.
- **Decision:**
  - Build the shared `TavilyRail` component displaying real states: loading, "not run: no key", "not generated", empty ("no results" with query), and error with status and body.
  - Surface the "not generated" state on `/contagion` when demo data lacks Tavily news items, reporting the absence as a backend gap in precomputed demo data without modifying backend logic.
  - Require https-only links with `rel="noopener noreferrer"` and enforce zero HTML rendering.

### D-65: Tavily scope restriction to Feature 1
- **Status:** Accepted
- **Context:** Features 2 (filings consistency) and 3 (trade log forensics) endpoints return XBRL metrics, rules, and portfolio replays without external news or search data.
- **Decision:**
  - Tavily exists only in Feature 1 in the backend.
  - Do not render `TavilyRail` on `/filings` and `/trade-log` when the backend returns no Tavily data.

### D-66: Hosted demo filings search and live company lookup backend gap
- **Status:** Accepted
- **Context:** Users require searching filings consistency audits for listed Indian equities across fiscal quarters. The hosted backend provides only `/f2/demo` serving precomputed evaluations for demo companies.
- **Decision:**
  - Log the backend gap "no endpoint for a live lookup of any listed company" without modifying backend services.
  - Frontend `/filings` search dynamically populates companies and fiscal periods from the `/f2/demo` response without hardcoding company symbols or periods.
  - When an uncataloged company is queried, display "Not in the precomputed demo. Available companies:" followed by the available companies list, and "A live lookup of any listed company is not available in the hosted demo."
  - When an unavailable period is requested for a known company, inform the user and list available periods.

### D-67: Dependency addition: openpyxl
- **Status:** chosen, no advisor review, provisional
- **Context:** Safe server-side parsing and tabular text extraction from `.xlsx` spreadsheets uploaded by users for financial analysis.
- **Decision:**
  - Add `openpyxl` as a backend dependency in `pyproject.toml`.
  - Read cell values only (`data_only=True`), never evaluate formulas, and ignore external links.

### D-68: Dependency addition: python-docx
- **Status:** chosen, no advisor review, provisional
- **Context:** Safe server-side text extraction from Word documents (`.docx`) provided as research briefs or financial notes.
- **Decision:**
  - Add `python-docx` as a backend dependency in `pyproject.toml`.
  - Process paragraphs and tables strictly in memory, rejecting macro-enabled documents.

### D-69: Dependency addition: pypdf
- **Status:** chosen, no advisor review, provisional
- **Context:** Safe in-memory text extraction from PDF financial reports and filing disclosures without external binary CLI dependencies.
- **Decision:**
  - Add `pypdf` as a backend dependency in `pyproject.toml`.
  - Extract text per page while enforcing configured page limits and execution timeouts.

### D-70: Dependency addition: yfinance
- **Status:** chosen, no advisor review, provisional
- **Context:** Live market price retrieval at request time for financial contagion analysis and trade log forensics.
- **Decision:**
  - Add `yfinance` as a backend dependency in `pyproject.toml`. It was not previously a dependency in the project.
  - Wrap invocations in `backend/app/data/yfinance_client.py` with an in-memory TTL cache, request caps, and live error surfacing. Never return raw vendor payloads; produce derived indicators only.

### D-71: Contract change: AgentAskRequest model tier and reference text
- **Status:** chosen, no advisor review, provisional
- **Context:** The agent orchestrator requires clients to choose an inference model tier (`fast`, `balanced`, `deep`) and optionally pass extracted attachment text as read-only reference data.
- **Decision:**
  - Extend `AgentAskRequest` in `backend/app/contracts/agent.py` with:
    - `model_tier: Literal["fast", "balanced", "deep"] = "balanced"`
    - `attachment_text: str | None = None`
  - When an unavailable or denied tier is requested, return HTTP 503 with standard error envelope.

### D-72: Contract change: Authentication refresh token and endpoint
- **Status:** chosen, no advisor review, provisional
- **Context:** Client authentication requires session continuity across token expiries without re-entering credentials.
- **Decision:**
  - Extend `LoginResponse` in `backend/app/auth/models.py` with `refresh_token: str | None = None`.
  - Add `RefreshRequest` (`refresh_token: str`) and `RefreshResponse` (`access_token: str`, `token_type: str`, `expires_in: int`, `refresh_token: str | None`).
  - Implement `POST /api/auth/refresh` returning HTTP 401 on expired or invalid refresh token.
  - Redact tokens from server logs.

### D-73: Live NSE corporate filing lookup and rate limiting
- **Status:** chosen, no advisor review, provisional
- **Context:** Feature 2 consistency audits require fetching official equity symbols and XBRL filing instances from the National Stock Exchange of India. Direct automated requests to `nseindia.com` trigger anti-bot protections, whereas the official NSE archive server `nsearchives.nseindia.com` serves equities and corporate XBRL files. NSE terms have not been read.
- **Decision:**
  - Log that NSE terms have not been read.
  - Require user authentication for live lookups via `GET /f2/lookup`.
  - Enforce a per-user daily lookup limit and a global NSE outbound request rate limit from `config/parameters.yaml`.
  - Retrieve equity listings and XBRL instances from `nsearchives.nseindia.com`.
  - Cache each parsed company-period result in memory with a configurable TTL. Never return raw XML or CSV files to the client.

### D-74: Annual-only rule restriction for operating cash flow and working capital
- **Status:** chosen, no advisor review, provisional
- **Context:** Indian corporate reporting regulations (SEBI Ind AS) require full cash flow statements and detailed balance sheet schedules primarily in annual financial statements; quarterly disclosures typically omit complete cash flow schedules.
- **Decision:**
  - Based on code inspection of `backend/app/features/f2_filings/rules.py` and `derived_metrics.py`, exactly Rules R5 (operating cash flow quality), R6 (working capital divergence), and metric DSO (days sales outstanding) require cash flow or receivables/inventory balance sheet items. Rule R7 evaluates understatements against growth and sector thresholds and does not require cash flow data.
  - Restrict R5, R6, and DSO to annual filings only. For quarterly filings, evaluate R5 and R6 as `not_applicable` with an explanatory reason.

### D-75: File extraction safety and zip bomb defenses
- **Status:** chosen, no advisor review, provisional
- **Context:** User file uploads (`.pdf`, `.docx`, `.xlsx`) pose denial-of-service, macro execution, formula injection, and zip bomb risks if parsed without strict limits.
- **Decision:**
  - Implement safe extraction in `backend/app/features/files/extractor.py` and expose `POST /files/extract`.
  - Reject `.xlsm` and any macro-enabled file formats immediately.
  - Read Excel values only (`data_only=True`), never evaluate untrusted cell formulas, and ignore external links.
  - Cap uncompressed size and entry count of `.docx` and `.xlsx` archives from `config/parameters.yaml` to defeat zip bombs.
  - Cap maximum PDF pages from `config/parameters.yaml`.
  - Enforce an extraction timeout from config; raise loud errors on timeout or MIME/extension mismatches. Process all uploads strictly in memory.

### D-76: Feature 3 trade log upload in hosted mode
- **Status:** chosen, no advisor review, provisional
- **Context:** Feature 3 previously blocked upload in hosted mode due to un-shipped static benchmark data. With live benchmark price retrieval via `yfinance_client`, trade log upload can operate in hosted environments.
- **Decision:**
  - Introduce `f3_hosted_upload_enabled` (boolean, default true) in `config/parameters.yaml`.
  - Allow `POST /f3/review` to process uploaded trade logs against live benchmark prices while maintaining the precomputed demo fallback `/f3/demo`.

### D-77: Dependency addition: react-markdown
- **Status:** chosen, no advisor review, provisional
- **Context:** Agent chat responses contain structured plain prose that must be safely formatted in the React UI without injecting raw server HTML.
- **Decision:**
  - Add `react-markdown` as a frontend dependency in `frontend/web/package.json`.
  - Disable raw HTML rendering completely to prevent XSS vulnerabilities.
  - Prohibit `dangerouslySetInnerHTML` across all UI views.
  - Format lists, bold text, inline code, and wrap long code blocks in collapsible containers.

### D-78: Session management via httpOnly cookies with 5-hour idle timeout
- **Status:** chosen, no advisor review, provisional
- **Context:** D-60 previously stored JWT tokens strictly in JavaScript runtime memory, causing full session loss on any page refresh and lacking idle session expiration.
- **Decision:**
  - Store the refresh token and last-activity timestamp in a secure `httpOnly` cookie managed strictly by Next.js server routes (`/api/auth/login`, `/api/auth/session`, `/api/auth/logout`).
  - Access tokens remain strictly in runtime memory, never written to cookies, `localStorage`, `sessionStorage`, URLs, or logs.
  - Configure cookie with `SameSite=Lax`, `Secure` in production, `HttpOnly`, and narrow path `/api/auth`.
  - Validate the `Origin` header on all Next.js auth server routes against server origin to prevent CSRF.
  - Enforce a 5-hour idle timeout configured via `SESSION_IDLE_HOURS = 5`.
  - Only deliberate user interactions (clicks, keypresses, navigation, throttled) update the last-activity timestamp via a dedicated server touch; background pre-expiry access token refreshes must never extend the idle window.
  - After 5 hours of inactivity, the session route clears the cookie and surfaces the sign-in prompt: "Signed out after 5 hours of no use."

### D-79: Model tier catalog endpoint gap
- **Status:** Accepted
- **Context:** The frontend agent interface provides model selection between Fast, Balanced, and Deep tiers. The backend exposes `POST /agent/ask` accepting `model_tier`, but does not provide an endpoint listing available model tiers or their live health.
- **Decision:**
-  - Log the absence of a `GET /llm/tiers` model tier catalog endpoint as a backend gap without changing backend code.
-  - Frontend presents Fast, Balanced, and Deep tiers (defaulting to Balanced).
-  - A tier is marked disabled and unavailable only upon receiving an HTTP 503 response from the backend specifying the tier unavailability reason.

### D-80: Request origin verification with Host comparison, loopback config list, and protocol-aware cookie flags
- **Status:** chosen, no advisor review, provisional
-**Context:** Following D-78 session cookie introduction, local testing revealed origin mismatches between localhost and 127.0.0.1, rigid cookie Secure flags dropping cookies on plain HTTP test environments, and client-side unauthenticated navigation loops on initial mount prior to session verification.
- **Decision:**
  - Verify `Origin` header host against request `Host` header, allowing matches dynamically.
  - Allow extra origins only from an explicit configuration list (`DEFAULT_EXTRA_ORIGINS`), ensuring localhost:3000 and 127.0.0.1:3000 interoperability without hardcoded fixed-host breakage.
  - Reject untrusted origins with HTTP 403 and error code `origin_rejected`.
  - Set cookie `Secure` flag only when the request protocol is https (or `x-forwarded-proto: https`) or `NODE_ENV === "production"`.
  - Require Next.js server auth routes to return standardized JSON with HTTP status and code.
  - Guard protected UI views with `sessionChecked` state in `AuthContext` to prevent premature redirects to `/login` during initial cookie exchange.
  - Verify session cookie storage immediately post-login, raising `cookie_storage_failed` if the browser fails to persist the cookie.

### D-81: Intentional frontend deprecation of legacy LLM endpoints
- **Status:** chosen, no advisor review, provisional
- **Context:** The frontend `/agent` interface was unified into a single chat interface and unrequested third-party news search components (`TavilyRail`) were eliminated in favor of clean, unified sections.
- **Decision:**
  - Deprecate frontend usage of `/llm/runtime_call` and `/llm/tavily_search`.
  - Mark `/llm/runtime_call` and `/llm/tavily_search` as intentionally unused in the frontend endpoint coverage audit (`src/tests/endpoint_coverage.test.ts`).

### D-82: Deletion of legacy plain HTML screens (frontend/app) and demo endpoints
- **Status:** Accepted
- **Context:** The legacy plain HTML screens in `frontend/app` relied on obsolete `/demo` endpoints and synthetic stubs, conflicting with the Real-Data Policy. Full modern functionality is consolidated under `frontend/web` (Next.js) and `frontend/console` (ops inspection).
- **Decision:**
  - Delete `frontend/app/` completely and remove its mount from `backend/app/main.py`.
  - Redirect root path `/` to `/console`.
  - Delete mock/demo endpoints (`/demo/*`), synthetic trade log scripts, and synthetic CSV datasets.
  - Direct all Feature 1, Feature 2, and Feature 3 workflows through live endpoints (`/f1/scan`, `/f2/companies`, `/f2/lookup`, `/f3/review`).
  - Provider injection applied across orchestrator, explanation, adjudication, and review modules with real provider instantiation in production and test helpers strictly isolated to tests.

### D-83: Fiscal year baseline expansion to FY01, Nifty 50 top group, and server-side equity search
- **Status:** Accepted
- **Context:** The legacy filings lookup loaded all NSE listed equities (~2,000+) directly into the browser on mount, ordering alphabetically by symbol without market importance or Nifty 50 prominence. The period picker only provided hardcoded choices starting at FY27.
- **Decision:**
  - Expand backend fiscal year range minimum from 2020 to 2001 (`FILINGS_FIRST_FISCAL_YEAR = 2001`, label `FY01`), enabling historical audits from Q1 FY01 through the current fiscal year computed dynamically from the calendar clock.
  - Implement `GET /f2/top50` fetching official Nifty 50 constituents live from `https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv` with cache TTL, displayed as the initial "Nifty 50" group.
  - Retain the full equity list on the server and introduce `GET /f2/search?q={query}` requiring 2+ characters, prioritizing symbol matches over company names, and capping at configured `f2_search_result_limit` (20 results).
  - Transition frontend filings picker to a calendar-style layout with dynamic fiscal year dropdown (FY01 to current FY), Q1–Q4 month buttons (Apr–Jun, Jul–Sep, Oct–Dec, Jan–Mar), Annual button, and disabled future quarters.

### D-84: Routing without prices, token limit guards, and nullable cost accounting
- **Status:** Accepted
- **Context:** Previously, an unset pricing entry in `config/models.yaml` triggered a 503 `price_not_set` error, blocking analytical requests to real inference providers when API keys were valid. Furthermore, the ledger required a non-null dollar cost, preventing tracking when upstream token costs were not configured.
- **Decision:**
  - Remove the 503 `price_not_set` refusal path from the router, allowing real calls to proceed directly to configured LLM providers without synthetic placeholders in any environment.
  - When pricing is unset, record token usage in `public.llm_ledger` with `est_cost_usd = null`, returning `null` cost in the response contract and displaying cost as "unknown" in replies and ops reports. Never use guessed or default prices.
  - Add configurable token limits in `config/parameters.yaml`: per-user daily token limits (`llm_per_user_daily_token_limit`, `llm_per_user_daily_token_limit_judge_all`) and per-call token limits (`llm_per_call_max_tokens`, `llm_per_call_max_tokens_judge_all`), with higher allocations for judge accounts.
  - Enforce token limits when pricing is unset, raising HTTP 429 (`quota_exceeded`) with UTC reset timestamp (`X-Reset-Time`) when exceeded. When pricing is set, USD budget guards and costs continue to function normally.

### D-85: Strict verbatim filing claim verification, financial company exclusion, and error taxonomy mapping
- **Status:** Accepted
- **Context:**
  1. POST `/agent/ask` returned bare HTTP 500 when errors occurred during LLM provider communication, output parsing, or ledger writes.
  2. The filings consistency audit previously fabricated stated claims by comparing reported metrics to themselves (`stated_value = rev_val`), producing false "pass" results on non-existent management statements, and displayed `-- = --` in the table.
  3. Financial institutions (banks, NBFCs, insurers) report non-standard Ind AS templates not supported by non-financial consistency metrics.
- **Decision:**
  1. Map agent errors deterministically: provider upstream error -> 502 `PROVIDER_ERROR` (with upstream status), ledger failure -> 500 `LEDGER_ERROR`, output parsing failure -> 502 `MODEL_OUTPUT_INVALID`. Bare HTTP 500 is eliminated from the agent router path, and server-side traces are logged internally only.
  2. Enforce strict verbatim quotes: claims must come exclusively from verified announcement text with exact quotes. If no claim text exists, R0-R7 return `not_applicable` with reason `"no management claim text available"`.
  3. Prohibit comparing a filed value with itself via `assert_not_same_field`, raising `ValueError` if `stated_value` and its source refer to the same field.
  4. Exclude financial institutions (banks, NBFCs, insurance companies) returning HTTP 422 `UNSUPPORTED_COMPANY_TYPE` with reason `"financial companies are not covered"`. Classification is derived from NSE industry data (`ind_nifty50list.csv`), sector names in `f2_financial_sectors`, symbol checks, and keywords in `f2_financial_keywords`.
  5. Fix frontend rule table: display verified claim quotes when available or `"No management claim text for this period."` when absent; show filed metrics with field name, formatted number, unit, and fiscal period without `-- = --`.

### D-86: Short-lived database connection lifecycle, closed-connection retry, and model success logging
- **Status:** chosen, no advisor review, provisional
- **Context:** `POST /agent/ask` previously failed with `500 LEDGER_ERROR: Failed to record call in ledger: the connection is closed` when an open database connection was held across long-running external LLM model calls and tools, or when connection shadowing closed an active handle prematurely.
- **Decision:**
  - Never hold a database connection across a model call or any external network call. Open fresh, short-lived connections immediately before each database write or read, and close them immediately in `finally:` blocks.
  - Implement connection liveness detection (`is_connection_closed`) and closed-connection retry in `record_llm_call` and `increment_quota_atomic`. If an operation encounters a closed or broken connection, retry once with a freshly opened short connection. If the second attempt fails, raise a loud `LedgerError` (HTTP 500 `LEDGER_ERROR`). Never drop a write silently.
  - Apply the short-lived connection pattern across all database access paths: `/agent/ask`, `/llm/runtime_call`, `/f1/scan`, `/f2/lookup`, `/files/extract`, entitlement guards, and auth routes.
  - Report model call completion status, tier, and token counts in server logs and error messages if ledger recording fails after a successful upstream inference call. Never log API keys or user prompts.
