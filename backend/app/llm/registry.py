"""Model registry resolving tiers (fast, balanced, deep) from the live Token Factory catalog."""

import json
import logging
import urllib.request
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import yaml

from backend.app.config.env import Settings, load_settings
from backend.app.llm.exceptions import (
    LLMUpstreamError,
    ModelResolutionError,
    PriceNotSetError,
    TierUnavailableError,
)

logger = logging.getLogger("backend.app.llm")


def load_models_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load model tier and pricing configuration from config/models.yaml."""
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


def resolve_tier_model(
    tier: str,
    live_model_ids: list[str],
    models_config: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Resolve a tier ('fast', 'balanced', 'deep', 'vision') to a concrete model ID.

    Rules:
    - Deny list: models matching deny_patterns (e.g. 'llama') are strictly prohibited.
    - Pattern order: patterns are evaluated strictly in configured order.
    - First allowed match: returns the first allowed model matching the highest-priority pattern.
    - Disabled tier: returns unavailable with configured reason (e.g. vision v2).
    - No match: returns unavailable with reason; never falls back to another tier/model.

    Returns:
        (resolved_model_id, None) if resolved.
        (None, reason) if unavailable.
    """
    deny_patterns = [p.lower() for p in models_config.get("deny_patterns", ["llama"])]
    tiers_cfg = models_config.get("tiers", {})

    canonical_tier = tier.lower().strip()
    if canonical_tier == "mid":
        canonical_tier = "balanced"

    if canonical_tier not in tiers_cfg:
        allowed = list(tiers_cfg.keys())
        return None, f"Unknown tier '{tier}'. Allowed tiers: {allowed}"

    cfg = tiers_cfg[canonical_tier]
    if not cfg.get("enabled", True) or cfg.get("status") == "disabled":
        return None, cfg.get("reason", f"Tier '{tier}' is disabled")

    patterns = cfg.get("patterns", [])
    if not patterns:
        return None, f"No search patterns configured for tier '{tier}'"

    # Filter out models matching deny patterns
    allowed_models = [
        mid for mid in live_model_ids
        if not any(deny in mid.lower() for deny in deny_patterns)
    ]

    # Resolve first allowed match following strict pattern order
    for pattern in patterns:
        pat_lower = pattern.lower()
        for mid in allowed_models:
            if pat_lower in mid.lower():
                return mid, None

    return None, f"No allowed model matching patterns {patterns} found in live catalog"


def match_alias_to_model(
    alias: str,
    live_model_ids: list[str],
    alias_config: dict[str, Any],
) -> str:
    """Resolve an alias to a concrete model ID (legacy wrapper)."""
    canonical = "balanced" if alias == "mid" else alias
    # Fallback to direct substring lookup if alias_config is old format
    cfg = alias_config.get(canonical) or alias_config.get(alias)
    if cfg:
        substrings = cfg.get("preferred_substrings") or cfg.get("patterns") or []
        for sub in substrings:
            for mid in live_model_ids:
                if "llama" not in mid.lower() and sub.lower() in mid.lower():
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
        self.tiers_cfg = self.config.get("tiers", {})
        self.aliases_cfg = self.config.get("aliases", {})
        self.resolved_models: dict[str, str] = {}
        self.unavailable_reasons: dict[str, str] = {}
        self.live_model_ids = live_model_ids

    def initialize(self) -> None:
        """Resolve all tiers against live models. Sets status or resolution per tier."""
        base_url = self.settings.get_var_value("NEBIUS_BASE_URL") or ""
        api_key = self.settings.get_var_value("NEBIUS_API_KEY") or ""

        if self.live_model_ids is None:
            self.live_model_ids = fetch_live_model_ids(base_url, api_key)

        for tier in ["fast", "balanced", "deep", "vision"]:
            resolved, reason = resolve_tier_model(tier, self.live_model_ids, self.config)
            if resolved:
                self.resolved_models[tier] = resolved
                if tier == "balanced":
                    self.resolved_models["mid"] = resolved
                logger.info("Resolved LLM tier '%s' to model ID: '%s'", tier, resolved)
            else:
                self.unavailable_reasons[tier] = reason or "unavailable"
                if tier == "balanced":
                    self.unavailable_reasons["mid"] = reason or "unavailable"
                logger.warning("LLM tier '%s' is unavailable: %s", tier, reason)

    def get_tier_model_id(self, tier: str) -> str:
        """Retrieve resolved model ID for tier, or raise TierUnavailableError."""
        canonical = "balanced" if tier == "mid" else tier
        if canonical in self.resolved_models:
            return self.resolved_models[canonical]
        reason = self.unavailable_reasons.get(canonical, f"Tier '{tier}' has not been resolved")
        raise TierUnavailableError(tier=tier, reason=reason)

    def get_model_id(self, alias: str) -> str:
        """Retrieve resolved model ID for alias/tier."""
        return self.get_tier_model_id(alias)

    def is_tier_available(self, tier: str) -> bool:
        """Check whether a given tier was successfully resolved."""
        canonical = "balanced" if tier == "mid" else tier
        return canonical in self.resolved_models

    def get_tier_unavailable_reason(self, tier: str) -> str | None:
        """Retrieve unavailable reason for tier if not available."""
        canonical = "balanced" if tier == "mid" else tier
        return self.unavailable_reasons.get(canonical)

    def get_pricing(self, alias: str) -> tuple[float, float]:
        """Retrieve (price_per_1m_input, price_per_1m_output) in USD."""
        canonical = "balanced" if alias == "mid" else alias
        cfg = self.tiers_cfg.get(canonical) or self.aliases_cfg.get(canonical)
        if not cfg:
            raise ModelResolutionError(f"No pricing configured for tier/alias '{alias}'")
        in_p = cfg.get("price_per_1m_input_usd")
        out_p = cfg.get("price_per_1m_output_usd")
        if in_p is None or out_p is None:
            raise PriceNotSetError(canonical)
        return (float(in_p), float(out_p))
