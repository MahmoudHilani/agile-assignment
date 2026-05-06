import base64

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.voice import TTSRequest, TTSResponse
from app.services.interfaces import TextToSpeechProvider
from app.services.tts import TTSError, synthesize_answer

router = APIRouter(tags=["tts"])


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
