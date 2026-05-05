from pydantic import BaseModel, Field


class VoiceSessionRequest(BaseModel):
    session_id: str | None = None
    locale: str | None = None


class VoiceSessionResponse(BaseModel):
    status: str
    message: str


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Answer text to synthesize")
    locale: str | None = Field(default=None, description="BCP-47 locale tag, e.g. 'en-US'")
    streamed: bool = Field(
        default=False,
        description="Return chunked audio instead of a single response",
    )


class TTSChunk(BaseModel):
    index: int
    mime_type: str
    audio_b64: str = Field(description="Base-64-encoded audio bytes for this chunk")


class TTSResponse(BaseModel):
    mime_type: str
    audio_b64: str = Field(description="Base-64-encoded audio bytes for the complete response")
    chunk_count: int = Field(default=1)