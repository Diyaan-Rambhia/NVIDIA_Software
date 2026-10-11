# Architecture & Engineering Decisions

### D-01: Minimal package skeleton for Phase A0
- **Status:** Accepted
- **Context:** Initial repo layout requires non-implemented modules per PROJECT.md §3.4.
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
- **Context:** Operational parameters APP_ENV and LOG_LEVEL establish execution mode and logging verbosity prior to any external service setup.
- **Decision:** Assign default values in Settings (APP_ENV to 'production', LOG_LEVEL to 'INFO') and set required_when_group_enabled to False for both in the registry. Function presence() reports them as present by virtue of these defaults even when absent from .env or process environment. Secrets must never have defaults.

### D-07: Static configuration loading and parameter resolution (A0.4)
- **Status:** Accepted
- **Context:** Domain parameters, analytical thresholds, pricing tiers, sector universes, historical episodes, and financial lexicons must be completely configured via declarative YAML files, validated strictly with Pydantic v2 schemas (`extra="forbid"`), and avoid hardcoding in Python logic.
- **Decision:** Store all baseline parameters and thresholds under `config/` (`parameters.yaml`, `thresholds.yaml`, `plans.yaml`, `universe.yaml`, `episodes.yaml`, `lexicon.yaml`). Validate using Pydantic v2 models raising `ConfigError` naming file and field. Support run-time overrides via `resolve_parameters(overrides)` raising `ParameterError` for bound, mutability, or type violations, and cross-validate time windows with `validate_window_consistency()`. No new external dependencies added.

### D-08: Deferral of contract model definitions pending batch implementation (A0.5)
- **Status:** Accepted
- **Context:** PROJECT.md §7.3 lists contract models by name (`Portfolio`, `CorrelationScan`, `EvidencePack`, `Hypothesis`, `Claim`, `FilingMetric`, `Inconsistency`, `TradeLog`, `DecisionReview`, `AgentStep`, `ColumnMapping`, error envelope) without defining explicit field names, types, or schemas in §7.3. Inventing or freezing speculative schemas ahead of batch requirements risks divergence and breaking changes.
- **Decision:** Mark contract models listed in PROJECT.md §7.3 as "contract pending". Defer concrete model definitions until their respective consuming batches:
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

### D-11: Alignment of plans configuration with PROJECT.md specifications (A1)
- **Status:** Accepted
- **Context:** `config/plans.yaml` previously deviated from PROJECT.md §4.3: retail tiers configured limited/full access to Feature 1 contagion scan instead of hard segment restriction, and institutional_free lacked locked upgrade linkage.
- **Decision:** Correct `config/plans.yaml` to strictly match PROJECT.md §4.3: Feature 1 is configured with `access: none` on `retail_free` and `retail_paid`, and `access: locked` with `unlocks_with: institutional_paid` on `institutional_free`. Feature 3 on `retail_free` and `institutional_free` is configured with `access: limited`.

### D-12: Transition to daily quotas and configurable reset cadence (A1)
- **Status:** Accepted (finance advisor to confirm: daily vs monthly)
- **Context:** PROJECT.md FR-QUO-001 and PROGRESS.md A1.3 specify daily quota enforcement with UTC boundary calculation, whereas initial schema defined monthly fields.
- **Decision:** Rename `quota_per_month` to `quota_per_day` across `FeatureRule` schema and `config/plans.yaml`. Discard all monthly figures. Use only daily values explicitly specified in PROJECT.md:
  - `retail_free`: F2 = 3 analyses/day, F3 = 1 log/day (FR-QUO-001)
  - `institutional_free`: F2 = 3 analyses/day, F3 = 1 log/day (§4.3, same as retail_free)
  - `institutional_paid`: F3 quota is resolved by D-26 (5/day, provisional, no advisor review).
  Reset schedule is driven by `reset_rule: utc_calendar_day` in `config/plans.yaml` and loaded via `PlansConfig`, ensuring no hardcoded cadence in calculation logic.

### D-13: Canonical Indian fiscal period format and trading calendar alignment policy (A2.1)
- **Status:** Accepted
- **Context:** Project specifications (PROJECT.md §4.1, §FR-FIL-006, and financial context notes) reference Indian quarterly periods using the pattern "Q1 FY27" (April-June 2026), while multi-asset alignment requires strict data integrity without silent dropping or forward-filling.
- **Decision:** Restrict fiscal period label parsing exclusively to the canonical format demonstrated across the specification: `Q[1-4] FY\d{2}` (e.g. `Q1 FY27`). All alternative or non-canonical formats are rejected with an explicit `ValueError`. Multi-series calendar alignment enforces an exact match against the provided trading calendar dates, surfacing missing data (gaps), dates outside the calendar, non-positive prices, and mixed naive/aware datetimes with loud failures.

### D-14: NumPy dependency for array and matrix computations (A2.2)
- **Status:** Accepted
- **Context:** Core statistical and correlation estimators require fast, vectorised array operations and eigenvalue decomposition.
- **Decision:** Add `numpy` to `pyproject.toml` dependencies.

### D-15: SciPy dependency for rank correlation and statistics (A2.2)
- **Status:** Accepted
- **Context:** Robustness check against volatility bias requires Spearman rank correlation per PROJECT.md §5.4.
- **Decision:** Add `scipy` to `pyproject.toml` dependencies to provide `scipy.stats.spearmanr`.

### D-16: scikit-learn dependency for Ledoit-Wolf covariance shrinkage (A2.2)
- **Status:** Accepted
- **Context:** High-dimensional asset covariance matrices with limited sample length require Ledoit-Wolf shrinkage per PROJECT.md §5.2.
- **Decision:** Add `scikit-learn` to `pyproject.toml` dependencies for `sklearn.covariance.ledoit_wolf`.

### D-17: Pure estimator conventions, parameters, and pending values (A2.2)
- **Status:** Accepted
- **Context:** Estimators require explicit definitions for EWMA initialization, Forbes-Rigobon variance calculation, absorption-ratio matrix representation, and component count parameterization.
- **Decision:**
  - **EWMA initialization:** PROJECT.md §5.2 states initialization from the first W observations. Sample covariance of the first W observations (`ddof=1`) serves as initial matrix Σ_0, recursively updated via Σ_t = λ Σ_{t-1} + (1 - λ) r_t r_tᵀ with zero-mean returns (docs silent, standard choice).
  - **Forbes-Rigobon variance definition:** PROJECT.md §5.3 defines relative variance shift δ = σ²_x,high / σ²_x,low - 1. Docs silent on sample variance degrees of freedom; standard choice: unbiased sample variance `ddof=1` (docs silent, standard choice).
  - **Absorption-ratio matrix choice:** PROJECT.md §5.5 specifies correlation matrix, whereas parameter register notes advisor confirmation is pending; standard choice: correlation matrix (docs silent, standard choice).
  - **Absorption ratio component count k:** Window bounds and parameter defaults come strictly from configuration (`parameters.yaml`). Integer component count `k` is not specified as a static integer in config (which provides `k_fraction`), so `k` is a required argument with no default in `absorption_ratio` and is marked pending advisor confirmation.

### D-18: Standard day-count basis named constant for XIRR (A2.3)
- **Status:** Accepted
- **Context:** PROJECT.md §5.11 and 10_parameters_register.md §5 establish standard spreadsheet convention of 365 days per year for XIRR cash flow discounting. Bare literals are forbidden in logic.
- **Decision:** Define named constant `DAYS_PER_YEAR = 365.0` in `backend/app/features/f3_log/xirr.py`.

### D-19: Moving-block bootstrap algorithm and output conventions (A2.3)
- **Status:** Accepted
- **Context:** PROJECT.md §5.6 specifies moving-block bootstrap with recorded seed. Block wrapping, partial block handling, and output distribution format are not explicitly detailed in finance docs.
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
  - Pending parameters: `annualisation_factor` (required argument without default, pending advisor confirmation on return cadence) and risk-free series specification.

### D-23: Derived filing metrics and validation constraints (A2.4)
- **Status:** Accepted
- **Context:** Financial filing analysis requires strict period matching, non-zero denominator guards, dynamic calendar day counts, and unit consistency.
- **Decision:**
  - YoY and QoQ growth: Strict validation requiring matching prior fiscal quarter (`t - 4Q` for YoY, `t - 1Q` for QoQ); zero or negative base raises `ParameterError`.
  - DSO: Uses dynamic fiscal period calendar day count computed via A2.1 fiscal utilities (`fiscal_period_to_dates`). Non-positive revenue raises `ParameterError`.
  - Margins and OCF: Revenue from operations must be strictly positive; non-positive revenue or PAT raises `ParameterError`.
  - Q4 derivation: Subtraction of 9M cumulative from annual figure requires matching fiscal year and identical unit. Negative derived revenue raises `ParameterError`; negative derived profit (loss) is permitted; other negative types pending advisor confirmation.

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





