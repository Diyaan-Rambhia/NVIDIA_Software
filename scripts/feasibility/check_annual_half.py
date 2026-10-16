import httpx
import json
from pathlib import Path
from bs4 import BeautifulSoup

DATA_DIR = Path("data") / "xbrl"
DATA_DIR.mkdir(parents=True, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results",
}
client = httpx.Client(headers=headers, follow_redirects=True, timeout=25.0)
client.get("https://www.nseindia.com")

targets = ["INFY", "ITC", "MARUTI", "TATASTEEL", "RELIANCE"]

# 1. Fetch Half-Yearly
r_half = client.get("https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Half%20Yearly&from_date=01-04-2024&to_date=30-09-2024")
half_data = r_half.json() if r_half.status_code == 200 else []
print("Half-yearly total items:", len(half_data))

# 2. Fetch Annual
r_ann = client.get("https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Annual&from_date=01-04-2023&to_date=31-03-2024")
ann_data = r_ann.json() if r_ann.status_code == 200 else []
print("Annual total items:", len(ann_data))

def find_entries(data_list, period_name):
    found = {}
    for d in data_list:
        sym = d.get("symbol")
        if sym in targets and sym not in found:
            xbrl = d.get("xbrl") or ""
            if xbrl.endswith(".xml") and "Ind-AS" in str(d.get("indAs", "")):
                found[sym] = d
    return found

half_found = find_entries(half_data, "Half-Yearly")
ann_found = find_entries(ann_data, "Annual")

print("Half-yearly found symbols:", list(half_found.keys()))
print("Annual found symbols:", list(ann_found.keys()))

results = {}

def check_metrics(xml_content):
    soup = BeautifulSoup(xml_content, "xml")
    # Operating cash flow
    has_ocf = bool(soup.find(lambda el: el.name and any(tag.lower() in el.name.lower() for tag in [
        "cashflowfromusedinoperatingactivities",
        "cashflowsfromusedinoperatingactivities",
        "cashflowsfromoperatingactivities",
        "operatingcashflow",
    ])))
    # Receivables
    has_rec = bool(soup.find(lambda el: el.name and any(tag.lower() in el.name.lower() for tag in [
        "tradereceivables",
        "receivables",
    ])))
    return has_ocf, has_rec

for sym in targets:
    results[sym] = {"half_yearly": {}, "annual": {}}
    
    # Check half-yearly
    if sym in half_found:
        url = half_found[sym]["xbrl"]
        r = client.get(url)
        if r.status_code == 200:
            has_ocf, has_rec = check_metrics(r.content)
            results[sym]["half_yearly"] = {"ocf": has_ocf, "receivables": has_rec, "url": url}
    
    # Check annual
    if sym in ann_found:
        url = ann_found[sym]["xbrl"]
        r = client.get(url)
        if r.status_code == 200:
            has_ocf, has_rec = check_metrics(r.content)
            results[sym]["annual"] = {"ocf": has_ocf, "receivables": has_rec, "url": url}

client.close()
print(json.dumps(results, indent=2))
