"""Verbatim-quote verification utility per PROJECT.md §4.9 and PROGRESS.md A2.12."""

from backend.app.config.loader import ParameterError
from backend.app.contracts.filings import Claim


def verify_quote(
    source_text: str,
    quote: str,
    start: int,
    end: int,
) -> bool:
    """Verify that a quote exists verbatim at specified character offsets.

    Parameters
    ----------
    source_text : str
        Original full document text.
    quote : str
        Quoted string to verify.
    start : int
        Start character offset (0-indexed, inclusive).
    end : int
        End character offset (0-indexed, exclusive).

    Returns
    -------
    bool
        True if `source_text[start:end] == quote` exactly. False otherwise.

    Raises
    ------
    ParameterError
        If offsets are inverted or negative.
    """
    if start < 0:
        raise ParameterError(
            field="start",
            value=start,
            allowed_range=(0, None),
            reason="Start offset cannot be negative",
        )
    if end < start:
        raise ParameterError(
            field="end",
            value=end,
            allowed_range=f">= {start}",
            reason="End offset cannot precede start offset",
        )
    if end > len(source_text):
        return False

    # Exact substring check: no case-folding, no fuzzy matching
    return source_text[start:end] == quote


def verify_claim_quote(source_text: str, claim: Claim) -> bool:
    """Verify that a Claim contract quote matches source text verbatim at its offsets."""
    return verify_quote(
        source_text=source_text,
        quote=claim.quote,
        start=claim.start,
        end=claim.end,
    )
