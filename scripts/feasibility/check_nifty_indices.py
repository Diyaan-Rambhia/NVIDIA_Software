"""Feasibility check for NSE Indices (niftyindices.com)."""
from pathlib import Path
import httpx

DATA_DIR = Path("data") / "nifty_indices"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

def check_nifty_indices():
    results = {}
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15.0)
    try:
        r_home = client.get("https://www.niftyindices.com")
        results["home_status"] = r_home.status_code
        (DATA_DIR / "home.html").write_bytes(r_home.content[:1000])

        # Test index data download or historical report endpoint
        # Nifty Indices historical data endpoint:
        # https://www.niftyindices.com/reports/historical-data
        r_report = client.get("https://www.niftyindices.com/reports/historical-data")
        results["report_page_status"] = r_report.status_code

        # Test API endpoint
        # https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatablecsv
        r_api = client.post(
            "https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatablecsv",
            json={"name": "NIFTY 50"},
            headers={"Content-Type": "application/json; charset=UTF-8", "Referer": "https://www.niftyindices.com/"}
        )
        results["api_status"] = r_api.status_code
        if r_api.status_code == 200:
            (DATA_DIR / "api_res.json").write_bytes(r_api.content[:2000])
            results["api_format"] = "json"
        else:
            results["api_format"] = "none"
    except Exception as exc:
        results["error"] = str(exc)
    finally:
        client.close()
    return results

if __name__ == "__main__":
    res = check_nifty_indices()
    print("Nifty Indices Results:", res)
