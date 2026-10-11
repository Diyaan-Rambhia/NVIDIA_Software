# fininsight

Financial intelligence platform backend scaffold.

## Setup

Keep the repo outside OneDrive-synced folders once real keys exist.

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

### Configuration

All operational thresholds, window parameters, pricing plans, candidate universe, episodes, and financial lexicons are declared under `config/`:
- `config/parameters.yaml` — Domain parameters with strict bounds, defaults, units, and mutability flags
- `config/thresholds.yaml` — Quantitative tolerances and sector growth rates
- `config/plans.yaml` — Access definitions for retail, institutional, and judge tiers
- `config/universe.yaml` — Sector symbols excluding pharma and health candidates
- `config/episodes.yaml` — Candidate historical episodes (pending confirmation)
- `config/lexicon.yaml` — Normalized sentiment phrases and ambiguous terms

Validate and load full configuration at startup:
```python
from backend.app.config import load_all_config, resolve_parameters

cfg = load_all_config()
active_params = resolve_parameters({"W": 120})
```

### Application Shell & Ops Console

The FastAPI application shell (`create_app`) initializes structured JSON-line logging, echoes `X-Request-ID` or generates a UUID, routes all exceptions through the unified `ErrorEnvelope`, and exposes `/health` and `/ready` probes.

In development mode (`APP_ENV=development`), the basic ops console and inspection endpoints are available:
- `GET /ops/status` — Environment, code version, python version, uptime, and enabled groups
- `GET /ops/config` — Environment variable presence grouped with required status (never values)
- `GET /ops/parameters` — Loaded parameter register with bounds and units
- `GET /console/` — Dense technical diagnostics console (`index.html` and `config.html`)

Run the development server:
```bash
make run
```

### Verification

Run the test suite:

```bash
make test
```

Run lint and type checks:

```bash
make lint
```

Check environment variable configuration:

```bash
make check-env
```

## Provisional parameters, not reviewed by a finance professional

Educational only. The following values are provisional working parameters pending formal financial advisor review (DECISIONS.md D-26):
1. **Absorption ratio component count:** `k_fraction` 0.20 in `config/parameters.yaml` (`k` derived as `max(1, ceil(N * 0.20))`).
2. **Institutional performance metrics:** Daily return frequency, annualisation factor 252, and risk-free series "91-day T-bill yield (source decided in X1)".
3. **XIRR solver configuration:** Bracket `[-0.99, 10.0]`, tolerance `1e-9`, max iterations 200, grid points 1000.
4. **Quotas:** `institutional_paid` Feature 3 daily quota set to 5 (5x the `institutional_free` daily quota).
5. **Sector growth thresholds:** Conservative YoY strong-growth baseline floors in `config/thresholds.yaml` (FMCG 6%, IT services 8%, Autos 10%, Capital goods 12%, Metals 10%, Energy 8%, Telecom 8%, Consumer durables 10%, Other 8%), with provisional threshold labelling applied to candidate flags.

Note: Per-model LLM token prices remain pending and are not assigned provisional values.
