"""OpenAI-compatible HTTP client wrapper for Nebius Token Factory."""

import json
import logging
import time
import urllib.request
import uuid
from typing import Any
from urllib.error import HTTPError, URLError

from backend.app.config.env import Settings, load_settings
from backend.app.db.connection import get_connection
from backend.app.llm.cache import ResponseCache, make_cache_key
from backend.app.llm.exceptions import (
    LedgerError,
    LLMTimeoutError,
    LLMUpstreamError,
    ModelOutputInvalidError,
)
from backend.app.llm.guard import assert_no_financial_advice
from backend.app.llm.ledger import calculate_cost_usd, check_budget_guard, record_llm_call
from backend.app.llm.registry import ModelRegistry

logger = logging.getLogger("backend.app.llm")


class LLMClient:
    """Wrapper calling Token Factory OpenAI-compatible endpoints with guards and accounting."""

    def __init__(
        self,
        registry: ModelRegistry,
        settings: Settings | None = None,
        cache: ResponseCache | None = None,
    ) -> None:
        self.registry = registry
        self.settings = settings or load_settings()
        self.cache = cache or ResponseCache()
        self.base_url = self.settings.get_var_value("NEBIUS_BASE_URL") or ""
        self.api_key = self.settings.get_var_value("NEBIUS_API_KEY") or ""

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
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send completion request to resolved model with retries, caching, and guards."""
        model_id = self.registry.get_model_id(alias)
        pricing = self.registry.get_pricing(alias)

        call_params: dict[str, Any] = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
            "response_format": response_format,
        }
        cache_key = make_cache_key(model_id, messages, call_params)

        # 1. Check cache
        cached = self.cache.get(cache_key, bypass_cache=bypass_cache)
        if cached is not None:
            logger.info("LLM cache hit for alias '%s' (%s)", alias, model_id)
            # Record zero-token cache hit in ledger
            try:
                conn = get_connection(self.settings, autocommit=True)
                record_llm_call(
                    conn=conn,
                    user_id=user_id,
                    route=route,
                    alias=alias,
                    model_id=model_id,
                    input_tokens=0,
                    output_tokens=0,
                    est_cost_usd=0.0,
                    cache_hit=True,
                )
                conn.close()
            except Exception as exc:
                logger.warning("Failed to record cache hit in ledger: %s", exc)
            return cached

        # 2. Check budget guard or token limit guard
        estimated_in = sum(len(m.get("content") or "") for m in messages) // 4 + 100
        estimated_out = max_tokens or 1000
        projected_tokens = estimated_in + estimated_out

        if pricing is not None:
            projected_cost = calculate_cost_usd(estimated_in, estimated_out, pricing[0], pricing[1])
            daily_budget_str = self.settings.get_var_value("DAILY_LLM_BUDGET_USD")
            test_budget_str = self.settings.get_var_value("TEST_DAILY_LLM_BUDGET_USD")
            effective_budget = float(test_budget_str or daily_budget_str or 0.0)

            conn = get_connection(self.settings, autocommit=True)
            try:
                check_budget_guard(conn, projected_cost, effective_budget)
            finally:
                conn.close()
        else:
            from backend.app.config.loader import load_all_config
            from backend.app.llm.ledger import check_token_limit_guard

            cfg = load_all_config()
            params = cfg.parameters.parameters if cfg else {}
            p_daily = params.get("llm_per_user_daily_token_limit")
            p_call = params.get("llm_per_call_max_tokens")
            daily_token_limit = int(p_daily.default) if p_daily else 0
            call_max_tokens = int(p_call.default) if p_call else 0

            guard_conn = None
            try:
                guard_conn = get_connection(self.settings, autocommit=True)
            except Exception:
                guard_conn = None
            try:
                check_token_limit_guard(
                    conn=guard_conn,
                    user_id=user_id,
                    projected_tokens=projected_tokens,
                    daily_limit=daily_token_limit,
                    call_max_tokens=call_max_tokens,
                    settings=self.settings,
                )
            finally:
                if guard_conn is not None:
                    try:
                        guard_conn.close()
                    except Exception:
                        pass

        # 3. Prepare payload and call upstream
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload_dict: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload_dict["max_tokens"] = max_tokens
        if tools is not None:
            payload_dict["tools"] = tools
        if response_format is not None:
            payload_dict["response_format"] = response_format

        read_timeout = 120 if alias == "deep" else 60
        req_data = json.dumps(payload_dict).encode("utf-8")

        # Retry loop: up to 2 retries on 429 and 5xx only with exponential backoff
        max_retries = 2
        last_exc: Exception | None = None

        for attempt in range(max_retries + 1):
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=read_timeout) as resp:
                    raw_body = resp.read().decode("utf-8")
                    try:
                        resp_data = json.loads(raw_body)
                    except (json.JSONDecodeError, UnicodeDecodeError) as json_err:
                        raise ModelOutputInvalidError(
                            f"MODEL_OUTPUT_INVALID: Failed to parse provider response: {json_err}"
                        ) from json_err
                    break
            except HTTPError as exc:
                err_text = exc.read().decode("utf-8")
                last_exc = LLMUpstreamError(exc.code, err_text)
                if exc.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                    backoff = 2**attempt
                    logger.warning(
                        "Upstream HTTP %s, retrying in %ds (attempt %d/%d)",
                        exc.code,
                        backoff,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(backoff)
                    continue
                raise last_exc from exc
            except (URLError, TimeoutError) as exc:
                last_exc = LLMTimeoutError(f"Request timed out or failed: {exc}")
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                raise last_exc from exc
        else:
            if last_exc:
                raise last_exc
            raise LLMTimeoutError("Max retries exceeded")

        # 4. Extract content and assert advice guard
        choice = resp_data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content") or msg.get("reasoning_content") or ""
        assert_no_financial_advice(content)

        # 5. Extract actual tokens and record in ledger
        usage = resp_data.get("usage", {})
        actual_in = usage.get("prompt_tokens", estimated_in)
        actual_out = usage.get("completion_tokens", 0)
        actual_cost = (
            calculate_cost_usd(actual_in, actual_out, pricing[0], pricing[1])
            if pricing is not None
            else None
        )

        model_call_status = "success"
        try:
            record_llm_call(
                conn=conn,
                user_id=user_id,
                route=route,
                alias=alias,
                model_id=model_id,
                input_tokens=actual_in,
                output_tokens=actual_out,
                est_cost_usd=actual_cost,
                cache_hit=False,
                settings=self.settings,
            )
        except Exception as exc:
            logger.error(
                "Model call succeeded (tier=%s, input_tokens=%d, output_tokens=%d, status=%s), but ledger recording failed: %s",
                alias,
                actual_in,
                actual_out,
                model_call_status,
                exc,
            )
            raise LedgerError(
                f"LEDGER_ERROR: Failed to record call in ledger (model call succeeded: tier={alias}, tokens={actual_in}+{actual_out}, status={model_call_status}): {exc}"
            ) from exc


        # 6. Save to cache
        self.cache.set(cache_key, resp_data)

        return resp_data
