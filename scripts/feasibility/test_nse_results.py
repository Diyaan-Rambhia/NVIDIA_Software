"""Test NSE financial results endpoint with initialized session."""
from pathlib import Path
import httpx
import json

DATA_DIR = Path("data") / "xbrl"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

def test_nse_results():
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20.0)
    try:
        # 1. Hit home page to get Akamai cookies
        r_home = client.get("https://www.nseindia.com")
        print("Home status:", r_home.status_code)
        
        # 2. Hit financial results page
        r_page = client.get("https://www.nseindia.com/companies-listing/corporate-filings-financial-results")
        print("Results page status:", r_page.status_code)
        
        # 3. Hit API endpoint
        api_headers = dict(HEADERS)
        api_headers["Accept"] = "application/json, text/plain, */*"
        api_headers["Referer"] = "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"
        
        r_api = client.get(
            "https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly",
            headers=api_headers
        )
        print("API status:", r_api.status_code)
        print("API content length:", len(r_api.content))
        if r_api.status_code == 200:
            (DATA_DIR / "nse_quarterly_results.json").write_bytes(r_api.content)
            data = r_api.json()
            print("Items returned:", len(data))
            if data:
                print("First item sample:", list(data[0].keys()))
                # Find an XBRL link or symbol
                for item in data[:10]:
                    print("Symbol:", item.get("symbol"), "xbrl:", item.get("xbrl") or item.get("xbrlAttachment"))
    except Exception as exc:
        print("Error:", exc)
    finally:
        client.close()

if __name__ == "__main__":
    test_nse_results()
