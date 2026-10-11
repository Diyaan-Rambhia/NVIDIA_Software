"""Known-answer tests for text chunker with stable character offsets per PROGRESS.md A2.12."""

import pytest

from backend.app.config.loader import ParameterError
from backend.app.features.f2_filings.text_chunker import chunk_text


def test_chunker_empty_string() -> None:
    """Empty string returns empty chunk list."""
    chunks = chunk_text("", chunk_size=100, chunk_overlap=20)
    assert chunks == []


def test_chunker_text_shorter_than_chunk_size() -> None:
    """Text shorter than chunk size returns a single chunk spanning the full text."""
    sample = "Reliance Industries reported consolidated Q3 results."
    chunks = chunk_text(sample, chunk_size=100, chunk_overlap=10)
    assert len(chunks) == 1
    assert chunks[0].start == 0
    assert chunks[0].end == len(sample)
    assert chunks[0].text == sample
    assert sample[chunks[0].start : chunks[0].end] == chunks[0].text


def test_chunker_text_exact_chunk_size() -> None:
    """Text exactly equal to chunk size returns a single chunk."""
    sample = "1234567890"
    chunks = chunk_text(sample, chunk_size=10, chunk_overlap=2)
    assert len(chunks) == 1
    assert chunks[0].start == 0
    assert chunks[0].end == 10
    assert chunks[0].text == sample


def test_chunker_multiple_chunks_roundtrip() -> None:
    """Overlapping chunks must round-trip exactly when slicing the original text."""
    text = (
        "Tata Consultancy Services reported strong quarterly performance. "
        "Revenue from operations grew 8.5% YoY in constant currency terms. "
        "Operating margin stood at 25.1%, expanding 40 bps sequentially. "
        "Order book total contract value reached record levels across all major markets."
    )
    chunk_size = 50
    chunk_overlap = 15

    chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    assert len(chunks) > 1

    # Every chunk must round-trip perfectly by slicing the original
    for chunk in chunks:
        assert text[chunk.start : chunk.end] == chunk.text
        assert len(chunk.text) <= chunk_size
        assert chunk.end - chunk.start == len(chunk.text)

    # Verify overlap step
    step = chunk_size - chunk_overlap
    for i in range(len(chunks) - 1):
        assert chunks[i + 1].start == chunks[i].start + step


def test_chunker_unicode_roundtrip() -> None:
    """Unicode characters (e.g. ₹ symbol, Hindi text) round-trip with character offsets."""
    unicode_text = (
        "रिलायंस इंडस्ट्रीज ने ₹1,20,000 करोड़ का राजस्व दर्ज किया। "
        "मुनाफे में 12% की वृद्धि देखी गई। "
        "सभी व्यावसायिक क्षेत्रों में मजबूत प्रदर्शन रहा।"
    )
    chunk_size = 35
    chunk_overlap = 10

    chunks = chunk_text(unicode_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    assert len(chunks) >= 3

    for chunk in chunks:
        # Slicing unicode text by character offsets reproduces chunk.text identically
        assert unicode_text[chunk.start : chunk.end] == chunk.text


def test_chunker_invalid_chunk_size_raises() -> None:
    """Zero or negative chunk size raises ParameterError."""
    with pytest.raises(ParameterError) as exc:
        chunk_text("Sample text", chunk_size=0, chunk_overlap=0)
    assert exc.value.field == "chunk_size"

    with pytest.raises(ParameterError) as exc_neg:
        chunk_text("Sample text", chunk_size=-10, chunk_overlap=5)
    assert exc_neg.value.field == "chunk_size"


def test_chunker_negative_overlap_raises() -> None:
    """Negative overlap raises ParameterError."""
    with pytest.raises(ParameterError) as exc:
        chunk_text("Sample text", chunk_size=100, chunk_overlap=-5)
    assert exc.value.field == "chunk_overlap"


def test_chunker_overlap_greater_than_or_equal_size_raises() -> None:
    """Overlap >= chunk_size raises ParameterError."""
    with pytest.raises(ParameterError) as exc_eq:
        chunk_text("Sample text", chunk_size=100, chunk_overlap=100)
    assert exc_eq.value.field == "chunk_size"

    with pytest.raises(ParameterError) as exc_gt:
        chunk_text("Sample text", chunk_size=100, chunk_overlap=120)
    assert exc_gt.value.field == "chunk_size"
