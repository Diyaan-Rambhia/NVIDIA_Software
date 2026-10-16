"""Feasibility check for RBI and FBIL (rates, 91-day T-bill yields)."""
from pathlib import Path
import httpx
from bs4 import BeautifulSoup

DATA_DIR = Path("data") / "rbi_fbil"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def check_rbi():
    results = {}
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20.0, verify=False)
    try:
        # Check RBI main site rates page / press release
        r_main = client.get("https://www.rbi.org.in")
        results["rbi_main_status"] = r_main.status_code
        (DATA_DIR / "rbi_main.html").write_bytes(r_main.content[:2000])

        # DBIE portal
        r_dbie = client.get("https://dbie.rbi.org.in")
        results["dbie_status"] = r_dbie.status_code
        (DATA_DIR / "dbie.html").write_bytes(r_dbie.content[:2000])
    except Exception as exc:
        results["rbi_error"] = str(exc)
    finally:
        client.close()
    return results

def check_fbil():
    results = {}
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20.0, verify=False)
    try:
        r_home = client.get("https://www.fbil.org.in")
        results["fbil_home_status"] = r_home.status_code
        (DATA_DIR / "fbil_home.html").write_bytes(r_home.content[:2000])

        # FBIL Treasury Bill benchmark page
        # FBIL publishes Money Market / Treasury Bill benchmarks under sub-URLs or POST endpoints
        soup = BeautifulSoup(r_home.text, "html.parser")
        results["title"] = soup.title.string.strip() if soup.title else None
        
        # Check for T-Bill / MIBOR keywords
        text_lower = r_home.text.lower()
        results["mentions_tbill"] = "treasury bill" in text_lower or "t-bill" in text_lower
        results["mentions_mibor"] = "mibor" in text_lower
    except Exception as exc:
        results["fbil_error"] = str(exc)
    finally:
        client.close()
    return results

if __name__ == "__main__":
    print("Checking RBI...")
    print("RBI:", check_rbi())
    print("Checking FBIL...")
    print("FBIL:", check_fbil())
