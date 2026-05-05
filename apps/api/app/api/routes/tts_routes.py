from __future__ import annotations

import asyncio
import base64
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas.voice import TTSChunk, TTSRequest, TTSResponse
from app.services.query_service import run_rag_query, run_rag_query_stream
from app.services.interfaces import TextToSpeechProvider
from app.services.tts import TTSError, stream_answer_chunks, synthesize_answer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tts"])


def get_answer_from_llm(question: str) -> str:
    answer, _sources = run_rag_query(question, top_k=5)
    return answer


def stream_answer_from_llm(question: str):
    async def _collect_chunks() -> list[str]:
        return [chunk async for chunk in run_rag_query_stream(question, top_k=5)]

    for chunk in asyncio.run(_collect_chunks()):
        if chunk.strip():
            yield chunk


def get_tts_provider() -> TextToSpeechProvider:
    from gtts import gTTS
    import io
    from app.domain.models import AudioSynthesis

    class GTTSProvider:
        def synthesize(self, text: str) -> AudioSynthesis:
            buf = io.BytesIO()
            gTTS(text=text, lang="en", slow=False).write_to_fp(buf)
            buf.seek(0)
            return AudioSynthesis(audio_bytes=buf.read(), mime_type="audio/mpeg")

    return GTTSProvider()


@router.post(
    "/tts",
    response_model=TTSResponse,
    status_code=status.HTTP_200_OK,
    summary="Synthesise text to audio (single response)",
)
def synthesize_tts(
    body: TTSRequest,
    provider: TextToSpeechProvider = Depends(get_tts_provider),
) -> TTSResponse:
    try:
        result = synthesize_answer(provider, body.text)
    except TTSError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"TTS provider error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error.") from exc
    return TTSResponse(
        mime_type=result.mime_type,
        audio_b64=base64.b64encode(result.audio_bytes).decode(),
        chunk_count=1,
    )


@router.post(
    "/tts/stream",
    summary="Synthesise text to audio (streamed chunks)",
    response_class=StreamingResponse,
)
def synthesize_tts_stream(
    body: TTSRequest,
    provider: TextToSpeechProvider = Depends(get_tts_provider),
) -> StreamingResponse:
    def _generate():
        try:
            for index, chunk in enumerate(stream_answer_chunks(provider, body.text)):
                tts_chunk = TTSChunk(
                    index=index,
                    mime_type=chunk.mime_type,
                    audio_b64=base64.b64encode(chunk.audio_bytes).decode(),
                )
                yield tts_chunk.model_dump_json() + "\n"
        except Exception:
            yield '{"error": "Unexpected error during speech synthesis."}\n'
    return StreamingResponse(_generate(), media_type="application/x-ndjson")


@router.post(
    "/ask",
    response_model=TTSResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask team LLM and get audio response",
)
def ask_and_speak(
    body: TTSRequest,
    provider: TextToSpeechProvider = Depends(get_tts_provider),
) -> TTSResponse:
    try:
        answer = get_answer_from_llm(body.text)
        result = synthesize_answer(provider, answer)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error.") from exc
    return TTSResponse(
        mime_type=result.mime_type,
        audio_b64=base64.b64encode(result.audio_bytes).decode(),
        chunk_count=1,
    )


@router.post(
    "/ask/stream",
    summary="Ask team LLM and get streamed audio response",
    response_class=StreamingResponse,
)
def ask_and_speak_stream(
    body: TTSRequest,
    provider: TextToSpeechProvider = Depends(get_tts_provider),
) -> StreamingResponse:
    def _generate():
        try:
            for text_chunk in stream_answer_from_llm(body.text):
                if text_chunk.strip():
                    try:
                        result = synthesize_answer(provider, text_chunk)
                        tts_chunk = TTSChunk(
                            index=0,
                            mime_type=result.mime_type,
                            audio_b64=base64.b64encode(result.audio_bytes).decode(),
                        )
                        yield tts_chunk.model_dump_json() + "\n"
                    except Exception as e:
                        logger.error("TTS chunk error: %s", e)
                        continue
        except Exception:
            yield '{"error": "Unexpected error."}\n'
    return StreamingResponse(_generate(), media_type="application/x-ndjson")
