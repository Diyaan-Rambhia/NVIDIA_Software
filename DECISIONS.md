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
