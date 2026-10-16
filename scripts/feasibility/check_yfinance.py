"""Feasibility check for Yahoo Finance (yfinance) Indian tickers."""
from pathlib import Path
import httpx
import json

DATA_DIR = Path("data") / "yfinance"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

def check_ticker(symbol: str, interval: str = "1d", range_param: str = "1y"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range_param}&includeAdjustedClose=true"
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15.0)
    try:
        r = client.get(url)
        status = r.status_code
        if status == 200:
            data = r.json()
            (DATA_DIR / f"{symbol.replace('^', '')}.json").write_text(json.dumps(data, indent=2))
            chart = data.get("chart", {})
            result = chart.get("result", [{}])[0]
            meta = result.get("meta", {})
            indicators = result.get("indicators", {})
            quote = indicators.get("quote", [{}])[0]
            adjclose = indicators.get("adjclose", [{}])[0]
            timestamps = result.get("timestamp", [])
            
            return {
                "reachable": True,
                "status_code": status,
                "currency": meta.get("currency"),
                "exchange": meta.get("exchangeName"),
                "data_points": len(timestamps),
                "has_open": bool(quote.get("open")),
                "has_high": bool(quote.get("high")),
                "has_low": bool(quote.get("low")),
                "has_close": bool(quote.get("close")),
                "has_volume": bool(quote.get("volume")),
                "has_adjclose": bool(adjclose.get("adjclose")),
            }
        else:
            return {"reachable": False, "status_code": status, "error": r.text[:200]}
    except Exception as exc:
        return {"reachable": False, "status_code": 0, "error": str(exc)}
    finally:
        client.close()

if __name__ == "__main__":
    symbols = ["RELIANCE.NS", "RELIANCE.BO", "^NSEI", "^BSESN", "^CRSLDX", "INDIAVIX.NS"]
    for sym in symbols:
        res = check_ticker(sym)
        print(f"Ticker {sym}:", res)
