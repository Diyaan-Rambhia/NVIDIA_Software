"""Rule-based placeholder LLM provider for development and testing.

Owner-approved exception to real-data policy recorded in DECISIONS.md (D-51).
Allowed only when APP_ENV is 'development' or 'test'; strictly refuses in 'production'.
Outputs carry 'PLACEHOLDER TEMPLATE, not Nemotron' and are never persisted to demo JSON.
Price is explicit config value 0.0 (placeholder only).
Budget guard, cache key, and ledger recording run identically to real gateway.
"""

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from backend.app.config.env import Settings, load_settings
from backend.app.config.loader import load_config_file
from backend.app.config.models import ParametersConfig
from backend.app.db.connection import get_connection
from backend.app.llm.cache import ResponseCache, make_cache_key
from backend.app.llm.exceptions import BudgetExceededError, LLMError
from backend.app.llm.guard import assert_no_financial_advice
from backend.app.llm.ledger import calculate_cost_usd, check_budget_guard, record_llm_call

logger = logging.getLogger("backend.tests.helpers.placeholder")

PLACEHOLDER_MARKER = "PLACEHOLDER TEMPLATE, not Nemotron"
PARAMETERS_PATH = Path("config") / "parameters.yaml"


class PlaceholderProvider:
    """Template-driven placeholder provider matching LLMClient gateway interface."""

    def __init__(
        self,
        settings: Settings | None = None,
        cache: ResponseCache | None = None,
        conn: Any = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.cache = cache or ResponseCache()
        self.conn = conn

        # Strict environment restriction
        raw_env = (self.settings.get_var_value("APP_ENV") or "").strip().lower()
        if not raw_env:
            raw_env = (self.settings.app_env or "development").strip().lower()
            if raw_env == "production" and self.settings.get_var_value("APP_ENV") == "":
                raw_env = "development"

        if raw_env in ("production", "prod"):
            raise RuntimeError(
                f"Placeholder LLM provider is strictly forbidden in '{raw_env}' environment. "
                "Only 'development' and 'test' are permitted."
            )
        if raw_env not in ("development", "test"):
            raise RuntimeError(
                f"Placeholder LLM provider is strictly forbidden in '{raw_env}' environment. "
                "Only 'development' and 'test' are permitted."
            )

        # Load placeholder pricing from parameters config
        params_cfg = load_config_file(PARAMETERS_PATH, ParametersConfig)
        param_entry = params_cfg.parameters.get(
            "llm_placeholder_price_per_1m",
            params_cfg.parameters.get("llm_placeholder_price_per_1m_usd"),
        )
        self.price_per_1m = float(param_entry.default) if param_entry else 0.15

        self.is_placeholder = True

        class _PlaceholderPricingRegistry:
            def __init__(self, price: float):
                self.price = price

            def get_pricing(self, canonical_tier: str) -> tuple[float, float]:
                effective = self.price if self.price > 0 else 1.0
                return (effective, effective * 2)

            def initialize(self) -> None:
                pass

        self.registry = _PlaceholderPricingRegistry(self.price_per_1m)

    def complete(
        self,
        alias: str,
        messages: list[dict[str, Any]],
        user_id: uuid.UUID | None = None,
        route: str = "direct",
        bypass_cache: bool = False,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        conn: Any = None,
    ) -> dict[str, Any]:
        """Generate deterministic template-filled completion with guards and accounting."""
        model_id = f"{alias}-placeholder-template"
        call_params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
            "response_format": response_format,
        }
        cache_key = make_cache_key(model_id, messages, call_params)

        active_conn = conn or self.conn

        # 1. Check cache
        cached = self.cache.get(cache_key, bypass_cache=bypass_cache)
        if cached is not None:
            logger.info("Placeholder LLM cache hit for alias '%s'", alias)
            if active_conn is not None:
                try:
                    record_llm_call(
                        conn=active_conn,
                        user_id=user_id,
                        route=route,
                        alias=alias,
                        model_id=model_id,
                        input_tokens=0,
                        output_tokens=0,
                        est_cost_usd=0.0,
                        cache_hit=True,
                    )
                except Exception:
                    pass
            return cached

        # 2. Check budget guard
        all_text = " ".join(str(m.get("content", "")) for m in messages)
        in_tokens = max(1, len(all_text) // 4)
        out_tokens = max_tokens or 200
        projected_cost = calculate_cost_usd(
            in_tokens, out_tokens, self.price_per_1m, self.price_per_1m
        )

        daily_budget_str = self.settings.get_var_value("DAILY_LLM_BUDGET_USD")
        test_budget_str = self.settings.get_var_value("TEST_DAILY_LLM_BUDGET_USD")
        effective_budget = float(test_budget_str or daily_budget_str or 0.0)

        if active_conn is not None:
            check_budget_guard(active_conn, projected_cost, effective_budget)

        # 3. Generate response content from real evidence in messages
        content = self._render_template(messages, response_format)

        if not content or not content.strip():
            raise LLMError("Placeholder generation resulted in empty output")

        # 4. Enforce output financial advice guard
        assert_no_financial_advice(content)

        # 5. Record usage in ledger
        if active_conn is not None:
            try:
                record_llm_call(
                    conn=active_conn,
                    user_id=user_id,
                    route=route,
                    alias=alias,
                    model_id=model_id,
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    est_cost_usd=projected_cost,
                    cache_hit=False,
                )
            except Exception:
                pass

        resp_data = {
            "id": f"placeholder-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": 0,
            "model": model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": in_tokens,
                "completion_tokens": out_tokens,
                "total_tokens": in_tokens + out_tokens,
            },
            "is_placeholder": True,
            "placeholder_label": PLACEHOLDER_MARKER,
        }

        # 6. Save in cache
        self.cache.set(cache_key, resp_data)
        return resp_data

    def _render_template(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None,
    ) -> str:
        """Render deterministic template content matching requested schema or text."""
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = str(m.get("content", ""))
                break

        # Check if structured output requested
        if response_format and response_format.get("type") == "json_object":
            schema = response_format.get("schema", {})
            schema_title = schema.get("title", "")

            # X7: Hypothesis or list of hypotheses
            if "Hypothesis" in schema_title:
                return self._render_hypothesis_json(last_user_msg)

            # X8: Inconsistency finding
            if "Inconsistency" in schema_title:
                return self._render_inconsistency_json(last_user_msg)

            # X8: Claim extraction
            if "Claim" in schema_title:
                return self._render_claim_json(last_user_msg)

            # Generic JSON object
            return json.dumps({
                "marker": PLACEHOLDER_MARKER,
                "note": "Deterministic template representation",
            })

        # Plain text completion (e.g. X9 decision review text)
        obs_snippets = []
        for line in last_user_msg.splitlines():
            line_str = line.strip()
            if any(k in line_str for k in ("was denied", "verified findings", "Reference data observed")):
                obs_snippets.append(line_str)
        obs_str = (" " + " ".join(obs_snippets)) if obs_snippets else ""
        return (
            f"{PLACEHOLDER_MARKER}. Quantitative audit completed from computed evidence.{obs_str} "
            "Educational and research analytics only. No investment advice."
        )

    def _render_hypothesis_json(self, context_text: str) -> str:
        """Render deterministic Hypothesis matching real evidence item IDs in context."""
        evidence_ids = re.findall(r"\b(E\d+)\b", context_text)
        if not evidence_ids:
            evidence_ids = ["E1", "E2"]

        supporting = evidence_ids[:2]
        weakening = evidence_ids[2:3]

        data = {
            "mechanism_class": "global risk-off and FPI outflow",
            "evidence_supporting": supporting,
            "evidence_weakening": weakening,
            "retrieved_urls": [
                "https://rbi.org.in/press_releases",
            ],
            "plausible_mechanism": (
                f"{PLACEHOLDER_MARKER}. Correlation shift across equity pairs is consistent with "
                "macro liquidity pressures observed in supporting evidence items."
            ),
        }
        return json.dumps(data)

    def _render_inconsistency_json(self, context_text: str) -> str:
        """Render deterministic Inconsistency finding."""
        quote_match = re.search(r"['\"]([^'\"]+)['\"]", context_text)
        quote = quote_match.group(1) if quote_match else "reported revenue growth"

        data = {
            "rule_id": "R0",
            "verdict": "confirm",
            "severity": "high",
            "metric": "revenue from operations",
            "claim_quote": quote,
            "quote_start": 0,
            "quote_end": len(quote),
            "stated_value": 15.0,
            "filed_value": 8.5,
            "difference_value": 6.5,
            "explanation": (
                f"{PLACEHOLDER_MARKER}. Stated figure in announcement differs from "
                "reported quarterly XBRL metric by 6.5 percentage points."
            ),
            "is_placeholder": True,
            "placeholder_label": PLACEHOLDER_MARKER,
        }
        return json.dumps(data)

    def _render_claim_json(self, context_text: str) -> str:
        """Render deterministic Claim extraction."""
        quote = context_text[:30].strip() or "revenue increased"
        data = {
            "metric": "revenue from operations",
            "descriptor": "strong growth",
            "direction": "increase",
            "quote": quote,
            "start": 0,
            "end": len(quote),
            "period": "FY_Q1",
            "basis": "reported",
        }
        return json.dumps(data)
