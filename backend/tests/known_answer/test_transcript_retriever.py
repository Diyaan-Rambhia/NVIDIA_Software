"""Known-answer tests for earnings-call transcript discovery, extraction, and validation."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.app.features.f2_filings.transcript_retriever import (
    TranscriptMetadata,
    TranscriptRequest,
    TranscriptRetrievalAgent,
)


def test_resolve_identifiers_known_symbols() -> None:
    """Agent resolves canonical names, symbols, and domains for known Indian equities."""
    agent = TranscriptRetrievalAgent()

    # Direct symbol
    req1 = TranscriptRequest(company="INFY", quarter="Q3", fiscal_year="FY25")
    name1, sym1, dom1 = agent.resolve_identifiers(req1)
    assert sym1 == "INFY"
    assert "Infosys" in name1
    assert "infosys.com" in dom1

    # Company name search
    req2 = TranscriptRequest(company="Maruti Suzuki", quarter="Q2", fiscal_year="FY25")
    name2, sym2, dom2 = agent.resolve_identifiers(req2)
    assert sym2 == "MARUTI"
    assert "Maruti Suzuki" in name2
    assert "marutisuzuki.com" in dom2

    # Custom company domain override
    req3 = TranscriptRequest(
        company="Custom Corp",
        quarter="Q1",
        fiscal_year="FY26",
        company_domain="customcorp.in",
    )
    name3, sym3, dom3 = agent.resolve_identifiers(req3)
    assert dom3 == "customcorp.in"


def test_build_search_queries() -> None:
    """Agent constructs focused queries for IR domain, NSE, BSE, and concalls."""
    agent = TranscriptRetrievalAgent()
    queries = agent.build_search_queries(
        company_name="Infosys Limited",
        symbol="INFY",
        quarter="Q3",
        fiscal_year="FY25",
        domain="infosys.com",
    )
    assert any("conference call transcript" in q for q in queries)
    assert any("earnings call transcript" in q for q in queries)
    assert any("site:infosys.com" in q for q in queries)
    assert any("site:bseindia.com" in q for q in queries)
    assert any("site:nseindia.com" in q for q in queries)


def test_classify_and_filter_url_hierarchy() -> None:
    """Agent correctly prioritizes IR > NSE > BSE > Aggregator and rejects invalid URLs."""
    agent = TranscriptRetrievalAgent()

    # 1. Official IR match
    acc, src, rej = agent.classify_and_filter_url(
        url="https://www.infosys.com/investors/reports/q3-fy25-transcript.pdf",
        title="Infosys Q3 FY25 Earnings Call Transcript",
        snippet="Moderator: Welcome to Infosys Q3 FY25 earnings call",
        company_name="Infosys Limited",
        symbol="INFY",
        quarter="Q3",
        fiscal_year="FY25",
        domain="infosys.com",
    )
    assert acc is True
    assert src == "official_ir"
    assert rej == ""

    # 2. NSE match
    acc, src, rej = agent.classify_and_filter_url(
        url="https://www.nseindia.com/corporate-filings/infy-concall-transcript.pdf",
        title="NSE Corporate Announcement Transcript",
        snippet="Concall transcript of Q3 FY25",
        company_name="Infosys Limited",
        symbol="INFY",
        quarter="Q3",
        fiscal_year="FY25",
        domain="infosys.com",
    )
    assert acc is True
    assert src == "official_nse"

    # 3. BSE match
    acc, src, rej = agent.classify_and_filter_url(
        url="https://www.bseindia.com/corporates/concall-transcript-infy.pdf",
        title="BSE Corporate Announcement Transcript",
        snippet="Concall transcript of Q3 FY25",
        company_name="Infosys Limited",
        symbol="INFY",
        quarter="Q3",
        fiscal_year="FY25",
        domain="infosys.com",
    )
    assert acc is True
    assert src == "official_bse"

    # 4. Aggregator match
    acc, src, rej = agent.classify_and_filter_url(
        url="https://www.screener.in/company/INFY/concall-transcript/",
        title="Infosys Concall Transcript",
        snippet="Full transcript of Infosys conference call",
        company_name="Infosys Limited",
        symbol="INFY",
        quarter="Q3",
        fiscal_year="FY25",
        domain="infosys.com",
    )
    assert acc is True
    assert src == "aggregator"

    # 5. Reject news media
    acc, _, rej = agent.classify_and_filter_url(
        url="https://finance.yahoo.com/news/infosys-earnings-call-highlights.html",
        title="Infosys Q3 Earnings Highlights",
        snippet="Summary of Infosys quarterly results",
        company_name="Infosys Limited",
        symbol="INFY",
        quarter="Q3",
        fiscal_year="FY25",
        domain="infosys.com",
    )
    assert acc is False
    assert "news" in rej.lower() or "media" in rej.lower()

    # 6. Reject pure presentation deck
    acc, _, rej = agent.classify_and_filter_url(
        url="https://www.infosys.com/investor-presentation.pdf",
        title="Investor Presentation Deck",
        snippet="Investor presentation slides",
        company_name="Infosys Limited",
        symbol="INFY",
        quarter="Q3",
        fiscal_year="FY25",
        domain="infosys.com",
    )
    assert acc is False
    assert "presentation" in rej.lower()

    # 7. Reject mismatched quarter
    acc, _, rej = agent.classify_and_filter_url(
        url="https://www.infosys.com/investors/q1-fy25-concall-transcript.pdf",
        title="Infosys Q1 FY25 Concall Transcript",
        snippet="Transcript of Q1 call",
        company_name="Infosys Limited",
        symbol="INFY",
        quarter="Q3",
        fiscal_year="FY25",
        domain="infosys.com",
    )
    assert acc is False
    assert "mismatched" in rej.lower()


def test_validate_transcript_content() -> None:
    """Agent validates presence of company, period, structural markers, and sufficient length."""
    agent = TranscriptRetrievalAgent()

    # Valid comprehensive transcript
    valid_text = (
        "Infosys Limited Q3 FY25 Earnings Conference Call.\n"
        "Moderator: Ladies and gentlemen, good day and welcome to the Infosys conference call.\n"
        "Management: Thank you. Welcome everyone. Our constant currency revenue growth was strong.\n"
        "Analyst: Congratulations on the margin expansion. Can you comment on large deal pipeline?\n"
        "Answer: Yes, our TCV remained robust throughout the quarter.\n"
        + " " + "word " * 1100
    )
    ok, reason = agent.validate_transcript_content(
        text=valid_text,
        company_name="Infosys Limited",
        symbol="INFY",
        quarter="Q3",
        fiscal_year="FY25",
    )
    assert ok is True
    assert reason == "passed"

    # Indian reporting notation (e.g. 3QFY25 or 2024-25)
    indian_notation_text = (
        "Tata Steel Limited Analyst Call to discuss results for 3QFY25 (FY 2024-25).\n"
        "Corporate Participants: T V Narendran, CEO & MD – Tata Steel Limited.\n"
        "Samita Shah: Good morning and welcome to the Tata Steel call for 3QFY25.\n"
        "Analyst: Can you speak about steel price realization and EBITDA?\n"
        "Management: Yes, our operating performance remained resilient.\n"
        + " " + "word " * 1100
    )
    ok_in, reason_in = agent.validate_transcript_content(
        text=indian_notation_text,
        company_name="Tata Steel Limited",
        symbol="TATASTEEL",
        quarter="Q3",
        fiscal_year="FY25",
    )
    assert ok_in is True
    assert reason_in == "passed"

    # Rejection 1: Missing company identity
    missing_company_text = (
        "Acme Global Q3 FY25 Earnings Call.\n"
        "Moderator: Good day.\n"
        "Management: Welcome.\n"
        + " " + "word " * 1100
    )
    ok, reason = agent.validate_transcript_content(
        text=missing_company_text,
        company_name="Infosys Limited",
        symbol="INFY",
        quarter="Q3",
        fiscal_year="FY25",
    )
    assert ok is False
    assert "identity" in reason.lower()

    # Rejection 2: Under 1,000 words without structural Q&A
    short_text = (
        "Infosys Limited Q3 FY25 Call.\n"
        "Management: Hello everyone.\n"
    )
    ok, reason = agent.validate_transcript_content(
        text=short_text,
        company_name="Infosys Limited",
        symbol="INFY",
        quarter="Q3",
        fiscal_year="FY25",
    )
    assert ok is False


def test_local_caching_and_not_found_report(tmp_path: Path) -> None:
    """Agent stores structured transcript and returns cache hits without searching."""
    agent = TranscriptRetrievalAgent()
    target_dir = tmp_path / "INFY" / "FY25" / "Q3"
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. When cache is empty, check_local_cache returns None
    assert agent.check_local_cache(target_dir) is None

    # 2. Write cached files
    sample_text = "Infosys Q3 FY25 Transcript.\n" + "word " * 1200
    (target_dir / "transcript.txt").write_text(sample_text, encoding="utf-8")
    meta = {
        "company": "Infosys Limited",
        "nse_symbol": "INFY",
        "quarter": "Q3",
        "fiscal_year": "FY25",
        "source_type": "official_ir",
        "validation_status": "passed",
        "word_count": 1200,
    }
    (target_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")

    # 3. Cache hit returns cached content
    cached = agent.check_local_cache(target_dir)
    assert cached is not None
    text, m = cached
    assert "Infosys" in text
    assert m["validation_status"] == "passed"

    # 4. End-to-end retrieve with cache hit
    req = TranscriptRequest(
        company="INFY",
        quarter="Q3",
        fiscal_year="FY25",
        output_dir=str(tmp_path),
    )
    result = agent.retrieve(req)
    assert result["status"] == "cached"
    assert result["metadata"]["nse_symbol"] == "INFY"


def test_retrieve_generates_not_found_when_no_candidates(tmp_path: Path) -> None:
    """Agent writes not_found.json with attempted searches when zero results found."""
    agent = TranscriptRetrievalAgent()
    # Mock Tavily search to return empty
    agent.execute_tavily_search = MagicMock(return_value=[])

    req = TranscriptRequest(
        company="NONEXISTENT_SYM",
        quarter="Q4",
        fiscal_year="FY29",
        output_dir=str(tmp_path),
    )
    result = agent.retrieve(req)

    assert result["status"] == "not_found"
    not_found_path = Path(result["path"])
    assert not_found_path.is_file()
    assert not_found_path.name == "not_found.json"

    data = json.loads(not_found_path.read_text(encoding="utf-8"))
    assert data["status"] == "not_found"
    assert len(data["searches_attempted"]) > 0
    assert len(data["official_sources_checked"]) > 0
