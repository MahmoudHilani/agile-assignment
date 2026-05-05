from collections.abc import Sequence
from typing import Protocol

from app.domain.models import (
    AudioSynthesis,
    AudioTranscription,
    ChatTurn,
    DocumentChunk,
    SearchResult,
)


class DocumentProcessor(Protocol):
    def process(self, source_name: str, content: bytes) -> Sequence[DocumentChunk]: ...


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: Sequence[str], mode: str = "document") -> Sequence[list[float]]: ...


class VectorStore(Protocol):
    def upsert(self, chunks: Sequence[DocumentChunk], vectors: Sequence[list[float]]) -> None: ...

    def search(self, query_vector: list[float], top_k: int) -> Sequence[SearchResult]: ...


class ChatProvider(Protocol):
    def generate(self, prompt: str, context: Sequence[SearchResult], history: Sequence[ChatTurn]) -> str: ...


class SpeechToTextProvider(Protocol):
    def transcribe(self, audio_bytes: bytes) -> AudioTranscription: ...


class TextToSpeechProvider(Protocol):
    def synthesize(self, text: str) -> AudioSynthesis: ...
