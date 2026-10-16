"""Download and parse real Ind AS XBRL file for one non-financial company."""
from pathlib import Path
import json
import httpx
from bs4 import BeautifulSoup

DATA_DIR = Path("data") / "xbrl"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.nseindia.com/",
}

def verify_xbrl():
    results_path = DATA_DIR / "nse_quarterly_results.json"
    data = json.loads(results_path.read_text(encoding="utf-8"))
    
    # Target companies: e.g. INFY, TCS, RELIANCE, VSTTILLERS, TATAMOTORS, etc.
    target_entry = None
    for entry in data:
        xbrl_url = entry.get("xbrl") or ""
        if xbrl_url.endswith(".xml") and "Ind-AS" in str(entry.get("indAs", "")):
            target_entry = entry
            break

    if not target_entry:
        raise ValueError("No valid Ind AS XBRL entry found")

    symbol = target_entry.get("symbol")
    company_name = target_entry.get("companyName")
    period = target_entry.get("period")
    xbrl_url = target_entry.get("xbrl")
    
    print(f"Selected Company: {company_name} ({symbol})")
    print(f"Period: {period}")
    print(f"XBRL URL: {xbrl_url}")

    # Download XBRL file
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20.0)
    r = client.get(xbrl_url)
    print(f"XBRL download HTTP status: {r.status_code}, length: {len(r.content)}")
    if r.status_code != 200:
        raise RuntimeError(f"Failed to download XBRL from {xbrl_url}: {r.status_code}")

    xml_path = DATA_DIR / f"{symbol}_result.xml"
    xml_path.write_bytes(r.content)

    # Parse XML
    soup = BeautifulSoup(r.content, "xml")
    
    # Extract financial tags (Ind AS taxonomy)
    extracted_metrics = {}
    tags_to_find = [
        "RevenueFromOperations",
        "TotalRevenue",
        "TotalIncome",
        "ProfitBeforeTax",
        "ProfitLossForPeriod",
        "ComprehensiveIncomeForThePeriod",
        "BasicEarningsLossPerShareFromContinuingOperations",
        "DilutedEarningsLossPerShareFromContinuingOperations",
        "PaidUpEquityShareCapital",
    ]

    for tag in tags_to_find:
        # Search by tag name regardless of namespace prefix
        elem = soup.find(lambda el: el.name and el.name.endswith(tag))
        if elem:
            extracted_metrics[tag] = {
                "value": elem.text.strip(),
                "contextRef": elem.get("contextRef"),
                "unitRef": elem.get("unitRef"),
                "decimals": elem.get("decimals"),
            }

    print("\n--- Extracted Ind AS Metrics ---")
    for k, v in extracted_metrics.items():
        print(f"  {k}: {v['value']} (unit: {v['unitRef']}, context: {v['contextRef']})")

    # Save summary
    summary = {
        "company": company_name,
        "symbol": symbol,
        "period": period,
        "xbrl_url": xbrl_url,
        "metrics": extracted_metrics,
    }
    (DATA_DIR / f"{symbol}_parsed_metrics.json").write_text(json.dumps(summary, indent=2))
    return summary

if __name__ == "__main__":
    verify_xbrl()
