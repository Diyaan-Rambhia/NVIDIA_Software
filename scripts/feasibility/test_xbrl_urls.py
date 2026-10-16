"""Test various BSE and NSE XBRL endpoints."""
from pathlib import Path
import httpx

DATA_DIR = Path("data") / "xbrl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def test_urls():
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15.0)
    urls = [
        "https://www.bseindia.com/corporates/xbrl.html",
        "https://www.bseindia.com/corporates/FinResults.aspx",
        "https://nsearchives.nseindia.com/corporate/xbrl/",
        "https://www.nseindia.com/api/corporates-financial-results?index=equities",
    ]
    for url in urls:
        try:
            r = client.get(url)
            print(f"{url} -> status {r.status_code}, len: {len(r.content)}")
            if r.status_code == 200:
                name = url.split("/")[-1].replace("?", "_").replace("&", "_")
                if not name:
                    name = "root"
                (DATA_DIR / f"{name[:30]}").write_bytes(r.content[:2000])
        except Exception as exc:
            print(f"{url} -> ERROR: {exc}")
    client.close()

if __name__ == "__main__":
    test_urls()
