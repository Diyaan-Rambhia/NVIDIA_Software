"""Download and parse 5 non-financial companies across different sectors."""
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

COMPANIES = [
    {"symbol": "INFY", "sector": "it_services", "url": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117294_1348219_16012025074210.xml"},
    {"symbol": "ITC", "sector": "fmcg", "url": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_118941_1373614_06022025072019.xml"},
    {"symbol": "MARUTI", "sector": "autos", "url": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_118041_1364863_29012025055034.xml"},
    {"symbol": "TATASTEEL", "sector": "metals", "url": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117788_1362364_27012025071559.xml"},
    {"symbol": "RELIANCE", "sector": "energy", "url": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117298_1348254_16012025082021.xml"},
]

def run():
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25.0)
    results = {}
    for comp in COMPANIES:
        sym = comp["symbol"]
        sec = comp["sector"]
        url = comp["url"]
        xml_file = DATA_DIR / f"{sym}.xml"
        try:
            if not xml_file.exists():
                r = client.get(url)
                if r.status_code != 200:
                    results[sym] = {"parsed": "no", "error": f"HTTP {r.status_code}", "fields": []}
                    continue
                xml_file.write_bytes(r.content)
            
            content = xml_file.read_bytes()
            soup = BeautifulSoup(content, "xml")
            
            # Check for revenue
            has_rev = bool(soup.find(lambda el: el.name and any(tag in el.name for tag in ["RevenueFromOperations", "TotalRevenue"])))
            # Check for profit
            has_profit = bool(soup.find(lambda el: el.name and any(tag in el.name for tag in ["ProfitLossForPeriod", "ProfitBeforeTax"])))
            # Check for operating cash flow
            has_ocf = bool(soup.find(lambda el: el.name and any(tag in el.name for tag in ["CashFlowsFromUsedInOperatingActivities", "CashFlowFromUsedInOperatingActivities", "OperatingCashFlow"])))
            # Check for receivables
            has_rec = bool(soup.find(lambda el: el.name and any(tag in el.name for tag in ["TradeReceivables", "Receivables"])))
            
            fields_found = []
            if has_rev:
                fields_found.append("revenue")
            if has_profit:
                fields_found.append("profit")
            if has_ocf:
                fields_found.append("operating cash flow")
            if has_rec:
                fields_found.append("receivables")
                
            results[sym] = {
                "sector": sec,
                "parsed": "yes",
                "fields": fields_found,
            }
        except Exception as exc:
            results[sym] = {"sector": sec, "parsed": "no", "error": str(exc), "fields": []}
            
    client.close()
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run()
