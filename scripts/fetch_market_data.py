"""Fetch price series for candidate universe via Yahoo Finance chart API into data/yfinance/."""

import json
import logging
import time
from pathlib import Path

import httpx
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_market_data")

DATA_DIR = Path("data") / "yfinance"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = Path("config") / "universe.yaml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def load_universe_symbols() -> list[str]:
    """Extract candidate symbols from config/universe.yaml and append .NS suffix."""
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    symbols: list[str] = ["^NSEI"]
    sectors = data.get("sectors", {})
    for _, sym_list in sectors.items():
        for s in sym_list:
            clean_s = s.strip()
            if not clean_s.endswith(".NS") and not clean_s.startswith("^"):
                symbols.append(f"{clean_s}.NS")
            else:
                symbols.append(clean_s)
    return symbols


def fetch_ticker(client: httpx.Client, symbol: str, range_param: str = "2y") -> bool:
    """Fetch ticker data once into data/yfinance/ if not already present."""
    file_name = f"{symbol.replace('^', '')}.json"
    target_file = DATA_DIR / file_name

    if target_file.exists() and target_file.stat().st_size > 500:
        logger.info("Using cached local copy for %s", symbol)
        return True

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?interval=1d&range={range_param}&includeAdjustedClose=true"
    )

    for attempt in range(2):
        try:
            r = client.get(url)
            if r.status_code == 200:
                data = r.json()
                chart = data.get("chart", {})
                results = chart.get("result", [])
                if results and results[0].get("timestamp"):
                    target_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    logger.info("Successfully fetched and cached %s (%d points)", symbol, len(results[0]["timestamp"]))
                    return True
                else:
                    logger.warning("Empty data for %s: %s", symbol, chart.get("error"))
                    return False
            else:
                logger.warning("HTTP %s for %s", r.status_code, symbol)
        except Exception as exc:
            logger.warning("Attempt %d failed for %s: %s", attempt + 1, symbol, exc)
            time.sleep(1.0)

    return False


def run_fetch() -> tuple[int, int]:
    """Run fetch for all universe symbols, return (ok_count, fail_count)."""
    symbols = load_universe_symbols()
    logger.info("Total universe symbols to check/fetch: %d", len(symbols))

    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20.0)
    ok_count = 0
    fail_count = 0

    try:
        for idx, sym in enumerate(symbols):
            success = fetch_ticker(client, sym)
            if success:
                ok_count += 1
            else:
                fail_count += 1
            time.sleep(0.1)
    finally:
        client.close()

    logger.info("Fetch complete. OK: %d, Failed: %d", ok_count, fail_count)
    return ok_count, fail_count


if __name__ == "__main__":
    run_fetch()
