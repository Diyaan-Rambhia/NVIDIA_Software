"""Text chunking utility with character offsets per PROJECT.md §4.9 and A2.12."""

from pydantic import Field

from backend.app.config.loader import ParameterError
from backend.app.contracts.common import StrictContractModel


class TextChunk(StrictContractModel):
    """Text chunk with stable, reproducible character offsets into source text."""

    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    index: int = Field(ge=0)


def chunk_text(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    """Chunk source text into overlapping segments with stable character offsets.

    Parameters
    ----------
    text : str
        Source text to chunk.
    chunk_size : int
        Maximum character count per chunk. Sourced from config/parameters.yaml.
    chunk_overlap : int
        Character overlap between consecutive chunks. Sourced from config/parameters.yaml.

    Returns
    -------
    list[TextChunk]
        Ordered list of chunks with exact [start, end) character offsets.
        Guarantees that slicing `text[chunk.start:chunk.end] == chunk.text`.

    Raises
    ------
    ParameterError
        If chunk_size <= 0, chunk_overlap < 0, or chunk_size <= chunk_overlap.
    """
    if chunk_size <= 0:
        raise ParameterError(
            field="chunk_size",
            value=chunk_size,
            allowed_range=(1, None),
            reason="chunk_size must be strictly positive",
        )
    if chunk_overlap < 0:
        raise ParameterError(
            field="chunk_overlap",
            value=chunk_overlap,
            allowed_range=(0, None),
            reason="chunk_overlap cannot be negative",
        )
    if chunk_size <= chunk_overlap:
        raise ParameterError(
            field="chunk_size",
            value=chunk_size,
            allowed_range=f"> {chunk_overlap}",
            reason="chunk_size must be strictly greater than chunk_overlap",
        )

    n = len(text)
    if n == 0:
        return []

    if n <= chunk_size:
        return [TextChunk(text=text, start=0, end=n, index=0)]

    chunks: list[TextChunk] = []
    step = chunk_size - chunk_overlap
    start = 0
    idx = 0

    while start < n:
        end = min(start + chunk_size, n)
        chunk_slice = text[start:end]
        chunks.append(TextChunk(text=chunk_slice, start=start, end=end, index=idx))
        idx += 1
        if end >= n:
            break
        start += step

    return chunks
