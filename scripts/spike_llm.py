"""Spike script testing LLM capabilities on Nebius Token Factory per PROGRESS.md X3.6."""

import logging
import sys
from typing import Any

from pydantic import BaseModel, Field

from backend.app.config.env import load_settings
from backend.app.llm.client import LLMClient
from backend.app.llm.registry import ModelRegistry
from backend.app.llm.structured import complete_structured
from backend.app.llm.tools import execute_tool_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("spike_llm")


class SimpleFinancialEntity(BaseModel):
    """Schema model for JSON capability probe."""
    company_name: str
    symbol: str
    metric: str
    value_inr_crore: float = Field(description="Numerical value in INR crore")


def dummy_stock_lookup(symbol: str) -> dict[str, Any]:
    """Test tool callable by LLM."""
    return {"symbol": symbol, "status": "active", "exchange": "NSE"}


def run_spike() -> None:
    """Run capability spike across Nano, Super, Ultra and print summary table."""
    settings = load_settings()
    base_url = settings.get_var_value("NEBIUS_BASE_URL")
    api_key = settings.get_var_value("NEBIUS_API_KEY")

    if not base_url or not api_key:
        print("ERROR: NEBIUS_BASE_URL or NEBIUS_API_KEY not configured in environment.")
        sys.exit(1)

    registry = ModelRegistry(settings=settings)
    try:
        registry.initialize()
    except Exception as exc:
        print(f"ERROR: Model registry initialization failed: {exc}")
        sys.exit(1)

    client = LLMClient(registry=registry, settings=settings)
    results: list[dict[str, str]] = []

    for alias in ["fast", "mid", "deep"]:
        model_id = registry.get_model_id(alias)
        logger.info("Testing alias '%s' (%s)...", alias, model_id)

        # 1. Hello probe
        hello_ok = False
        reasoning_detected = "none"
        try:
            resp = client.complete(
                alias=alias,
                messages=[{"role": "user", "content": "Respond with the word PONG."}],
                max_tokens=100,
            )
            msg = resp.get("choices", [{}])[0].get("message", {})
            content_str = (msg.get("content") or msg.get("reasoning_content") or "").lower()
            if "pong" in content_str:
                hello_ok = True
            if "reasoning_content" in msg or "<think>" in (msg.get("content") or ""):
                reasoning_detected = "detected"
        except Exception as exc:
            logger.warning("Hello probe failed for %s: %s", alias, exc)

        # 2. JSON schema probe
        json_ok = False
        try:
            entity = complete_structured(
                client=client,
                alias=alias,
                messages=[{
                    "role": "user",
                    "content": "Sample entity: Reliance Industries (RELIANCE), revenue 200000.0.",
                }],
                schema_model=SimpleFinancialEntity,
                max_tokens=200,
            )
            if entity.symbol == "RELIANCE":
                json_ok = True
        except Exception as exc:
            logger.warning("JSON schema probe failed for %s: %s", alias, exc)

        # 3. Tool call probe
        tool_ok = False
        tools = [{
            "type": "function",
            "function": {
                "name": "dummy_stock_lookup",
                "description": "Look up stock symbol metadata",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            },
        }]
        handlers = {"dummy_stock_lookup": dummy_stock_lookup}

        try:
            final_resp, hist = execute_tool_loop(
                client=client,
                alias=alias,
                messages=[{"role": "user", "content": "Look up symbol TCS using the tool."}],
                tools=tools,
                tool_handlers=handlers,
                step_cap=3,
                max_tokens=200,
            )
            # Checked if tool was executed in history
            tool_called = any(m.get("role") == "tool" for m in hist)
            if tool_called:
                tool_ok = True
        except Exception as exc:
            logger.warning("Tool call probe failed for %s: %s", alias, exc)

        # Classify status
        if hello_ok and json_ok and tool_ok:
            overall = "works"
        elif hello_ok and (json_ok or tool_ok):
            overall = "partly works"
        else:
            overall = "fails"

        results.append({
            "alias": alias,
            "model_id": model_id,
            "status": overall,
            "json_schema": "pass" if json_ok else "fail",
            "tool_call": "pass" if tool_ok else "fail",
            "reasoning": reasoning_detected,
        })

    # Print summary table
    print("\n" + "=" * 80)
    hdr = f"{'Alias':<8} | {'Model ID':<35} | {'Status':<12} | {'JSON':<6} | {'Tools':<6}"
    print(hdr)
    print("-" * 80)
    for r in results:
        row = (
            f"{r['alias']:<8} | {r['model_id']:<35} | {r['status']:<12} | "
            f"{r['json_schema']:<6} | {r['tool_call']:<6}"
        )
        print(row)
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_spike()
