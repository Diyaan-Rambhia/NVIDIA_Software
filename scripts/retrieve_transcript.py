#!/usr/bin/env python3
"""CLI utility to discover, extract, validate, and archive NSE conference call transcripts.

Usage:
  # Via individual flags:
  python scripts/retrieve_transcript.py --company INFY --quarter Q3 --fy FY25 --domain infosys.com --out transcripts

  # Via inline JSON:
  python scripts/retrieve_transcript.py --json '{"company": "INFY", "quarter": "Q3", "fiscal_year": "FY25", "company_domain": "infosys.com", "output_dir": "./transcripts"}'

  # Via input file:
  python scripts/retrieve_transcript.py --file request.json
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.features.f2_filings.transcript_retriever import (
    TranscriptRequest,
    TranscriptRetrievalAgent,
)


def parse_arguments() -> TranscriptRequest:
    """Parse CLI flags or JSON payload into TranscriptRequest."""
    parser = argparse.ArgumentParser(
        description="Retrieve, extract, validate, and archive NSE company earnings call transcripts."
    )
    parser.add_argument("--json", type=str, help="Inline JSON string matching input schema.")
    parser.add_argument("--file", type=str, help="Path to JSON file matching input schema.")
    parser.add_argument("--company", type=str, help="Company name or NSE symbol (e.g., INFY, TCS, MARUTI).")
    parser.add_argument("--quarter", type=str, help="Reporting quarter (Q1, Q2, Q3, Q4).")
    parser.add_argument("--fy", "--fiscal-year", dest="fiscal_year", type=str, help="Fiscal year (e.g., FY25, FY26).")
    parser.add_argument("--domain", "--company-domain", dest="company_domain", type=str, default=None, help="Company official domain (e.g., infosys.com).")
    parser.add_argument("--out", "--output-dir", dest="output_dir", type=str, default="./transcripts", help="Target output directory (default: ./transcripts).")

    args = parser.parse_args()

    # 1. Handle JSON string
    if args.json:
        data = json.loads(args.json)
        return TranscriptRequest(
            company=data["company"],
            quarter=data["quarter"],
            fiscal_year=data["fiscal_year"],
            company_domain=data.get("company_domain"),
            output_dir=data.get("output_dir", "./transcripts"),
        )

    # 2. Handle JSON file
    if args.file:
        file_path = Path(args.file)
        if not file_path.is_file():
            print(f"Error: JSON file not found at {file_path}", file=sys.stderr)
            sys.exit(1)
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return TranscriptRequest(
            company=data["company"],
            quarter=data["quarter"],
            fiscal_year=data["fiscal_year"],
            company_domain=data.get("company_domain"),
            output_dir=data.get("output_dir", "./transcripts"),
        )

    # 3. Handle individual CLI flags
    if not (args.company and args.quarter and args.fiscal_year):
        print(
            "Error: Must specify either --json, --file, or all of (--company, --quarter, --fy).",
            file=sys.stderr,
        )
        parser.print_help()
        sys.exit(1)

    return TranscriptRequest(
        company=args.company,
        quarter=args.quarter,
        fiscal_year=args.fiscal_year,
        company_domain=args.company_domain,
        output_dir=args.output_dir,
    )


def main() -> None:
    request = parse_arguments()
    print("=" * 70)
    print("NSE EARNINGS CALL TRANSCRIPT RETRIEVAL AGENT")
    print("=" * 70)
    print(f"Company:      {request.company}")
    print(f"Period:       {request.quarter} {request.fiscal_year}")
    print(f"Domain:       {request.company_domain or '(auto-resolve)'}")
    print(f"Output Dir:   {request.output_dir}")
    print("-" * 70)

    agent = TranscriptRetrievalAgent()
    result = agent.retrieve(request)

    status = result.get("status")
    if status in ("success", "cached"):
        meta = result.get("metadata", {})
        print(f"[STATUS] {status.upper()}")
        print(f"Saved Path:         {result.get('path')}")
        print(f"Source Type:        {meta.get('source_type')}")
        print(f"Source URL:         {meta.get('source_url')}")
        print(f"Extraction Method:  {meta.get('extraction_method')}")
        print(f"Word Count:         {meta.get('word_count')}")
        print(f"Validation:         {meta.get('validation_status')}")
        print("=" * 70)
        sys.exit(0)
    else:
        rep = result.get("report", {})
        print("[STATUS] NOT FOUND")
        print(f"Diagnostic Report:  {result.get('path')}")
        print(f"Sources Checked:    {rep.get('official_sources_checked')}")
        print(f"Searches Run:       {len(rep.get('searches_attempted', []))}")
        print(f"Candidates Tested:  {len(rep.get('candidate_urls_evaluated', []))}")
        print(f"Rejections:         {len(rep.get('rejection_reasons', []))}")
        print("=" * 70)
        sys.exit(2)


if __name__ == "__main__":
    main()
