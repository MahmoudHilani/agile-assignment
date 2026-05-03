from pydantic import BaseModel


class VoiceSessionRequest(BaseModel):
    session_id: str | None = None
    locale: str | None = None


class VoiceSessionResponse(BaseModel):
    status: str
    message: str


class VoiceTranscriptionResponse(BaseModel):
    text: str

class TTSRequest(BaseModel):
    text: str

class TTSResponse(BaseModel):
    mime_type: str
    audio_b64: str
    chunk_count: int

class TTSChunk(BaseModel):
    index: int
    mime_type: str
    audio_b64: str