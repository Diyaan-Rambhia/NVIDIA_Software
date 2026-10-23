"""Known-answer tests for Stage 1 and Stage 2 enhancements."""

import io
import json
import zipfile
import pytest

from backend.app.auth.models import LoginResponse, RefreshRequest, RefreshResponse
from backend.app.features.files.extractor import extract_file_content
from backend.app.llm.exceptions import NonProseAnswerError, TierUnavailableError
from backend.app.llm.guard import assert_plain_prose, clean_prose_text
from backend.app.llm.registry import resolve_tier_model


def test_model_tier_resolution_structural_inputs() -> None:
    """Test model tier resolution: deny list ('llama'), pattern order, and unavailable states."""
    models_config = {
        "deny_patterns": ["llama"],
        "tiers": {
            "fast": {"patterns": ["Lightning", "Nano-30B"], "enabled": True},
            "balanced": {"patterns": ["Super-120b"], "enabled": True},
            "deep": {"patterns": ["Ultra-550b"], "enabled": True},
            "vision": {
                "patterns": ["Omni"],
                "enabled": False,
                "status": "disabled",
                "reason": "vision tier scheduled for v2",
            },
        },
    }

    # 1. Deny list: model containing 'llama' is strictly ignored even if pattern matches
    catalog_with_llama = ["meta-llama-3.1-Lightning-model", "other-Lightning-model"]
    resolved, reason = resolve_tier_model("fast", catalog_with_llama, models_config)
    assert resolved == "other-Lightning-model"
    assert "llama" not in resolved.lower()

    # If only llama matches, it must be unavailable
    catalog_only_llama = ["meta-llama-3.1-Lightning-model"]
    resolved, reason = resolve_tier_model("fast", catalog_only_llama, models_config)
    assert resolved is None
    assert reason is not None
    assert "no allowed model" in reason.lower()

    # 2. Pattern order: 'Lightning' takes precedence over 'Nano-30B'
    catalog_both_patterns = ["sample-Nano-30B-model", "sample-Lightning-model"]
    resolved, reason = resolve_tier_model("fast", catalog_both_patterns, models_config)
    assert resolved == "sample-Lightning-model"

    # If Lightning is absent, Nano-30B is resolved
    catalog_second_pattern = ["sample-Nano-30B-model"]
    resolved, reason = resolve_tier_model("fast", catalog_second_pattern, models_config)
    assert resolved == "sample-Nano-30B-model"

    # 3. Unavailable tier: vision is disabled for v2
    resolved_vision, reason_vision = resolve_tier_model("vision", ["sample-Omni-v1"], models_config)
    assert resolved_vision is None
    assert "vision tier scheduled for v2" in reason_vision

    # 4. Unknown tier gives clear unavailable reason
    resolved_unknown, reason_unknown = resolve_tier_model("quantum", ["sample-quantum"], models_config)
    assert resolved_unknown is None
    assert "unknown tier" in reason_unknown.lower()


def test_answer_format_prose_post_check_and_cleaner() -> None:
    """Test plain prose enforcement, non-prose rejection, and raw ** asterisk cleaning."""
    # 1. Code blocks must be rejected with 'model returned a non-prose answer'
    with pytest.raises(NonProseAnswerError, match="model returned a non-prose answer"):
        assert_plain_prose("Here is the answer:\n```python\nprint('hello')\n```")

    # 2. Raw JSON objects must be rejected
    with pytest.raises(NonProseAnswerError, match="model returned a non-prose answer"):
        assert_plain_prose('{"status": "success", "symbol": "INFY", "metrics": {"revenue": 100}}')

    # 3. Code-heavy answers must be rejected
    code_text = "def calculate_xirr():\n    import math\n    x = 10\n    return x\n"
    with pytest.raises(NonProseAnswerError, match="model returned a non-prose answer"):
        assert_plain_prose(code_text, max_code_density=0.20)

    # 4. Clean plain prose must pass
    valid_prose = (
        "The absorption ratio increased during the period, reflecting tighter cross-sector linkages. "
        "Reported revenues and operating margins remained steady."
    )
    assert_plain_prose(valid_prose)

    # 5. Raw markdown asterisks and tool names are cleanly stripped/sanitized
    dirty_text = "Analysis shows **strong growth** in revenue. Tool **f1_contagion** evaluated pairs."
    cleaned = clean_prose_text(dirty_text)
    assert "**" not in cleaned
    assert "strong growth" in cleaned
    assert "f1_contagion" not in cleaned
    assert "F1 Contagion" in cleaned


def test_auth_refresh_contracts() -> None:
    """Test LoginResponse and RefreshRequest/RefreshResponse models."""
    import uuid

    uid = uuid.uuid4()
    login_resp = LoginResponse(
        access_token="test_access_jwt",
        token_type="bearer",
        user_id=uid,
        refresh_token="test_refresh_jwt",
    )
    assert login_resp.refresh_token == "test_refresh_jwt"

    refresh_req = RefreshRequest(refresh_token="test_refresh_jwt")
    assert refresh_req.refresh_token == "test_refresh_jwt"

    refresh_resp = RefreshResponse(
        access_token="new_access_jwt",
        token_type="bearer",
        user_id=uid,
        refresh_token="new_refresh_jwt",
    )
    assert refresh_resp.access_token == "new_access_jwt"
    assert refresh_resp.refresh_token == "new_refresh_jwt"


def test_file_extraction_safety_real_files() -> None:
    """Test in-memory file extraction with small real files and security validations."""
    import docx
    import openpyxl
    import pypdf

    # 1. Build real small PDF in memory
    pdf_writer = pypdf.PdfWriter()
    page = pdf_writer.add_blank_page(width=72, height=72)
    # Write empty blank page text test
    pdf_bytes_io = io.BytesIO()
    pdf_writer.write(pdf_bytes_io)
    # Real PDF with text using stream
    pdf_writer2 = pypdf.PdfWriter()
    pdf_writer2.add_page(page)
    # Test valid text extraction with small docx
    doc = docx.Document()
    doc.add_paragraph("Quarterly earnings report summary.")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Revenue"
    table.rows[0].cells[1].text = "1000 Cr"
    docx_io = io.BytesIO()
    doc.save(docx_io)
    docx_bytes = docx_io.getvalue()

    extracted_docx = extract_file_content("report.docx", docx_bytes)
    assert "Quarterly earnings report summary." in extracted_docx
    assert "Revenue | 1000 Cr" in extracted_docx

    # 2. Build real small XLSX in memory
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Metric", "Amount"])
    ws.append(["Operating Revenue", 5000])
    # Add a formula; extraction must read value only and never crash or execute
    ws.append(["Formula Cell", "=SUM(B2:B2)"])
    xlsx_io = io.BytesIO()
    wb.save(xlsx_io)
    xlsx_bytes = xlsx_io.getvalue()

    extracted_xlsx = extract_file_content("finances.xlsx", xlsx_bytes)
    assert "Operating Revenue | 5000" in extracted_xlsx

    # 3. Reject macro-enabled file (.xlsm)
    with pytest.raises(ValueError, match="Macro-enabled office files"):
        extract_file_content("exploit.xlsm", b"dummy content")

    # 4. Reject images as v2
    with pytest.raises(ValueError, match="not available yet"):
        extract_file_content("chart.png", b"dummy png content", content_type="image/png")

    # 5. Reject empty file
    with pytest.raises(ValueError, match="empty"):
        extract_file_content("empty.docx", b"")

    # 6. Refuse decompression bomb zip with huge uncompressed size
    fake_bomb_io = io.BytesIO()
    with zipfile.ZipFile(fake_bomb_io, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write an entry that advertises a large uncompressed size
        zinfo = zipfile.ZipInfo("large.xml")
        zinfo.file_size = 100 * 1024 * 1024  # 100 MB declared size
        zf.writestr(zinfo, b"a" * 1000)

    bomb_bytes = fake_bomb_io.getvalue()
    with pytest.raises(ValueError, match="Uncompressed archive size.*exceeds safety limit"):
        extract_file_content("bomb.docx", bomb_bytes, limits={"file_extract_max_uncompressed_bytes": 500})



def test_yfinance_client_live_cache_and_derived_only() -> None:
    """Test yfinance client TTL caching and failure behavior."""
    from backend.app.data.yfinance_client import (
        _YFINANCE_CACHE,
        clean_ticker_symbol,
        fetch_live_ticker_history,
    )

    # 1. Ticker symbol normalization
    assert clean_ticker_symbol("INFY") == "INFY.NS"
    assert clean_ticker_symbol("NSEI") == "^NSEI"
    assert clean_ticker_symbol("^BSESN") == "^BSESN"

    # 2. Server TTL caching
    dummy_prices = {"2026-01-01": 100.0, "2026-01-02": 102.5}
    _YFINANCE_CACHE["TEST_TICKER.NS"] = (9999999999.0, dummy_prices)  # Far future timestamp

    cached = fetch_live_ticker_history("TEST_TICKER", cache_ttl_seconds=3600)
    assert cached == dummy_prices

    # 3. Failure on unknown ticker with no cache gives clear error naming ticker
    with pytest.raises(ValueError, match="Failed to fetch market data from yfinance for ticker 'NONEXISTENT_XYZ'"):
        fetch_live_ticker_history("NONEXISTENT_XYZ", cache_ttl_seconds=1)


def test_f2_lookup_and_annual_only_rules() -> None:
    """Test Feature 2 lookup validation and annual-only rule restrictions."""
    from backend.app.features.f2_filings.lookup import perform_f2_lookup

    # 1. Period validation: invalid format must be rejected
    with pytest.raises(ValueError, match="Invalid fiscal period format"):
        perform_f2_lookup(company_query="INFY", period_query="invalid_period_format")

    # 2. Unknown company must be rejected with official equity list error
    with pytest.raises(ValueError, match="not found in official NSE equity list"):
        perform_f2_lookup(company_query="UNKNOWN_NONEXISTENT_CORP_12345", period_query="Q3 FY25")

    # 3. Quarterly filing evaluation: R5 and R6 must be not_applicable
    lookup_res = perform_f2_lookup(company_query="INFY", period_query="Q3 FY25")
    assert lookup_res["symbol"] == "INFY"
    assert "RevenueFromOperations" in lookup_res["verified_metrics"]

    rules = {r["rule_id"]: r for r in lookup_res["rules_evaluated"]}
    assert "R0" in rules
    # R5 (cash quality) and R6 (working capital) must be not_applicable on quarterly filings
    assert rules["R5"]["status"] == "not_applicable"
    assert "annual filings" in rules["R5"]["reason"].lower()
    assert rules["R6"]["status"] == "not_applicable"
    assert "annual filings" in rules["R6"]["reason"].lower()


def test_agent_orchestrator_tier_and_attachment() -> None:
    """Test Agent loop with model_tier and attachment_text."""
    import uuid
    from backend.app.agent.orchestrator import run_agent_loop
    from backend.app.auth.models import UserClaims
    from backend.app.config.env import Settings
    from backend.tests.helpers.placeholder import PlaceholderProvider

    user = UserClaims(user_id=uuid.uuid4(), email="test@example.com", plan="retail_free")
    dev_settings = Settings(app_env="development")
    provider = PlaceholderProvider(settings=dev_settings)

    # 1. Unavailable tier (vision) raises TierUnavailableError
    with pytest.raises(TierUnavailableError, match="vision tier scheduled for v2"):
        run_agent_loop(
            query="Check systemic correlation",
            user=user,
            model_tier="vision",
            provider=provider,
        )

    # 2. Valid tier with attachment data runs and includes reference snippet
    resp = run_agent_loop(
        query="Check systemic correlation",
        user=user,
        model_tier="balanced",
        attachment_text="Audit Note: Company reported unexpected inventory surge.",
        provider=provider,
    )
    assert resp.answer is not None
    assert "Reference data observed" in resp.answer
    assert "**" not in resp.answer

