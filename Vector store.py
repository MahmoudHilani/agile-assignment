"""Thread-safe in-memory vector store.

This implementation keeps all vectors in a plain Python list, which is suitable
for a single-document knowledge base of up to tens of thousands of chunks.
Swap this out for a proper vector database (Pinecone, Qdrant, ChromaDB, etc.)
by implementing the VectorStore protocol in interfaces.py.

Similarity metric: cosine similarity.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Sequence

from app.domain.models import DocumentChunk, SearchResult


class InMemoryVectorStore:
    """Stores (chunk, vector) pairs and supports cosine-similarity search."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._chunks: list[DocumentChunk] = []
        self._vectors: list[list[float]] = []

    def upsert(
        self,
        chunks: Sequence[DocumentChunk],
        vectors: Sequence[list[float]],
    ) -> None:
        """Replace the entire store with *chunks* and their corresponding *vectors*."""
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        with self._lock:
            self._chunks = list(chunks)
            self._vectors = [list(v) for v in vectors]

    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]:
        """Return the *top_k* most similar chunks by cosine similarity."""
        with self._lock:
            if not self._chunks:
                return []
            scored = [
                (self._cosine(query_vector, v), chunk)
                for chunk, v in zip(self._chunks, self._vectors)
            ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchResult(
                chunk_id=chunk.id,
                score=round(score, 6),
                text=chunk.text,
                metadata=chunk.metadata,
            )
            for score, chunk in scored[:top_k]
        ]

    def clear(self) -> None:
        """Remove all stored data."""
        with self._lock:
            self._chunks = []
            self._vectors = []

    @property
    def chunk_count(self) -> int:
        with self._lock:
            return len(self._chunks)

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)


# Module-level singleton replaced on each document upload
_store = InMemoryVectorStore()


def get_vector_store() -> InMemoryVectorStore:
    """Return the application-wide vector store singleton."""
    return _store