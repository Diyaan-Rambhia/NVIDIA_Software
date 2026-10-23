"""Model verification script testing Token Factory model tiers against real endpoints.

To be executed directly by the operator. Reads configuration and secrets from .env.
Never prints or logs API keys.
"""

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

import yaml

# Try loading python-dotenv if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    # Manual .env reader fallback
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from backend.app.llm.registry import load_models_config, resolve_tier_model


def make_request(url: str, api_key: str, payload: dict | None = None, method: str = "GET") -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    base_url = os.environ.get("NEBIUS_BASE_URL", "").rstrip("/")
    api_key = os.environ.get("NEBIUS_API_KEY", "")
    test_budget_str = os.environ.get("TEST_DAILY_LLM_BUDGET_USD", "1.00")
    test_budget = float(test_budget_str)

    if not base_url or not api_key:
        print("FAIL: NEBIUS_BASE_URL or NEBIUS_API_KEY is missing from environment / .env")
        print("Model verification skipped: not run: no key")
        return 1

    print("Verifying model tiers from live catalog...")
    models_cfg = load_models_config()

    # 1. Fetch live model IDs
    try:
        models_data = make_request(f"{base_url}/models", api_key)
        live_model_ids = [m["id"] for m in models_data.get("data", []) if "id" in m]
        print(f"Retrieved {len(live_model_ids)} live models from Token Factory.")
    except Exception as exc:
        print(f"FAIL: Unable to fetch live model catalog: {exc}")
        return 1

    tiers = ["fast", "balanced", "deep", "vision"]
    total_spent_usd = 0.0

    print("\nTier Resolution Summary:")
    print("-" * 75)
    print(f"{'Tier':<12} | {'Status':<12} | {'Resolved Model ID / Reason':<45}")
    print("-" * 75)

    test_tool = [
        {
            "type": "function",
            "function": {
                "name": "lookup_stock",
                "description": "Lookup stock price info",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Ticker symbol"}
                    },
                    "required": ["symbol"],
                },
            },
        }
    ]

    json_schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "sentiment_response",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "score": {"type": "number"},
                },
                "required": ["summary", "score"],
                "additionalProperties": False,
            },
        },
    }

    tier_results = []

    for tier in tiers:
        resolved_id, reason = resolve_tier_model(tier, live_model_ids, models_cfg)
        if not resolved_id:
            status_label = "disabled" if tier == "vision" else "unavailable"
            print(f"{tier:<12} | {status_label:<12} | {reason or 'no match':<45}")
            tier_results.append({
                "tier": tier,
                "status": status_label,
                "model_id": "N/A",
                "tool_calling": "N/A",
                "json_schema": "N/A",
                "tokens": "0 in / 0 out",
                "cost_usd": 0.0,
                "reason": reason,
            })
            continue

        print(f"{tier:<12} | {'resolved':<12} | {resolved_id:<45}")

        # Check hard budget cap before testing
        if total_spent_usd >= test_budget:
            print(f"WARNING: Test budget limit reached (${test_budget:.4f}). Stopping further tests.")
            tier_results.append({
                "tier": tier,
                "status": "budget_limit",
                "model_id": resolved_id,
                "tool_calling": "skipped",
                "json_schema": "skipped",
                "tokens": "0",
                "cost_usd": 0.0,
            })
            continue

        # Test tool calling with tiny prompt
        tool_status = "fails"
        in_tokens = 0
        out_tokens = 0
        try:
            tool_payload = {
                "model": resolved_id,
                "messages": [
                    {"role": "user", "content": "Check stock price for RELIANCE using the tool."}
                ],
                "tools": test_tool,
                "tool_choice": "auto",
                "max_tokens": 80,
                "temperature": 0.0,
            }
            res = make_request(f"{base_url}/chat/completions", api_key, tool_payload, method="POST")
            usage = res.get("usage", {})
            in_tokens += usage.get("prompt_tokens", 0)
            out_tokens += usage.get("completion_tokens", 0)

            choice = res.get("choices", [{}])[0]
            msg = choice.get("message", {})
            calls = msg.get("tool_calls", [])
            if calls and any(c.get("function", {}).get("name") == "lookup_stock" for c in calls):
                tool_status = "works"
            elif calls:
                tool_status = "partly"
            else:
                tool_status = "fails"
        except Exception as exc:
            tool_status = f"fails ({type(exc).__name__})"

        # Test JSON schema structured output
        schema_status = "fails"
        try:
            schema_payload = {
                "model": resolved_id,
                "messages": [
                    {"role": "user", "content": "Return summary 'ok' and score 1.0 in schema format."}
                ],
                "response_format": json_schema,
                "max_tokens": 60,
                "temperature": 0.0,
            }
            res2 = make_request(f"{base_url}/chat/completions", api_key, schema_payload, method="POST")
            usage2 = res2.get("usage", {})
            in_tokens += usage2.get("prompt_tokens", 0)
            out_tokens += usage2.get("completion_tokens", 0)

            choice2 = res2.get("choices", [{}])[0]
            content = choice2.get("message", {}).get("content", "")
            parsed = json.loads(content)
            if "summary" in parsed and "score" in parsed:
                schema_status = "works"
            else:
                schema_status = "partly"
        except Exception as exc:
            schema_status = f"fails ({type(exc).__name__})"

        # Provisional cost estimation
        cost_est = (in_tokens * 0.20 + out_tokens * 0.80) / 1_000_000.0
        total_spent_usd += cost_est

        tier_results.append({
            "tier": tier,
            "status": "verified",
            "model_id": resolved_id,
            "tool_calling": tool_status,
            "json_schema": schema_status,
            "tokens": f"{in_tokens} in / {out_tokens} out",
            "cost_usd": cost_est,
        })

    print("\nDetailed Tier Capability Report:")
    print("-" * 85)
    print(f"{'Tier':<10} | {'Tool Calling':<14} | {'JSON Schema':<14} | {'Tokens':<18} | {'Est Cost (USD)':<12}")
    print("-" * 85)
    for r in tier_results:
        print(f"{r['tier']:<10} | {str(r.get('tool_calling', 'N/A')):<14} | {str(r.get('json_schema', 'N/A')):<14} | {str(r.get('tokens', 'N/A')):<18} | ${r.get('cost_usd', 0.0):.6f}")
    print("-" * 85)
    print(f"Total spent against test budget: ${total_spent_usd:.6f} / ${test_budget:.2f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
