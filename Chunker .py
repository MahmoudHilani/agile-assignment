"""Split a document into overlapping text chunks for embedding.

Strategy
--------
1. Prefer splitting on paragraph boundaries (double newline).
2. If a paragraph still exceeds ``chunk_size``, split it further on sentences
   (full-stop + space) and then on whitespace as a last resort.
3. Accumulate splits into chunks of at most ``chunk_size`` characters,
   carrying ``chunk_overlap`` characters from the previous chunk so that
   context is not lost at boundaries.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence

from app.domain.models import DocumentChunk


def chunk_text(
    text: str,
    source_name: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[DocumentChunk]:
    """Return a list of :class:`DocumentChunk` objects derived from *text*.

    Parameters
    ----------
    text:
        Full document text (already parsed to plain-text).
    source_name:
        A label stored in each chunk's metadata, e.g. the filename.
    chunk_size:
        Maximum character length of each chunk.
    chunk_overlap:
        Number of characters carried forward from the end of the previous chunk.

    Raises
    ------
    ValueError
        If *text* is empty after stripping, or if *chunk_size* < 1.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    text = text.strip()
    if not text:
        raise ValueError("Cannot chunk an empty document.")

    splits = _split_into_units(text, chunk_size)
    raw_chunks = _merge_units(splits, chunk_size, chunk_overlap)

    return [
        DocumentChunk(
            id=str(uuid.uuid4()),
            text=chunk,
            metadata={"source": source_name, "chunk_index": idx},
        )
        for idx, chunk in enumerate(raw_chunks)
    ]


# ── internal helpers ──────────────────────────────────────────────────────────

def _split_into_units(text: str, chunk_size: int) -> list[str]:
    """Break *text* into small units (≤ chunk_size chars where possible)."""
    # Primary split: paragraphs
    paragraphs = re.split(r"\n\n+", text)
    units: list[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) <= chunk_size:
            units.append(para)
        else:
            # Secondary split: sentences
            sentences = re.split(r"(?<=\.)\s+", para)
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                if len(sent) <= chunk_size:
                    units.append(sent)
                else:
                    # Last resort: whitespace tokens
                    words = sent.split()
                    buf = ""
                    for word in words:
                        candidate = f"{buf} {word}".strip() if buf else word
                        if len(candidate) <= chunk_size:
                            buf = candidate
                        else:
                            if buf:
                                units.append(buf)
                            buf = word
                    if buf:
                        units.append(buf)
    return units


def _merge_units(units: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    """Merge small units into chunks of at most *chunk_size* characters."""
    chunks: list[str] = []
    current = ""

    for unit in units:
        separator = "\n\n" if current else ""
        candidate = f"{current}{separator}{unit}"
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
                # Carry overlap from end of current chunk
                overlap_text = current[-chunk_overlap:] if chunk_overlap > 0 else ""
                separator = "\n\n" if overlap_text else ""
                current = f"{overlap_text}{separator}{unit}".strip()
            else:
                # Single unit already exceeds chunk_size — emit as-is
                chunks.append(unit)
                current = unit[-chunk_overlap:] if chunk_overlap > 0 else ""

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]