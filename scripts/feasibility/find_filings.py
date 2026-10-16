import httpx
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results",
}
client = httpx.Client(headers=headers, follow_redirects=True, timeout=20.0)
client.get("https://www.nseindia.com")

# Test how to query different date ranges or parameters for corporates-financial-results
# Let's test from_date and to_date with dd-mm-yyyy or DD-MM-YYYY
for query in [
    "index=equities&from_date=01-01-2024&to_date=31-12-2024",
    "index=equities&from_date=01-04-2024&to_date=30-09-2024",
    "index=equities&period=Half%20Yearly&from_date=01-04-2024&to_date=30-09-2024",
    "index=equities&period=Annual&from_date=01-04-2023&to_date=31-03-2024",
    "index=equities&symbol=INFY&period=Quarterly",
]:
    url = f"https://www.nseindia.com/api/corporates-financial-results?{query}"
    r = client.get(url)
    try:
        data = r.json()
        print(query, "-> status:", r.status_code, "count:", len(data) if isinstance(data, list) else data)
    except Exception as exc:
        print(query, "-> status:", r.status_code, "error:", exc)
