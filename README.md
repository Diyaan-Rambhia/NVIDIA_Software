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
