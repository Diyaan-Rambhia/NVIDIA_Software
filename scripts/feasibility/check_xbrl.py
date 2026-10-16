"""Feasibility check for NSE/BSE Ind AS financial results XBRL."""
from pathlib import Path
import httpx
import json
from bs4 import BeautifulSoup

DATA_DIR = Path("data") / "xbrl"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

def check_bse_xbrl():
    results = {}
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15.0)
    try:
        # Check BSE financial results API for Reliance scripcode 500325 or Infosys 500209
        url = "https://api.bseindia.com/BseIndiaAPI/api/Fin_Results/w?scripcode=500325"
        r = client.get(url, headers={"Referer": "https://www.bseindia.com/"})
        results["bse_fin_status"] = r.status_code
        if r.status_code == 200:
            (DATA_DIR / "bse_fin.json").write_bytes(r.content)
            results["bse_fin_format"] = "json"

        # Check BSE Corporate Announcements / XBRL links
        xbrl_url = "https://api.bseindia.com/BseIndiaAPI/api/XBRL_Data_New/w?scripcode=500325"
        r_xbrl = client.get(xbrl_url, headers={"Referer": "https://www.bseindia.com/"})
        results["bse_xbrl_status"] = r_xbrl.status_code
        if r_xbrl.status_code == 200:
            (DATA_DIR / "bse_xbrl.json").write_bytes(r_xbrl.content)
    except Exception as exc:
        results["bse_error"] = str(exc)
    finally:
        client.close()
    return results

if __name__ == "__main__":
    print("Checking BSE XBRL...")
    res = check_bse_xbrl()
    print("Results:", res)
