"""Feasibility check for FRED API and series."""
from pathlib import Path
import httpx
from backend.app.config.env import load_settings

DATA_DIR = Path("data") / "fred"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def check_fred():
    settings = load_settings()
    fred_key = getattr(settings, "fred_api_key", None)
    
    results = {
        "key_present": bool(fred_key),
        "needs_key": fred_key is None or len(str(fred_key).strip()) == 0,
    }

    # Public web check of FRED series without key (FRED series webpage)
    # Testing India 3-month Treasury Bill / Interest rate series: INTGSBINM193N
    client = httpx.Client(follow_redirects=True, timeout=15.0)
    try:
        r_series = client.get("https://fred.stlouisfed.org/series/INTGSBINM193N")
        results["series_page_status"] = r_series.status_code
        if r_series.status_code == 200:
            (DATA_DIR / "INTGSBINM193N.html").write_bytes(r_series.content[:2000])
            results["series_available_on_fred"] = True
            results["series_title"] = "Interest Rates, Government Securities, Treasury Bills for India"
        else:
            results["series_available_on_fred"] = False
    except Exception as exc:
        results["web_error"] = str(exc)

    # If key is available, test API endpoint
    if fred_key:
        try:
            r_api = client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={"series_id": "INTGSBINM193N", "api_key": fred_key, "file_type": "json"}
            )
            results["api_status"] = r_api.status_code
        except Exception as exc:
            results["api_error"] = str(exc)
    else:
        results["api_status"] = "needs key"

    client.close()
    return results

if __name__ == "__main__":
    res = check_fred()
    print("FRED Results:", res)
