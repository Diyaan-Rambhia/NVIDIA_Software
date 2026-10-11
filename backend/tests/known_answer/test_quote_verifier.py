"""Known-answer tests for verbatim quote verifier per PROGRESS.md A2.12."""

import pytest

from backend.app.config.loader import ParameterError
from backend.app.contracts.filings import Claim
from backend.app.features.f2_filings.quote_verifier import verify_claim_quote, verify_quote


def test_quote_exact_match_passes() -> None:
    """Exact verbatim match returns True."""
    doc = "HDFC Bank reported net profit of ₹16,821 crore, up 33.5% YoY."
    quote = "up 33.5% YoY"
    start = doc.index(quote)
    end = start + len(quote)

    assert verify_quote(doc, quote, start, end) is True


def test_quote_near_miss_case_difference_fails() -> None:
    """Case mismatch must fail (exact substring only, no case folding)."""
    doc = "Infosys delivered strong revenue growth of 7.9%."
    quote = "Strong revenue growth of 7.9%"  # capitalized 'S'
    start = doc.index("strong revenue growth of 7.9%")
    end = start + len(quote)

    assert verify_quote(doc, quote, start, end) is False


def test_quote_near_miss_trailing_whitespace_fails() -> None:
    """Trailing whitespace near-miss must fail without loose normalization."""
    doc = "Larsen & Toubro order inflow grew 35% in Q3."
    quote = "order inflow grew 35% "  # extra trailing space
    start = doc.index("order inflow grew 35%")
    end = start + len("order inflow grew 35%")

    assert verify_quote(doc, quote, start, end) is False


def test_quote_off_by_one_offset_fails() -> None:
    """Off-by-one offsets must fail exact substring comparison."""
    doc = "Operating margin expanded by 50 bps."
    quote = "expanded by 50 bps"
    start = doc.index(quote)
    end = start + len(quote)

    # Shift start by 1
    assert verify_quote(doc, quote, start + 1, end) is False
    # Shift end by 1
    assert verify_quote(doc, quote, start, end - 1) is False


def test_quote_unicode_exact_match() -> None:
    """Unicode characters like ₹ and Indian script match verbatim."""
    doc = "कंपनी का शुद्ध लाभ ₹4,500 करोड़ रहा।"
    quote = "₹4,500 करोड़"
    start = doc.index(quote)
    end = start + len(quote)

    assert verify_quote(doc, quote, start, end) is True

    # Near-miss: standard Latin Rs. instead of ₹
    wrong_quote = "Rs.4,500 करोड़"
    assert verify_quote(doc, wrong_quote, start, end) is False


def test_verify_claim_contract_quote() -> None:
    """verify_claim_quote correctly verifies valid and invalid Claim instances."""
    doc = "Revenue from operations reached ₹25,000 crore."
    quote = "₹25,000 crore"
    start = doc.index(quote)
    end = start + len(quote)

    valid_claim = Claim(
        metric="revenue",
        descriptor="reached",
        direction="up",
        quote=quote,
        start=start,
        end=end,
        period="Q3 FY25",
        basis="reported",
    )
    assert verify_claim_quote(doc, valid_claim) is True

    # Tampered quote in claim
    tampered_claim = Claim(
        metric="revenue",
        descriptor="reached",
        direction="up",
        quote="₹30,000 crore",
        start=start,
        end=end,
        period="Q3 FY25",
        basis="reported",
    )
    assert verify_claim_quote(doc, tampered_claim) is False


def test_quote_invalid_offsets_raise() -> None:
    """Negative start or inverted end offsets raise ParameterError."""
    doc = "ITC Limited agribusiness segment revenue grew."

    with pytest.raises(ParameterError) as exc_neg:
        verify_quote(doc, "agribusiness", -1, 10)
    assert exc_neg.value.field == "start"

    with pytest.raises(ParameterError) as exc_inv:
        verify_quote(doc, "agribusiness", 15, 10)
    assert exc_inv.value.field == "end"


def test_quote_out_of_bounds_end_returns_false() -> None:
    """End offset beyond text length returns False."""
    doc = "Brief note."
    assert verify_quote(doc, "Brief", 0, 100) is False
