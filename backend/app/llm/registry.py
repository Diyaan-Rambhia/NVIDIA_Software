"""Model registry resolving aliases (fast, mid, deep) from the live Token Factory catalog."""

import json
import logging
import urllib.request
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import yaml

from backend.app.config.env import Settings, load_settings
from backend.app.llm.exceptions import LLMUpstreamError, ModelResolutionError

logger = logging.getLogger("backend.app.llm")


def load_models_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load model alias and pricing configuration from config/models.yaml."""
    if config_path is None:
        root_dir = Path(__file__).resolve().parent.parent.parent.parent
        config_path = root_dir / "config" / "models.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Models configuration file not found at: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_live_model_ids(base_url: str, api_key: str) -> list[str]:
    """Fetch model IDs from the OpenAI-compatible /models endpoint."""
    if not base_url or not api_key:
        raise ModelResolutionError(
            "NEBIUS_BASE_URL and NEBIUS_API_KEY must be configured to fetch live model catalog"
        )

    url = f"{base_url.rstrip('/')}/models"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
            return [m["id"] for m in models if "id" in m]
    except HTTPError as exc:
        raise LLMUpstreamError(exc.code, exc.read().decode("utf-8")) from exc
    except (URLError, TimeoutError) as exc:
        raise ModelResolutionError(f"Failed to connect to model catalog at {url}: {exc}") from exc


def match_alias_to_model(
    alias: str,
    live_model_ids: list[str],
    alias_config: dict[str, Any],
) -> str:
    """Resolve an alias to a concrete model ID from the live catalog.

    Never hardcodes IDs. If no match is found in the live list, raises ModelResolutionError.
    """
    if alias not in alias_config:
        allowed = list(alias_config.keys())
        raise ModelResolutionError(f"Unknown alias '{alias}'. Allowed aliases: {allowed}")

    cfg = alias_config[alias]
    preferred_substrings = [s.lower() for s in cfg.get("preferred_substrings", [])]

    # Look for exact or substring matches in live model list
    for sub in preferred_substrings:
        for mid in live_model_ids:
            if sub in mid.lower():
                return mid

    raise ModelResolutionError(
        f"Unable to resolve model alias '{alias}' from live model list: {sorted(live_model_ids)}"
    )


class ModelRegistry:
    """Manages active resolved models and their token pricing."""

    def __init__(
        self,
        settings: Settings | None = None,
        config_path: Path | None = None,
        live_model_ids: list[str] | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.config = load_models_config(config_path)
        self.aliases_cfg = self.config.get("aliases", {})
        self.resolved_models: dict[str, str] = {}
        self.live_model_ids = live_model_ids

    def initialize(self) -> None:
        """Resolve all aliases against live models. Raises if any alias fails to resolve."""
        base_url = self.settings.get_var_value("NEBIUS_BASE_URL") or ""
        api_key = self.settings.get_var_value("NEBIUS_API_KEY") or ""

        if self.live_model_ids is None:
            self.live_model_ids = fetch_live_model_ids(base_url, api_key)

        for alias in ["fast", "mid", "deep"]:
            resolved = match_alias_to_model(alias, self.live_model_ids, self.aliases_cfg)
            self.resolved_models[alias] = resolved
            logger.info("Resolved LLM alias '%s' to model ID: '%s'", alias, resolved)

    def get_model_id(self, alias: str) -> str:
        """Retrieve resolved model ID for alias."""
        if alias not in self.resolved_models:
            raise ModelResolutionError(f"Alias '{alias}' has not been resolved")
        return self.resolved_models[alias]

    def get_pricing(self, alias: str) -> tuple[float, float]:
        """Retrieve (price_per_1m_input, price_per_1m_output) in USD."""
        if alias not in self.aliases_cfg:
            raise ModelResolutionError(f"No pricing configured for alias '{alias}'")
        cfg = self.aliases_cfg[alias]
        in_p = cfg.get("price_per_1m_input_usd")
        out_p = cfg.get("price_per_1m_output_usd")
        if in_p is None or out_p is None:
            raise ModelResolutionError(
                f"Pricing for model '{alias}' is pending. Calls to this model are refused."
            )
        return (float(in_p), float(out_p))
