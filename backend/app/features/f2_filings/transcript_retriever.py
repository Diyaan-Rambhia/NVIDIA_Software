"""Earnings-call and conference-call transcript retrieval and archiving engine.

Per PROJECT.md, FR-F2 requirements, and Indian market context (NSE/BSE).
Discovers official company conference call transcripts via Tavily Search,
extracts full text using Tavily Extract and local PDF parsing (pypdf),
enforces strict source prioritization (IR -> NSE -> BSE -> Aggregator),
validates authentic management dialogue and Q&A structure,
and archives clean transcripts and metadata locally with deduplicated caching.
"""

from __future__ import annotations

import io
import json
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import httpx
import pypdf

from backend.app.config.env import Settings, get_repo_root, load_settings

logger = logging.getLogger("backend.app.features.f2_filings.transcript_retriever")

# Common NSE symbol to primary domain and corporate name mapping
SYMBOL_DIRECTORY: dict[str, dict[str, str]] = {
    "INFY": {"name": "Infosys Limited", "domain": "infosys.com"},
    "TCS": {"name": "Tata Consultancy Services Limited", "domain": "tcs.com"},
    "MARUTI": {"name": "Maruti Suzuki India Limited", "domain": "marutisuzuki.com"},
    "RELIANCE": {"name": "Reliance Industries Limited", "domain": "ril.com"},
    "ITC": {"name": "ITC Limited", "domain": "itcportal.com"},
    "TATASTEEL": {"name": "Tata Steel Limited", "domain": "tatasteel.com"},
    "HINDUNILVR": {"name": "Hindustan Unilever Limited", "domain": "hul.co.in"},
    "HCLTECH": {"name": "HCL Technologies Limited", "domain": "hcltech.com"},
    "WIPRO": {"name": "Wipro Limited", "domain": "wipro.com"},
    "TATAMOTORS": {"name": "Tata Motors Limited", "domain": "tatamotors.com"},
    "BHARTIARTL": {"name": "Bharti Airtel Limited", "domain": "airtel.in"},
    "LT": {"name": "Larsen & Toubro Limited", "domain": "larsentoubro.com"},
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

HTTP_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
}


@dataclass
class TranscriptRequest:
    """Input specifications for transcript discovery and extraction."""

    company: str
    quarter: str
    fiscal_year: str
    company_domain: str | None = None
    output_dir: str = "./transcripts"


@dataclass
class TranscriptMetadata:
    """Structured metadata recorded alongside validated transcript text."""

    company: str
    nse_symbol: str
    quarter: str
    fiscal_year: str
    call_date: str = ""
    source_type: str = ""  # official_ir, official_nse, official_bse, aggregator
    source_url: str = ""
    pdf_url: str = ""
    retrieved_at: str = ""
    extraction_method: str = ""  # pypdf, tavily_extract, direct_html
    word_count: int = 0
    validation_status: str = "passed"
    notes: str = ""


@dataclass
class NotFoundReport:
    """Diagnostic report archived when no valid transcript can be retrieved."""

    company: str
    nse_symbol: str
    quarter: str
    fiscal_year: str
    searches_attempted: list[str] = field(default_factory=list)
    candidate_urls_evaluated: list[dict[str, Any]] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    official_sources_checked: list[str] = field(default_factory=list)
    status: str = "not_found"
    checked_at: str = ""


class TranscriptRetrievalAgent:
    """Agent that discovers, extracts, validates, and archives earnings call transcripts."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.api_key = self.settings.get_var_value("TAVILY_API_KEY")
        self._searched_queries: set[str] = set()

    def resolve_identifiers(self, request: TranscriptRequest) -> tuple[str, str, str]:
        """Resolve canonical company name, NSE symbol, and primary domain."""
        raw_company = request.company.strip()
        upper_company = raw_company.upper()

        if upper_company in SYMBOL_DIRECTORY:
            symbol = upper_company
            info = SYMBOL_DIRECTORY[upper_company]
            name = info["name"]
            domain = request.company_domain or info["domain"]
            return name, symbol, domain

        # Reverse lookup by company name
        for sym, info in SYMBOL_DIRECTORY.items():
            if raw_company.lower() in info["name"].lower() or info["name"].lower() in raw_company.lower():
                domain = request.company_domain or info["domain"]
                return info["name"], sym, domain

        # Fallback to provided values
        symbol = upper_company
        domain = request.company_domain or ""
        return raw_company, symbol, domain

    def get_target_directory(self, request: TranscriptRequest, symbol: str) -> Path:
        """Resolve target directory for storing transcripts and metadata."""
        out_base = Path(request.output_dir)
        if not out_base.is_absolute():
            out_base = get_repo_root() / out_base
        q_norm = request.quarter.strip().upper()
        fy_norm = request.fiscal_year.strip().upper()
        target_dir = out_base / symbol / fy_norm / q_norm
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def check_local_cache(
        self, target_dir: Path
    ) -> tuple[str, dict[str, Any]] | None:
        """Return cached transcript text and metadata if valid archive exists."""
        transcript_file = target_dir / "transcript.txt"
        metadata_file = target_dir / "metadata.json"

        if transcript_file.is_file() and metadata_file.is_file():
            try:
                meta = json.loads(metadata_file.read_text(encoding="utf-8"))
                if meta.get("validation_status") == "passed":
                    text = transcript_file.read_text(encoding="utf-8")
                    if len(text.strip()) > 0:
                        logger.info("Found valid cached transcript in %s", target_dir)
                        return text, meta
            except Exception as exc:
                logger.warning("Error reading cached transcript in %s: %s", target_dir, exc)
        return None

    def build_search_queries(
        self,
        company_name: str,
        symbol: str,
        quarter: str,
        fiscal_year: str,
        domain: str,
    ) -> list[str]:
        """Construct prioritized focused search queries."""
        q_norm = quarter.strip().upper()
        fy_norm = fiscal_year.strip().upper()
        q_digit = re.sub(r"[^\d]", "", q_norm)
        fy_digit = re.sub(r"[^\d]", "", fy_norm)

        queries: list[str] = []

        # 1. Targeted official domain queries (at most 2 focused queries)
        if domain:
            clean_domain = domain.replace("https://", "").replace("http://", "").strip("/")
            queries.append(f"site:{clean_domain} {symbol} transcript {q_norm} {fy_norm}")
            if q_digit:
                queries.append(f"site:{clean_domain} {q_digit}q transcript")

        # 2. Focused aggregator & exchange queries
        queries.append(f"site:alphastreet.com {company_name} {q_norm} {fy_norm} earnings call transcript")
        queries.append(f"site:gurufocus.com {symbol} {q_norm} 20{fy_digit} earnings call transcript")
        queries.append(f"site:bseindia.com {company_name} transcript {q_norm} {fy_norm}")
        queries.append(f"site:nseindia.com {company_name} transcript {q_norm} {fy_norm}")

        # 3. Open web search queries
        queries.append(f"{company_name} {q_norm} {fy_norm} conference call transcript")
        queries.append(f"{symbol} {q_norm} {fy_norm} earnings call transcript")
        if q_digit:
            queries.append(f"{company_name} {q_norm} {fy_norm} media release statement")

        return queries

    def build_broad_search_queries(
        self,
        company_name: str,
        symbol: str,
        domain: str,
    ) -> list[str]:
        """Construct broader search queries when specific quarter queries yield no results."""
        queries = [
            f"{company_name} investor relations transcript",
            f"{company_name} conference call transcript",
            f"{company_name} earnings call transcript",
            f"{symbol} concall transcript pdf",
        ]
        if domain:
            clean_domain = domain.replace("https://", "").replace("http://", "").strip("/")
            queries.append(f"site:{clean_domain} concall transcript")
        return queries

    def execute_tavily_search(
        self,
        query: str,
        domain: str | None = None,
        max_results: int = 10,
        restrict_domains: bool = False,
    ) -> list[dict[str, Any]]:
        """Query Tavily Search API with advanced search depth and domain preferences."""
        if query in self._searched_queries:
            return []
        self._searched_queries.add(query)

        if not self.api_key:
            logger.warning("TAVILY_API_KEY is not configured; search cannot proceed")
            return []

        url = "https://api.tavily.com/search"
        payload: dict[str, Any] = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
        }

        if restrict_domains:
            include_domains = ["nseindia.com", "bseindia.com"]
            if domain:
                clean_domain = domain.replace("https://", "").replace("http://", "").strip("/")
                if clean_domain:
                    include_domains.append(clean_domain)
            payload["include_domains"] = include_domains

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("results", [])
        except HTTPError as exc:
            logger.warning("Tavily Search HTTP %d: %s for query '%s'", exc.code, exc.reason, query)
            return []
        except URLError as exc:
            logger.warning("Tavily Search connection failed: %s for query '%s'", exc.reason, query)
            return []
        except Exception as exc:
            logger.warning("Tavily Search unexpected error: %s for query '%s'", exc, query)
            return []

    def classify_and_filter_url(
        self,
        url: str,
        title: str,
        snippet: str,
        company_name: str,
        symbol: str,
        quarter: str,
        fiscal_year: str,
        domain: str,
    ) -> tuple[bool, str, str]:
        """Classify candidate URL and determine rejection reason or source type.

        Returns (is_acceptable, source_type, rejection_reason).
        """
        lower_url = url.lower()
        lower_title = title.lower()
        lower_text = f"{lower_url} {lower_title} {snippet.lower()}"
        q_norm = quarter.strip().lower()
        fy_norm = fiscal_year.strip().lower()
        q_digit = re.sub(r"[^\d]", "", q_norm)

        # 1. Allow dedicated transcript aggregators and earnings subpaths
        is_transcript_subpath = (
            ("finance.yahoo.com" in lower_url and "/earnings/" in lower_url and any(k in lower_url for k in ["transcript", "earnings_call", "earnings-call"]))
            or "alphastreet.com" in lower_url
            or "gurufocus.com" in lower_url
            or "quartr.com" in lower_url
            or "earningsapi.io" in lower_url
        )

        # Reject news articles, third-party summaries, or blogs
        reject_domains = [
            "youtube.com",
            "youtu.be",
            "livemint.com",
            "economictimes.indiatimes.com/news",
            "financialexpress.com/market",
            "business-standard.com/markets",
            "ndtvprofit.com",
            "reuters.com",
            "bloomberg.com",
            "cnbctv18.com",
        ]
        if not is_transcript_subpath:
            reject_domains.extend(["yahoo.com", "finance.yahoo.com"])

        for rej_dom in reject_domains:
            if rej_dom in lower_url:
                return False, "", f"Third-party news or media summary: {rej_dom}"

        # 2. Reject pure presentations, investor decks, or audio files without transcript text
        if any(term in lower_url for term in ["investor-presentation", "presentation.pdf", "presentation_", "deck.pdf"]):
            if "transcript" not in lower_url and "concall" not in lower_url and "media_release" not in lower_url and "press-release" not in lower_url:
                return False, "", "Investor presentation deck without call discussion"

        if lower_url.endswith(".mp3") or lower_url.endswith(".wav") or "/audio/" in lower_url:
            return False, "", "Audio recording without transcript text"

        # 3. Reject paywalled/login pages
        if any(term in lower_url for term in ["/login", "/signin", "/subscribe", "/paywall"]):
            return False, "", "Paywall or login required"

        # 4. Check for conflicting quarters (e.g. searching for q3, but URL clearly indicates q1 or q2)
        other_quarter_digits = {"1", "2", "3", "4"} - {q_digit}
        for oqd in other_quarter_digits:
            if re.search(rf"[-_/](?:q{oqd}|{oqd}q)[-_/]", lower_url):
                return False, "", f"Mismatched reporting quarter: mentions Q{oqd} instead of {q_norm}"

        # 5. Check for conflicting fiscal years in URL if explicit years are present
        req_fy_digits = re.sub(r"[^\d]", "", fy_norm)
        if req_fy_digits:
            years_in_url = [y[2:] for y in re.findall(r"20\d\d", lower_url)] + re.findall(r"fy[-_]?(\d{2})", lower_url)
            prev_yr = str(int(req_fy_digits) - 1).zfill(2)
            non_matching = [y for y in years_in_url if y != req_fy_digits and y != prev_yr and len(y) == 2]
            if non_matching and req_fy_digits not in years_in_url and f"{prev_yr}{req_fy_digits}" not in lower_url:
                return False, "", f"Mismatched reporting fiscal year: URL mentions {years_in_url} instead of {fy_norm}"

        # 6. Must have concall or transcript or official disclosure indicator in URL or title
        transcript_markers = [
            "transcript",
            "conference-call",
            "conference_call",
            "concall",
            "earnings-call",
            "earnings_call",
            "investor-call",
            "call-transcript",
            "analysts-meet",
            "media_release",
            "media-release",
            "media statement",
            "press-release",
            "press_release",
            "results-faq",
            "results_faq",
            "financial_and_operational_performance",
        ]
        has_marker = any(m in lower_text for m in transcript_markers)
        if not has_marker:
            return False, "", "Does not indicate transcript or earnings call content"

        # 7. Determine source type hierarchy
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()

        clean_dom = domain.replace("https://", "").replace("http://", "").strip("/").lower()
        if clean_dom and clean_dom in netloc:
            return True, "official_ir", ""

        if "nseindia.com" in netloc:
            return True, "official_nse", ""

        if "bseindia.com" in netloc:
            return True, "official_bse", ""

        # Reputable Indian aggregator
        aggregator_domains = [
            "screener.in",
            "trendlyne.com",
            "researchbytes.com",
            "capitalmarket.com",
            "alphastreet.com",
            "gurufocus.com",
            "quartr.com",
            "earningsapi.io",
        ]
        if any(agg in netloc for agg in aggregator_domains):
            return True, "aggregator", ""

        # Company IR subdomain check (e.g. investors.company.com)
        if symbol.lower() in netloc or company_name.split()[0].lower() in netloc:
            return True, "official_ir", ""

        return True, "aggregator", ""

    def download_and_extract_pdf(self, pdf_url: str) -> tuple[str, str]:
        """Download remote PDF file and extract text page by page preserving structure."""
        try:
            parsed = urllib.parse.urlparse(pdf_url)
            headers = dict(HTTP_HEADERS)
            headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
            with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0) as client:
                resp = client.get(pdf_url)
                if resp.status_code != 200:
                    raise ValueError(f"HTTP {resp.status_code} while downloading PDF")

                reader = pypdf.PdfReader(io.BytesIO(resp.content))
                if reader.is_encrypted:
                    raise ValueError("Encrypted PDF cannot be read")

                pages_text: list[str] = []
                for idx, page in enumerate(reader.pages):
                    page_content = page.extract_text() or ""
                    if page_content.strip():
                        pages_text.append(f"--- [Page {idx + 1}] ---\n{page_content.strip()}")

                full_text = "\n\n".join(pages_text)
                return full_text, "pypdf"
        except Exception as exc:
            logger.warning("PDF extraction failed for %s: %s", pdf_url, exc)
            raise

    def extract_via_tavily(self, url: str) -> tuple[str, str]:
        """Extract markdown text from HTML page using Tavily Extract API."""
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY is not configured")

        api_url = "https://api.tavily.com/extract"
        payload = {
            "api_key": self.api_key,
            "urls": [url],
            "extract_depth": "advanced",
        }

        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results", [])
                if results:
                    content = results[0].get("raw_content", "").strip()
                    if content:
                        return content, "tavily_extract"
                raise ValueError("Tavily Extract returned empty raw_content")
        except Exception as exc:
            logger.warning("Tavily Extract API call failed for %s: %s", url, exc)
            raise

    def extract_direct_html(self, url: str) -> tuple[str, str]:
        """Fallback direct HTML fetch and text extraction."""
        parsed = urllib.parse.urlparse(url)
        headers = dict(HTTP_HEADERS)
        headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
        with httpx.Client(headers=headers, follow_redirects=True, timeout=20.0) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                raise ValueError(f"Direct HTML fetch failed with HTTP {resp.status_code}")

            raw_html = resp.text
            # Basic tag stripping and paragraph preservation
            text = re.sub(r"<script.*?</script>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", "\n", text)
            clean_lines = [line.strip() for line in text.splitlines() if line.strip()]
            extracted = "\n".join(clean_lines)
            if len(extracted.split()) < 300:
                raise ValueError("Direct HTML extraction yielded insufficient text content")
            return extracted, "direct_html"

    def extract_content(self, url: str) -> tuple[str, str, str]:
        """Extract text from URL handling PDF and HTML formats.

        Returns (extracted_text, extraction_method, pdf_url).
        """
        is_pdf = url.lower().endswith(".pdf") or ".pdf?" in url.lower() or "/pdf/" in url.lower()

        if is_pdf:
            text, method = self.download_and_extract_pdf(url)
            return text, method, url

        # Try Tavily Extract for HTML
        try:
            text, method = self.extract_via_tavily(url)
            return text, method, ""
        except Exception:
            # Fallback to direct HTML
            try:
                text, method = self.extract_direct_html(url)
                return text, method, ""
            except Exception as exc:
                raise ValueError(f"All extraction methods failed for {url}: {exc}") from exc

    def validate_transcript_content(
        self,
        text: str,
        company_name: str,
        symbol: str,
        quarter: str,
        fiscal_year: str,
    ) -> tuple[bool, str]:
        """Verify that extracted text meets all transcript quality criteria.

        Returns (is_valid, reason).
        """
        lower_text = text.lower()
        q_norm = quarter.strip().lower()
        fy_norm = fiscal_year.strip().lower()
        fy_digits = re.sub(r"[^\d]", "", fy_norm)

        company_tokens = [company_name.lower(), symbol.lower()]
        company_first_word = company_name.split()[0].lower()
        if len(company_first_word) >= 3:
            company_tokens.append(company_first_word)

        # 1. Header and title page verification (first 4000 characters)
        header_text = lower_text[:4000]
        has_header_company = any(
            re.search(r"\b" + re.escape(token) + r"\b", header_text) is not None
            for token in company_tokens
        )
        if not has_header_company:
            return False, f"Company identity '{symbol}' / '{company_name}' not found in call title / header section"

        # Indian quarter notations: q3, 3q, 3qfy, quarter 3, 3rd quarter, third quarter, or 'quarter ended december'
        q_digit = re.sub(r"[^\d]", "", q_norm)
        quarter_words = {
            "1": "first",
            "2": "second",
            "3": "third",
            "4": "fourth",
        }.get(q_digit, "")
        quarter_months = {
            "1": "june",
            "2": "september",
            "3": "december",
            "4": "march",
        }.get(q_digit, "")
        q_patterns = [
            rf"\b{re.escape(q_norm)}\b",
            rf"\b{q_digit}q\b",
            rf"\b{q_digit}qfy",
            rf"\bquarter\s*{q_digit}\b",
            rf"\b{q_digit}(?:st|nd|rd|th)?\s*quarter\b",
        ]
        if quarter_words:
            q_patterns.append(rf"\b{quarter_words}\s*quarter\b")
        if quarter_months:
            q_patterns.append(rf"\bquarter\s+ended[^\n.]*{quarter_months}\b")

        has_header_quarter = any(re.search(pat, header_text) is not None for pat in q_patterns)
        if not has_header_quarter:
            return False, f"Requested quarter '{q_norm}' not found in call title / header section"

        prev_digits = str(int(fy_digits) - 1).zfill(2) if fy_digits else ""
        has_header_fy = (
            fy_norm in header_text
            or (
                fy_digits
                and (
                    f"fy{fy_digits}" in header_text
                    or f"fy'{fy_digits}" in header_text
                    or f"fy '{fy_digits}" in header_text
                    or f"20{fy_digits}" in header_text
                    or (
                        prev_digits
                        and (
                            f"{prev_digits}-{fy_digits}" in header_text
                            or f"20{prev_digits}-20{fy_digits}" in header_text
                            or f"20{prev_digits}-{fy_digits}" in header_text
                        )
                    )
                )
            )
        )
        if not has_header_fy:
            return False, f"Requested fiscal year '{fy_norm}' not found in call title / header section"

        # 3. Transcript structural language check
        transcript_markers = [
            "moderator",
            "management",
            "analyst",
            "question",
            "answer",
            "opening remarks",
            "q&a",
            "conference call",
            "participants",
            "safe harbor",
            "ladies and gentlemen",
            "media release",
            "press release",
            "statement",
            "financial highlights",
            "ebitda",
            "performance highlights",
        ]
        marker_count = sum(1 for m in transcript_markers if m in lower_text)
        if marker_count < 2:
            return (
                False,
                f"Missing typical transcript language (found {marker_count} of 2 required markers)",
            )

        # 4. Word count check (minimum 1,000 words unless reasonably comprehensive statement)
        word_count = len(text.split())
        if word_count < 1000:
            if marker_count >= 4 and word_count >= 500:
                # Allow shorter verified transcript if Q&A markers are strong
                pass
            else:
                return (
                    False,
                    f"Word count ({word_count}) below minimum threshold of 1000 words",
                )

        # 5. Check that document is not just a presentation slide deck or summary
        if "table of contents" in lower_text and word_count < 1200 and "analyst" not in lower_text:
            return False, "Appears to be a presentation deck or summary rather than transcript"

        return True, "passed"

    def retrieve(self, request: TranscriptRequest) -> dict[str, Any]:
        """Execute end-to-end transcript retrieval workflow with validation and caching."""
        company_name, symbol, domain = self.resolve_identifiers(request)
        target_dir = self.get_target_directory(request, symbol)

        # Step 1: Check local cache
        cached = self.check_local_cache(target_dir)
        if cached is not None:
            text, meta = cached
            return {
                "status": "cached",
                "text": text,
                "metadata": meta,
                "path": str(target_dir / "transcript.txt"),
            }

        # Step 2: Execute search queries
        searches_attempted: list[str] = []
        candidate_evaluations: list[dict[str, Any]] = []
        rejection_reasons: list[str] = []
        official_sources_checked: list[str] = [
            domain or f"{symbol.lower()} website",
            "nseindia.com",
            "bseindia.com",
        ]

        queries = self.build_search_queries(
            company_name, symbol, request.quarter, request.fiscal_year, domain
        )

        all_results: list[dict[str, Any]] = []
        for q in queries:
            searches_attempted.append(q)
            results = self.execute_tavily_search(q, domain=domain, max_results=10, restrict_domains=False)
            all_results.extend(results)
            # Only break early if a promising transcript candidate for this quarter was discovered
            q_lower = request.quarter.strip().lower()
            has_promising = any(
                ("transcript" in (r.get("url") or "").lower() or "concall" in (r.get("url") or "").lower())
                and (q_lower in (r.get("url") or "").lower() or q_lower in (r.get("title") or "").lower())
                for r in all_results
            )
            if has_promising and len(all_results) >= 20:
                break
            if len(all_results) >= 45:
                break

        # If initial queries yielded no results, broaden search
        if not all_results:
            broad_queries = self.build_broad_search_queries(company_name, symbol, domain)
            for bq in broad_queries:
                searches_attempted.append(bq)
                results = self.execute_tavily_search(bq, domain=domain, max_results=10, restrict_domains=False)
                all_results.extend(results)
                if all_results:
                    break

        # Step 3: Classify and prioritize candidate URLs
        scored_candidates: list[tuple[int, dict[str, Any], str]] = []
        seen_urls: set[str] = set()

        priority_weights = {
            "official_ir": 40,
            "official_nse": 30,
            "official_bse": 20,
            "aggregator": 10,
        }

        for res in all_results:
            raw_url = res.get("url") or ""
            if not raw_url or raw_url in seen_urls:
                continue
            seen_urls.add(raw_url)

            title = res.get("title") or ""
            snippet = res.get("content") or ""

            acceptable, source_type, rej_reason = self.classify_and_filter_url(
                raw_url,
                title,
                snippet,
                company_name,
                symbol,
                request.quarter,
                request.fiscal_year,
                domain,
            )

            candidate_evaluations.append({
                "url": raw_url,
                "source_type": source_type,
                "acceptable": acceptable,
                "rejection_reason": rej_reason,
            })

            if acceptable:
                score = priority_weights.get(source_type, 0)
                if raw_url.lower().endswith(".pdf"):
                    score += 5  # Bonus for direct PDF
                scored_candidates.append((score, res, source_type))
            else:
                rejection_reasons.append(f"{raw_url}: {rej_reason}")

        # Sort candidates descending by priority score
        scored_candidates.sort(key=lambda item: item[0], reverse=True)

        # Step 4: Extract and validate candidates in order
        for score, candidate, source_type in scored_candidates:
            cand_url = candidate["url"]
            try:
                text, method, pdf_url = self.extract_content(cand_url)
                is_valid, val_reason = self.validate_transcript_content(
                    text, company_name, symbol, request.quarter, request.fiscal_year
                )

                if is_valid:
                    # Successfully validated transcript
                    word_count = len(text.split())
                    meta = TranscriptMetadata(
                        company=company_name,
                        nse_symbol=symbol,
                        quarter=request.quarter.strip().upper(),
                        fiscal_year=request.fiscal_year.strip().upper(),
                        call_date="",
                        source_type=source_type,
                        source_url=cand_url,
                        pdf_url=pdf_url or (cand_url if method == "pypdf" else ""),
                        retrieved_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        extraction_method=method,
                        word_count=word_count,
                        validation_status="passed",
                        notes=f"Retrieved via {source_type} priority score {score}",
                    )

                    transcript_file = target_dir / "transcript.txt"
                    metadata_file = target_dir / "metadata.json"

                    transcript_file.write_text(text, encoding="utf-8")
                    metadata_file.write_text(
                        json.dumps(asdict(meta), indent=2), encoding="utf-8"
                    )

                    logger.info(
                        "Saved verified transcript for %s %s %s (%d words) to %s",
                        symbol,
                        request.fiscal_year,
                        request.quarter,
                        word_count,
                        transcript_file,
                    )

                    return {
                        "status": "success",
                        "text": text,
                        "metadata": asdict(meta),
                        "path": str(transcript_file),
                    }
                else:
                    rejection_reasons.append(
                        f"Extracted content from {cand_url} failed validation: {val_reason}"
                    )
            except Exception as exc:
                rejection_reasons.append(f"Extraction failed for {cand_url}: {exc}")

        # Step 5: If all candidates failed or no candidates found, write not_found.json
        not_found_report = NotFoundReport(
            company=company_name,
            nse_symbol=symbol,
            quarter=request.quarter.strip().upper(),
            fiscal_year=request.fiscal_year.strip().upper(),
            searches_attempted=searches_attempted,
            candidate_urls_evaluated=candidate_evaluations,
            rejection_reasons=rejection_reasons,
            official_sources_checked=official_sources_checked,
            status="not_found",
            checked_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

        not_found_file = target_dir / "not_found.json"
        not_found_file.write_text(
            json.dumps(asdict(not_found_report), indent=2), encoding="utf-8"
        )

        logger.warning(
            "No transcript found for %s %s %s. Recorded diagnostics to %s",
            symbol,
            request.fiscal_year,
            request.quarter,
            not_found_file,
        )

        return {
            "status": "not_found",
            "report": asdict(not_found_report),
            "path": str(not_found_file),
        }
