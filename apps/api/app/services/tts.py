"""Text-to-speech orchestration service.

Responsibilities
----------------
- Clean raw answer text before synthesis (strip markdown, excessive whitespace, etc.)
- Split cleaned text into segments that fit within a TTS provider's character limit
- Synthesize each segment, retrying with smaller sub-chunks when a provider rejects
  an oversized segment
- Assemble segments into a single AudioSynthesis or yield them one at a time for
  streamed responses
- Surface TTS errors as TTSError without crashing the request flow

The service depends only on the TextToSpeechProvider protocol defined in
``app.services.interfaces`` so any concrete provider (OpenAI, ElevenLabs, gTTS …)
can be swapped in without touching this file.
"""

from __future__ import annotations

import base64
import logging
import re
from collections.abc import Generator, Sequence

from app.domain.models import AudioSynthesis
from app.services.interfaces import TextToSpeechProvider

logger = logging.getLogger(__name__)

# Default character limit per TTS request segment.
# Most cloud providers accept 4 000–5 000 characters; 4 000 is a safe default.
DEFAULT_CHUNK_LIMIT: int = 4_000

# When a chunk is rejected for being too long we split it in half and retry.
MIN_CHUNK_CHARS: int = 50


class TTSError(Exception):
    """Raised when TTS synthesis fails and cannot be recovered."""


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

_MARKDOWN_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`]+`")
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_BOLD_ITALIC = re.compile(r"(\*{1,3}|_{1,3})(.*?)\1")
_HORIZONTAL_RULE = re.compile(r"^\s*[-*_]{3,}\s*$", re.MULTILINE)
_EXTRA_WHITESPACE = re.compile(r"[ \t]{2,}")
_BLANK_LINES = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Return *text* with markdown and noise removed, ready for TTS input."""
    text = _MARKDOWN_IMAGE.sub("", text)
    text = _MARKDOWN_CODE_BLOCK.sub(" ", text)
    text = _INLINE_CODE.sub(lambda m: m.group(0)[1:-1], text)  # keep readable text
    text = _MARKDOWN_LINK.sub(r"\1", text)          # keep link label
    text = _HEADING.sub("", text)
    text = _BOLD_ITALIC.sub(r"\2", text)
    text = _HORIZONTAL_RULE.sub("", text)
    text = _EXTRA_WHITESPACE.sub(" ", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def split_into_chunks(text: str, limit: int = DEFAULT_CHUNK_LIMIT) -> list[str]:
    """Split *text* into segments no longer than *limit* characters.

    Splits prefer sentence boundaries ('. ', '? ', '! ') then paragraph
    boundaries then word boundaries, so that each chunk is a coherent unit.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    _split_recursive(text, limit, chunks)
    return [c for c in chunks if c.strip()]


def _split_recursive(text: str, limit: int, out: list[str]) -> None:
    if len(text) <= limit:
        out.append(text)
        return

    # Try sentence boundary first, then paragraph, then word, then hard cut.
    boundary = _find_boundary(text, limit)
    out.append(text[:boundary].strip())
    _split_recursive(text[boundary:].strip(), limit, out)


def _find_boundary(text: str, limit: int) -> int:
    """Return the best split index <= *limit* within *text*."""
    window = text[:limit]

    for delimiter in (". ", "? ", "! ", "\n\n", "\n", " "):
        pos = window.rfind(delimiter)
        if pos > 0:
            return pos + len(delimiter)

    # Hard cut as last resort.
    return limit


# ---------------------------------------------------------------------------
# Synthesis with retry
# ---------------------------------------------------------------------------

def _synthesize_with_retry(
    provider: TextToSpeechProvider,
    segment: str,
    attempt: int = 0,
) -> AudioSynthesis:
    """Synthesize *segment*, halving and retrying up to log2(len/MIN) times."""
    try:
        return provider.synthesize(segment)
    except Exception as exc:  # noqa: BLE001
        half = len(segment) // 2
        if half < MIN_CHUNK_CHARS:
            raise TTSError(
                f"TTS provider failed on segment of {len(segment)} chars "
                f"and it is too short to split further: {exc}"
            ) from exc

        logger.warning(
            "TTS provider rejected segment (%d chars, attempt %d); "
            "retrying with two halves. Error: %s",
            len(segment),
            attempt,
            exc,
        )
        left = _synthesize_with_retry(provider, segment[:half].strip(), attempt + 1)
        right = _synthesize_with_retry(provider, segment[half:].strip(), attempt + 1)

        # Concatenate raw audio bytes from both halves.
        return AudioSynthesis(
            audio_bytes=left.audio_bytes + right.audio_bytes,
            mime_type=left.mime_type,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def synthesize_answer(
    provider: TextToSpeechProvider,
    answer: str,
    chunk_limit: int = DEFAULT_CHUNK_LIMIT,
) -> AudioSynthesis:
    """Synthesize *answer* as a single AudioSynthesis object.

    The answer is cleaned, split into safe segments, each segment is
    synthesized (with retry on length errors), and the audio bytes are
    concatenated into one result.

    Raises
    ------
    TTSError
        If any segment fails synthesis even after splitting.
    """
    cleaned = clean_text(answer)
    if not cleaned:
        raise TTSError("Answer text is empty after cleaning; nothing to synthesize.")

    segments = split_into_chunks(cleaned, limit=chunk_limit)
    logger.debug("Synthesizing %d segment(s) for answer of %d chars.", len(segments), len(cleaned))

    parts: list[AudioSynthesis] = []
    for i, segment in enumerate(segments):
        try:
            part = _synthesize_with_retry(provider, segment)
            parts.append(part)
        except TTSError:
            logger.error("Failed to synthesize segment %d/%d; aborting.", i + 1, len(segments))
            raise

    mime_type = parts[0].mime_type
    combined_bytes = b"".join(p.audio_bytes for p in parts)
    return AudioSynthesis(audio_bytes=combined_bytes, mime_type=mime_type)


def stream_answer_chunks(
    provider: TextToSpeechProvider,
    answer: str,
    chunk_limit: int = DEFAULT_CHUNK_LIMIT,
) -> Generator[AudioSynthesis, None, None]:
    """Yield one AudioSynthesis per text segment.

    Suitable for streaming responses where audio chunks are sent to the client
    as soon as each segment is ready, rather than waiting for full synthesis.

    Raises
    ------
    TTSError
        If any segment fails synthesis even after splitting.
    """
    cleaned = clean_text(answer)
    if not cleaned:
        raise TTSError("Answer text is empty after cleaning; nothing to synthesize.")

    segments = split_into_chunks(cleaned, limit=chunk_limit)
    for segment in segments:
        yield _synthesize_with_retry(provider, segment)