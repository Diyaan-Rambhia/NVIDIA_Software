"""Feasibility check for NSDL and NSE institutional flow data."""
from pathlib import Path
import httpx

DATA_DIR = Path("data") / "flows"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

def check_nsdl_flows():
    results = {}
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15.0, verify=False)
    try:
        r_home = client.get("https://www.fpi.nsdl.co.in")
        results["nsdl_home_status"] = r_home.status_code
        (DATA_DIR / "nsdl_home.html").write_bytes(r_home.content[:2000])

        # NSDL reports daily sector/trend reports under public portal
        r_rep = client.get("https://www.fpi.nsdl.co.in/php/Reports.php")
        results["nsdl_reports_status"] = r_rep.status_code
        if r_rep.status_code == 200:
            (DATA_DIR / "nsdl_reports.html").write_bytes(r_rep.content[:2000])
    except Exception as exc:
        results["nsdl_error"] = str(exc)
    finally:
        client.close()
    return results

def check_nse_flows():
    results = {}
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15.0)
    try:
        # NSE FII/DII endpoint
        r_fiidii = client.get(
            "https://www.nseindia.com/api/fiidiiTradeReact",
            headers={"Referer": "https://www.nseindia.com/"}
        )
        results["nse_fiidii_status"] = r_fiidii.status_code
        if r_fiidii.status_code == 200:
            (DATA_DIR / "nse_fiidii.json").write_bytes(r_fiidii.content)
            results["format"] = "json"
        else:
            results["format"] = "none"
    except Exception as exc:
        results["nse_error"] = str(exc)
    finally:
        client.close()
    return results

if __name__ == "__main__":
    print("Checking NSDL flows...")
    print("NSDL:", check_nsdl_flows())
    print("Checking NSE flows...")
    print("NSE:", check_nse_flows())
