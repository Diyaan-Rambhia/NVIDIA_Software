"""Search verification script testing Tavily news search integration.

To be executed directly by the operator. Reads configuration and secrets from .env.
Never prints or logs API keys.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

import yaml

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()

    if not api_key:
        print("Tavily search verification: not run: no key")
        return 0

    print("Verifying Tavily live search at request time...")

    params_file = Path(__file__).resolve().parent.parent / "config" / "parameters.yaml"
    max_results = 3
    if params_file.is_file():
        try:
            pdata = yaml.safe_load(params_file.read_text(encoding="utf-8"))
            max_results = int(pdata.get("parameters", {}).get("f1_news_searches_per_run", {}).get("default", 3))
        except Exception:
            pass

    test_query = "Reserve Bank of India monetary policy liquidity Indian equities"
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": test_query,
        "search_depth": "basic",
        "max_results": max_results,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            print(f"PASS: Tavily returned {len(results)} search results for test query.")
            print("\nFormatted Search Evidence Items:")
            print("-" * 80)
            for idx, r in enumerate(results, start=1):
                evidence_id = f"E{idx}"
                title = r.get("title", "No Title")
                src_url = r.get("url", "No URL")
                snippet = (r.get("content") or "")[:120].strip()
                print(f"[{evidence_id}] {title}")
                print(f"     Source: {src_url}")
                print(f"     Snippet: {snippet}...")
                print("-" * 80)
            return 0
    except HTTPError as exc:
        print(f"FAIL: Tavily API returned HTTP {exc.code}: {exc.read().decode('utf-8')}")
        return 1
    except Exception as exc:
        print(f"FAIL: Tavily search connection error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
