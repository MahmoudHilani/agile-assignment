from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket, status

from app.core.responses import not_implemented_error
from app.schemas.voice import VoiceTranscriptionResponse
from app.services.speech_to_text_service import transcribe_audio

router = APIRouter(tags=["voice"])


@router.post(
    "/voice",
    response_model=VoiceTranscriptionResponse,
    status_code=status.HTTP_200_OK,
)
async def transcribe_voice(
    audio: UploadFile = File(...),
    locale: str = Form(default="en-US"),
) -> VoiceTranscriptionResponse:
    audio_bytes = await audio.read()

    try:
        text = transcribe_audio(audio_bytes, language=locale or "en-US")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return VoiceTranscriptionResponse(text=text)


@router.websocket("/voice")
async def voice_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json(not_implemented_error("Realtime voice transport").model_dump())
    await websocket.close(code=1011, reason="Not implemented")
