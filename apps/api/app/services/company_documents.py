from __future__ import annotations

import hashlib
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.core.config import Settings, get_settings
from app.domain.models import DocumentChunk, SearchResult

SUPPORTED_EXTENSIONS = {".md", ".txt"}
SUPPORTED_FORMATS = ", ".join(sorted(SUPPORTED_EXTENSIONS))
CURRENT_DOCUMENT_VERSION = "current"
EMBEDDING_DIMENSIONS = 64


class CompanyDocumentError(ValueError):
    pass


@dataclass(slots=True)
class IndexedCompanyDocument:
    source_name: str
    chunks_indexed: int


class InMemoryCompanyVectorStore:
    def __init__(self) -> None:
        self._items: list[tuple[DocumentChunk, list[float]]] = []

    def replace(self, chunks: list[DocumentChunk], vectors: list[list[float]]) -> None:
        self._items = list(zip(chunks, vectors, strict=True))

    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]:
        ranked: list[SearchResult] = []
        for chunk, vector in self._items:
            ranked.append(
                SearchResult(
                    chunk_id=chunk.id,
                    score=cosine_similarity(query_vector, vector),
                    text=chunk.text,
                    metadata=chunk.metadata,
                )
            )

        ranked.sort(key=lambda result: result.score, reverse=True)
        return ranked[:top_k]

    def clear(self) -> None:
        self._items.clear()

    @property
    def count(self) -> int:
        return len(self._items)


class CompanyDocumentService:
    def __init__(
        self,
        settings: Settings | None = None,
        vector_store: InMemoryCompanyVectorStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.vector_store = vector_store or InMemoryCompanyVectorStore()
        self.active_source_name: str | None = None

    def initialize(self) -> IndexedCompanyDocument | None:
        path = self.settings.canonical_company_document_path
        if not path.exists():
            self.active_source_name = None
            self.vector_store.clear()
            return None

        content = path.read_bytes()
        document = self._index(path.name, content)
        self.active_source_name = path.name
        return document

    def replace(self, source_name: str, content: bytes) -> IndexedCompanyDocument:
        document = self._index(source_name, content)
        self._save_canonical_document(content)
        self.active_source_name = source_name
        return document

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        if not self.active_source_name:
            raise CompanyDocumentError("No company document loaded")
        if not query.strip():
            raise CompanyDocumentError("Query cannot be empty")

        return self.vector_store.search(embed_text(query), top_k=top_k)

    def _index(self, source_name: str, content: bytes) -> IndexedCompanyDocument:
        text = parse_document(source_name, content)
        chunks = chunk_text(text)
        vectors = [embed_text(chunk) for chunk in chunks]
        document_chunks = [
            DocumentChunk(
                id=f"{CURRENT_DOCUMENT_VERSION}:{index}",
                text=chunk,
                metadata={
                    "source_name": source_name,
                    "version": CURRENT_DOCUMENT_VERSION,
                    "chunk_index": index,
                },
            )
            for index, chunk in enumerate(chunks)
        ]

        self.vector_store.replace(document_chunks, vectors)
        return IndexedCompanyDocument(source_name=source_name, chunks_indexed=len(chunks))

    def _save_canonical_document(self, content: bytes) -> None:
        target = self.settings.canonical_company_document_path
        target.parent.mkdir(parents=True, exist_ok=True)

        with NamedTemporaryFile(delete=False, dir=target.parent) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        shutil.move(str(tmp_path), target)


def parse_document(source_name: str, content: bytes) -> str:
    extension = Path(source_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise CompanyDocumentError(f"Unsupported format. Supported formats: {SUPPORTED_FORMATS}")
    if not content or not content.strip():
        raise CompanyDocumentError("Empty document")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CompanyDocumentError("Invalid document") from exc

    if not text.strip():
        raise CompanyDocumentError("Empty document")

    return text


def chunk_text(text: str, max_words: int = 120, overlap: int = 20) -> list[str]:
    if max_words <= 0:
        raise ValueError("max_words must be greater than zero")
    if overlap < 0 or overlap >= max_words:
        raise ValueError("overlap must be less than max_words")

    words = text.split()
    chunks: list[str] = []
    index = 0
    step = max_words - overlap

    while index < len(words):
        chunks.append(" ".join(words[index:index + max_words]))
        index += step

    return chunks


def embed_text(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    tokens = re.findall(r"[a-z0-9]+", text.lower())

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        vector[bucket] += 1.0

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector

    return [value / magnitude for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


company_document_service = CompanyDocumentService()
