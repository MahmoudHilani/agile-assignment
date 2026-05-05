from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DocumentChunk:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SearchResult:
    chunk_id: str
    score: float
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatTurn:
    role: str
    content: str


@dataclass(slots=True)
class AudioTranscription:
    text: str
    locale: str | None = None


@dataclass(slots=True)
class AudioSynthesis:
    audio_bytes: bytes
    mime_type: str
