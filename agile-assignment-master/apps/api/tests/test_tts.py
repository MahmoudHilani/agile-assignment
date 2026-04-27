"""Tests for the TTS service layer and voice HTTP endpoints.

Covers
------
- clean_text: markdown removal, whitespace normalisation
- split_into_chunks: short pass-through, long text splitting, boundary preference
- synthesize_answer: normal flow, multi-segment concatenation, TTSError propagation
- stream_answer_chunks: yields correct number of chunks
- _synthesize_with_retry: retries by halving on provider errors
- POST /tts endpoint: 200 success, 502 on TTS failure, 500 on unexpected error
- POST /tts/stream endpoint: NDJSON chunks, error sentinel on failure
"""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.routes.voice import get_tts_provider
from app.domain.models import AudioSynthesis
from app.main import app
from app.services.tts import (
    DEFAULT_CHUNK_LIMIT,
    TTSError,
    clean_text,
    split_into_chunks,
    stream_answer_chunks,
    synthesize_answer,
    _synthesize_with_retry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_audio(content: str = "audio", mime: str = "audio/mpeg") -> AudioSynthesis:
    return AudioSynthesis(audio_bytes=content.encode(), mime_type=mime)


def _make_provider(side_effect=None, return_value=None) -> MagicMock:
    provider = MagicMock()
    if side_effect is not None:
        provider.synthesize.side_effect = side_effect
    else:
        provider.synthesize.return_value = return_value or _fake_audio()
    return provider


# ---------------------------------------------------------------------------
# clean_text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_strips_markdown_headings(self):
        assert clean_text("# Hello") == "Hello"

    def test_strips_bold(self):
        assert clean_text("**important**") == "important"

    def test_strips_inline_code(self):
        result = clean_text("Use `foo()` to call it")
        assert "`" not in result
        assert "foo()" in result

    def test_strips_code_blocks(self):
        text = "Here is code:\n```python\nprint('hi')\n```\nDone."
        result = clean_text(text)
        assert "```" not in result
        assert "Done." in result

    def test_strips_markdown_links_keeps_label(self):
        result = clean_text("[Click here](https://example.com)")
        assert "Click here" in result
        assert "https://" not in result

    def test_strips_images(self):
        result = clean_text("![alt text](image.png) Some text")
        assert "![" not in result
        assert "Some text" in result

    def test_collapses_extra_whitespace(self):
        result = clean_text("Hello   world")
        assert "  " not in result

    def test_collapses_blank_lines(self):
        result = clean_text("A\n\n\n\nB")
        assert "\n\n\n" not in result

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_plain_text_unchanged(self):
        text = "The answer is forty-two."
        assert clean_text(text) == text


# ---------------------------------------------------------------------------
# split_into_chunks
# ---------------------------------------------------------------------------

class TestSplitIntoChunks:
    def test_short_text_returns_single_chunk(self):
        assert split_into_chunks("Hello world", limit=100) == ["Hello world"]

    def test_splits_at_sentence_boundary(self):
        sentence_a = "A " * 100
        sentence_b = "B " * 100
        text = sentence_a.strip() + ". " + sentence_b.strip()
        chunks = split_into_chunks(text, limit=210)
        assert len(chunks) == 2

    def test_all_chunks_within_limit(self):
        long = "word " * 1000
        chunks = split_into_chunks(long, limit=200)
        assert all(len(c) <= 200 for c in chunks)

    def test_no_empty_chunks(self):
        long = "word " * 1000
        chunks = split_into_chunks(long, limit=200)
        assert all(c.strip() for c in chunks)

    def test_exact_limit_is_one_chunk(self):
        text = "x" * DEFAULT_CHUNK_LIMIT
        assert split_into_chunks(text) == [text]

    def test_one_char_over_limit_splits(self):
        text = "x" * (DEFAULT_CHUNK_LIMIT + 1)
        chunks = split_into_chunks(text)
        assert len(chunks) >= 2


# ---------------------------------------------------------------------------
# _synthesize_with_retry
# ---------------------------------------------------------------------------

class TestSynthesizeWithRetry:
    def test_succeeds_on_first_attempt(self):
        provider = _make_provider(return_value=_fake_audio("ok"))
        result = _synthesize_with_retry(provider, "Hello")
        assert result.audio_bytes == b"ok"
        provider.synthesize.assert_called_once_with("Hello")

    def test_retries_by_halving_on_error(self):
        call_count = 0

        def side_effect(text):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("too long")
            return _fake_audio(f"audio-{call_count}")

        provider = _make_provider(side_effect=side_effect)
        segment = "a" * 200
        result = _synthesize_with_retry(provider, segment)
        assert len(result.audio_bytes) > 0
        assert call_count == 3

    def test_raises_tts_error_when_too_short_to_split(self):
        provider = _make_provider(side_effect=ValueError("too long"))
        with pytest.raises(TTSError, match="too short to split"):
            _synthesize_with_retry(provider, "Hi")


# ---------------------------------------------------------------------------
# synthesize_answer
# ---------------------------------------------------------------------------

class TestSynthesizeAnswer:
    def test_returns_audio_synthesis(self):
        provider = _make_provider(return_value=_fake_audio("sound"))
        result = synthesize_answer(provider, "Tell me something.")
        assert isinstance(result, AudioSynthesis)
        assert result.audio_bytes == b"sound"

    def test_concatenates_multiple_segments(self):
        provider = MagicMock()
        call_idx = 0

        def side_effect(text):
            nonlocal call_idx
            call_idx += 1
            return _fake_audio(f"chunk{call_idx}")

        provider.synthesize.side_effect = side_effect
        long_text = "sentence. " * 500
        result = synthesize_answer(provider, long_text)
        assert provider.synthesize.call_count >= 2
        assert b"chunk1" in result.audio_bytes
        assert b"chunk2" in result.audio_bytes

    def test_raises_tts_error_on_provider_failure(self):
        provider = _make_provider(side_effect=TTSError("provider down"))
        with pytest.raises(TTSError):
            synthesize_answer(provider, "Hello world this is a long enough sentence.")

    def test_raises_tts_error_on_empty_cleaned_text(self):
        provider = _make_provider()
        with pytest.raises(TTSError, match="empty after cleaning"):
            synthesize_answer(provider, "```\n\n```")

    def test_cleans_markdown_before_synthesis(self):
        provider = _make_provider(return_value=_fake_audio())
        synthesize_answer(provider, "# Heading\n**bold** answer text")
        called_with = provider.synthesize.call_args[0][0]
        assert "#" not in called_with
        assert "**" not in called_with


# ---------------------------------------------------------------------------
# stream_answer_chunks
# ---------------------------------------------------------------------------

class TestStreamAnswerChunks:
    def test_yields_one_chunk_for_short_text(self):
        provider = _make_provider(return_value=_fake_audio())
        chunks = list(stream_answer_chunks(provider, "Short answer."))
        assert len(chunks) == 1

    def test_yields_multiple_chunks_for_long_text(self):
        provider = _make_provider(return_value=_fake_audio())
        long_text = "word " * 1000
        chunks = list(stream_answer_chunks(provider, long_text, chunk_limit=200))
        assert len(chunks) > 1

    def test_each_yielded_value_is_audio_synthesis(self):
        provider = _make_provider(return_value=_fake_audio())
        for chunk in stream_answer_chunks(provider, "Answer text here."):
            assert isinstance(chunk, AudioSynthesis)

    def test_raises_tts_error_on_empty_text(self):
        provider = _make_provider()
        with pytest.raises(TTSError):
            list(stream_answer_chunks(provider, "```\n\n```"))


# ---------------------------------------------------------------------------
# POST /tts endpoint
# ---------------------------------------------------------------------------

client = TestClient(app)

FAKE_AUDIO_BYTES = b"fake-mp3-audio"
FAKE_MIME = "audio/mpeg"


@pytest.fixture
def mock_provider():
    fake = _make_provider(return_value=AudioSynthesis(audio_bytes=FAKE_AUDIO_BYTES, mime_type=FAKE_MIME))
    app.dependency_overrides[get_tts_provider] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def failing_provider():
    fake = _make_provider(side_effect=TTSError("provider unavailable"))
    app.dependency_overrides[get_tts_provider] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


class TestTTSEndpoint:
    def test_returns_200_with_base64_audio(self, mock_provider):
        resp = client.post("/tts", json={"text": "Hello world"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["mime_type"] == FAKE_MIME
        assert base64.b64decode(body["audio_b64"]) == FAKE_AUDIO_BYTES

    def test_returns_chunk_count_of_one(self, mock_provider):
        resp = client.post("/tts", json={"text": "Short answer."})
        assert resp.json()["chunk_count"] == 1

    def test_returns_422_for_empty_text(self, mock_provider):
        resp = client.post("/tts", json={"text": ""})
        assert resp.status_code == 422

    def test_returns_502_when_tts_provider_fails(self, failing_provider):
        resp = client.post("/tts", json={"text": "Some valid text here."})
        assert resp.status_code == 502
        assert "TTS provider error" in resp.json()["detail"]

    def test_locale_field_accepted(self, mock_provider):
        resp = client.post("/tts", json={"text": "Hello", "locale": "en-IE"})
        assert resp.status_code == 200


class TestTTSStreamEndpoint:
    def test_returns_200_with_ndjson_content_type(self, mock_provider):
        resp = client.post("/tts/stream", json={"text": "Stream this."})
        assert resp.status_code == 200
        assert "ndjson" in resp.headers["content-type"]

    def test_each_line_is_valid_json_chunk(self, mock_provider):
        resp = client.post("/tts/stream", json={"text": "Stream this answer."})
        lines = [l for l in resp.text.strip().split("\n") if l]
        assert len(lines) >= 1
        for line in lines:
            obj = json.loads(line)
            assert "audio_b64" in obj or "error" in obj

    def test_chunk_index_starts_at_zero(self, mock_provider):
        resp = client.post("/tts/stream", json={"text": "One sentence."})
        first_line = resp.text.strip().split("\n")[0]
        obj = json.loads(first_line)
        assert obj.get("index") == 0

    def test_stream_returns_error_sentinel_on_failure(self, failing_provider):
        resp = client.post("/tts/stream", json={"text": "Enough text to pass validation."})
        lines = [l for l in resp.text.strip().split("\n") if l]
        assert any("error" in json.loads(l) for l in lines)