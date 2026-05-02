from __future__ import annotations

import base64
import logging
import os
import requests

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, WebSocket, status
from fastapi.responses import StreamingResponse

from app.core.responses import not_implemented_error
from app.schemas.common import ApiError
from app.schemas.voice import (
    TTSChunk,
    TTSRequest,
    TTSResponse,
    VoiceSessionRequest,
)
from app.services.interfaces import TextToSpeechProvider
from app.services.tts import TTSError, stream_answer_chunks, synthesize_answer

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])


def get_answer_from_llm(question: str) -> str:
    ollama_url = os.getenv("OLLAMA_URL", "https://nebiakay-llama-backend.hf.space/api/generate")
    model_name = os.getenv("MODEL_NAME", "llama3.2:1b")
    response = requests.post(
        ollama_url,
        headers={"Content-Type": "application/json"},
        json={
            "model": model_name,
            "prompt": f"Answer in 2 sentences only: {question}",
            "stream": False
        }
    )
    data = response.json()
    print("LLM response:", data)
    if "response" not in data:
        raise Exception(f"LLM API error: {data}")
    return data["response"]


def stream_answer_from_llm(question: str):
    ollama_url = os.getenv("OLLAMA_URL", "https://nebiakay-llama-backend.hf.space/api/generate")
    model_name = os.getenv("MODEL_NAME", "llama3.2:1b")
    response = requests.post(
        ollama_url,
        headers={"Content-Type": "application/json"},
        json={
            "model": model_name,
            "prompt": f"Answer in 2 sentences only: {question}",
            "stream": True
        },
        stream=True
    )

    buffer = ""
    for line in response.iter_lines():
        if line:
            try:
                import json
                data = json.loads(line.decode("utf-8"))
                token = data.get("response", "")
                if token:
                    buffer += token
                    if any(p in buffer for p in [".", "!", "?"]):
                        yield buffer.strip()
                        buffer = ""
                if data.get("done"):
                    break
            except Exception:
                continue

    if buffer.strip():
        yield buffer.strip()


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
    summary="Synthesise answer text to audio (single response)",
)
def synthesize_tts(
    body: TTSRequest,
    provider: TextToSpeechProvider = Depends(get_tts_provider),
) -> TTSResponse:
    try:
        result = synthesize_answer(provider, body.text)
    except TTSError as exc:
        logger.error("TTS synthesis failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS provider error: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected TTS error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error during speech synthesis.",
        ) from exc

    return TTSResponse(
        mime_type=result.mime_type,
        audio_b64=base64.b64encode(result.audio_bytes).decode(),
        chunk_count=1,
    )


@router.post(
    "/tts/stream",
    summary="Synthesise answer text to audio (streamed chunks)",
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
        except TTSError as exc:
            logger.error("TTS stream error: %s", exc)
            yield f'{{"error": "{exc}"}}\n'
        except Exception:
            logger.exception("Unexpected TTS stream error")
            yield '{"error": "Unexpected error during speech synthesis."}\n'

    return StreamingResponse(
        _generate(),
        media_type="application/x-ndjson",
    )


@router.post(
    "/ask",
    response_model=TTSResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question and get audio response from team LLM",
)
def ask_and_speak(
    body: TTSRequest,
    provider: TextToSpeechProvider = Depends(get_tts_provider),
) -> TTSResponse:
    try:
        answer = get_answer_from_llm(body.text)
        result = synthesize_answer(provider, answer)
    except TTSError as exc:
        logger.error("TTS synthesis failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS provider error: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error.",
        ) from exc

    return TTSResponse(
        mime_type=result.mime_type,
        audio_b64=base64.b64encode(result.audio_bytes).decode(),
        chunk_count=1,
    )


@router.post(
    "/ask/stream",
    summary="Ask a question and get streamed audio response from team LLM",
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
            logger.exception("Unexpected TTS stream error")
            yield '{"error": "Unexpected error."}\n'

    return StreamingResponse(
        _generate(),
        media_type="application/x-ndjson",
    )


@router.post(
    "/voice",
    response_model=ApiError,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def create_voice_session(_: VoiceSessionRequest) -> ApiError:
    return not_implemented_error("Voice session creation")


@router.websocket("/voice/ws")
async def voice_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json(not_implemented_error("Realtime voice transport").model_dump())
    await websocket.close(code=1011, reason="Not implemented")