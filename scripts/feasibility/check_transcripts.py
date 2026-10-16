"""Feasibility check for company transcripts, investor presentations, and announcements."""
from pathlib import Path
import httpx
import json

DATA_DIR = Path("data") / "transcripts"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.nseindia.com/",
}

def check_announcements():
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20.0)
    results = {}
    try:
        # Initialize cookie on announcements page
        r_page = client.get("https://www.nseindia.com/companies-listing/corporate-filings-announcements")
        results["page_status"] = r_page.status_code
        
        # Query corporate announcements API
        api_headers = dict(HEADERS)
        api_headers["Accept"] = "application/json, text/plain, */*"
        api_headers["Referer"] = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
        
        r_api = client.get(
            "https://www.nseindia.com/api/corporate-announcements?index=equities",
            headers=api_headers
        )
        results["api_status"] = r_api.status_code
        if r_api.status_code == 200:
            data = r_api.json()
            (DATA_DIR / "announcements.json").write_bytes(r_api.content)
            results["total_announcements"] = len(data)
            
            # Look for transcripts / investor presentations / earnings calls
            transcripts = []
            for item in data:
                desc = (item.get("desc") or "").lower()
                att = item.get("attmntFile") or item.get("attachment") or ""
                if any(w in desc for w in ["transcript", "concall", "earning", "investor presentation", "audio"]):
                    transcripts.append({
                        "symbol": item.get("symbol"),
                        "company": item.get("companyName"),
                        "desc": item.get("desc"),
                        "attachment": att,
                    })
            results["sample_transcript_matches"] = len(transcripts)
            if transcripts:
                results["first_match"] = transcripts[0]
                # Test downloading attachment if URL is valid
                att_url = transcripts[0]["attachment"]
                if att_url and att_url.startswith("http"):
                    r_att = client.get(att_url)
                    results["attachment_download_status"] = r_att.status_code
                    results["attachment_size"] = len(r_att.content)
    except Exception as exc:
        results["error"] = str(exc)
    finally:
        client.close()
    return results

if __name__ == "__main__":
    res = check_announcements()
    print("Announcements & Transcripts Results:", res)
