"""Connection verification tool testing live external services.

Verifies:
- Supabase PostgreSQL database connection ('SELECT 1;')
- Auth JWKS retrieval from Supabase
- LLM model catalog and tier resolution (fast, balanced, deep)
- Model pricing configuration
- Search API connectivity
- Market data connectivity
- NSE equity archive list retrieval

Safe: Zero secret printing. Without --spend, makes zero paid LLM calls.
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

from backend.app.config.env import load_settings
from backend.app.config.loader import load_all_config
from backend.app.db.connection import get_connection
from backend.app.llm.registry import ModelRegistry


def check_db(settings: Any) -> tuple[bool, str]:
    """Test PostgreSQL database connectivity."""
    try:
        conn = get_connection(settings)
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            row = cur.fetchone()
            if row and row[0] == 1:
                conn.close()
                return True, "SELECT 1 successful"
        conn.close()
        return False, "Unexpected result from SELECT 1"
    except Exception as exc:
        return False, f"Connection failed: {exc}"


def check_auth_jwks(settings: Any) -> tuple[bool, str]:
    """Test Supabase JWKS retrieval."""
    supabase_url = settings.get_var_value("SUPABASE_URL")
    if not supabase_url:
        return False, "SUPABASE_URL not configured"

    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    anon_key = settings.get_var_value("SUPABASE_ANON_KEY")
    headers = {"apikey": anon_key} if anon_key else {}

    try:
        req = urllib.request.Request(jwks_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                key_count = len(data.get("keys", []))
                return True, f"Retrieved JWKS with {key_count} keys"
            return False, f"HTTP {resp.status}"
    except Exception as exc:
        return False, f"JWKS fetch failed: {exc}"


def check_model_catalog(settings: Any) -> tuple[bool, str]:
    """Verify registry resolves fast, balanced, deep tiers."""
    nebius_key = settings.get_var_value("NEBIUS_API_KEY")
    if not nebius_key:
        return False, "NEBIUS_API_KEY not configured"
    try:
        registry = ModelRegistry(settings=settings)
        registry.initialize()
        tiers = ["fast", "balanced", "deep"]
        resolved = []
        for t in tiers:
            mid = registry.get_tier_model_id(t)
            resolved.append(f"{t}->{mid}")
        return True, ", ".join(resolved)
    except Exception as exc:
        return False, f"Catalog resolution failed: {exc}"


def check_model_pricing(settings: Any) -> tuple[bool, str]:
    """Verify tier pricing in ModelRegistry."""
    try:
        registry = ModelRegistry(settings=settings)
        tiers = ["fast", "balanced", "deep"]
        pricing_info = []
        for t in tiers:
            try:
                inp, outp = registry.get_pricing(t)
                pricing_info.append(f"{t}: ${inp}/${outp}")
            except Exception as e:
                pricing_info.append(f"{t}: price_not_set ({e})")
        return True, ", ".join(pricing_info)
    except Exception as exc:
        return False, f"Pricing check failed: {exc}"


def check_nse_archives() -> tuple[bool, str]:
    """Verify connection to NSE archives equity list."""
    from backend.app.features.f2_filings.lookup import fetch_nse_equity_list

    try:
        equities = fetch_nse_equity_list()
        return True, f"Loaded {len(equities)} equities from official NSE archives"
    except Exception as exc:
        return False, f"NSE archives failed: {exc}"


def check_search_api(settings: Any) -> tuple[bool, str]:
    """Check Search API connectivity."""
    search_key = settings.get_var_value("TAVILY_API_KEY")
    if not search_key:
        return False, "Search API key not configured"

    try:
        payload = json.dumps({"query": "Reserve Bank of India", "max_results": 1}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {search_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return True, "Search API responded HTTP 200"
            return False, f"HTTP {resp.status}"
    except Exception as exc:
        return False, f"Search API error: {exc}"


def check_market_data() -> tuple[bool, str]:
    """Check market data provider connectivity."""
    try:
        from backend.app.data.yfinance_client import fetch_live_ticker_history

        series = fetch_live_ticker_history("RELIANCE")
        if series:
            return True, f"Retrieved {len(series)} points for RELIANCE"
        return False, "Empty series returned"
    except Exception as exc:
        return False, f"Market data query failed: {exc}"


def check_llm_spend(settings: Any) -> tuple[bool, str]:
    """Check live LLM inference with minimal spend."""
    nebius_key = settings.get_var_value("NEBIUS_API_KEY")
    if not nebius_key:
        return False, "NEBIUS_API_KEY not configured"

    try:
        from backend.app.llm.client import LLMClient

        client = LLMClient(api_key=nebius_key)
        resp = client.complete(
            model="meta-llama/Llama-3.1-8B-Instruct",
            messages=[{"role": "user", "content": "Respond with 'ok'."}],
            max_tokens=5,
        )
        return True, f"LLM responded: {resp.content.strip()}"
    except Exception as exc:
        return False, f"Live LLM call failed: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Check external service connections.")
    parser.add_argument("--spend", action="store_true", help="Execute minimal live LLM query (incurs token spend)")
    args = parser.parse_args()

    settings = load_settings()

    checks = [
        ("Database (SELECT 1)", lambda: check_db(settings)),
        ("Auth (Supabase JWKS)", lambda: check_auth_jwks(settings)),
        ("Model Catalog Tiers", lambda: check_model_catalog(settings)),
        ("Model Pricing", lambda: check_model_pricing(settings)),
        ("NSE Archives", check_nse_archives),
        ("Search API", lambda: check_search_api(settings)),
        ("Market Data", check_market_data),
    ]

    if args.spend:
        checks.append(("LLM Live Inference (--spend)", lambda: check_llm_spend(settings)))

    print("Checking external connections (zero secret printing)...")
    failed = 0
    for name, fn in checks:
        try:
            ok, msg = fn()
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] {name}: {msg}")
            if not ok:
                failed += 1
        except Exception as exc:
            print(f"[FAIL] {name}: Unhandled exception: {exc}")
            failed += 1

    if failed > 0:
        print(f"\n{failed} check(s) failed or unconfigured.")
    else:
        print("\nAll connection checks passed.")


if __name__ == "__main__":
    main()
