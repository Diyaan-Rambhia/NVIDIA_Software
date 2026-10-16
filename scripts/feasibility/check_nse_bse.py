"""Feasibility check for NSE/BSE direct downloads."""
from pathlib import Path
import httpx

DATA_DIR = Path("data") / "nse_bse"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def check_nse():
    results = {}
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=10.0)
    try:
        # Initial request to obtain session cookies
        r_home = client.get("https://www.nseindia.com")
        results["home_status"] = r_home.status_code
        (DATA_DIR / "nse_home.html").write_bytes(r_home.content[:1000])
        
        # Test historical/report download endpoint
        r_api = client.get(
            "https://www.nseindia.com/api/historical/cm/equity?symbol=RELIANCE",
            headers={"Referer": "https://www.nseindia.com/"}
        )
        results["api_status"] = r_api.status_code
        if r_api.status_code == 200:
            (DATA_DIR / "nse_equity.json").write_bytes(r_api.content)
            results["api_format"] = "json"
        else:
            results["api_format"] = "none"
    except Exception as exc:
        results["error"] = str(exc)
    finally:
        client.close()
    return results

def check_bse():
    results = {}
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=10.0)
    try:
        r_home = client.get("https://www.bseindia.com")
        results["home_status"] = r_home.status_code
        (DATA_DIR / "bse_home.html").write_bytes(r_home.content[:1000])

        r_api = client.get(
            "https://api.bseindia.com/BseIndiaAPI/api/StockTrading/w?flag=gsc&scripcode=500325",
            headers={"Referer": "https://www.bseindia.com/"}
        )
        results["api_status"] = r_api.status_code
        if r_api.status_code == 200:
            (DATA_DIR / "bse_quote.json").write_bytes(r_api.content)
            results["api_format"] = "json"
        else:
            results["api_format"] = "none"
    except Exception as exc:
        results["error"] = str(exc)
    finally:
        client.close()
    return results

if __name__ == "__main__":
    print("Testing NSE...")
    nse_res = check_nse()
    print("NSE Results:", nse_res)
    print("Testing BSE...")
    bse_res = check_bse()
    print("BSE Results:", bse_res)
