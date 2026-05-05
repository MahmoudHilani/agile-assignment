"""Tests for the company document management feature.

Covers
------
* Validation: empty, oversized, bad extension, path traversal
* Auth: unauthenticated (401) and non-admin (403) requests
* Happy path: replace + index via PUT /documents
* Startup indexing: index_startup_document() on first boot
* Re-indexing: vector store is refreshed after document replacement
* Vector store: upsert / search / clear
* Chunker: basic chunking, overlap, empty input
* Parser: .txt parsing (inline), unsupported extension error
"""

from __future__ import annotations

import io
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.domain.models import DocumentChunk
from app.main import app
from app.services.chunker import chunk_text
from app.services.document_parser import parse_document
from app.services.document_service import (
    MAX_FILE_BYTES,
    index_startup_document,
    reindex_document,
    replace_document,
    validate_filename,
    validate_size,
)
from app.services.embeddings import HashEmbeddingProvider
from app.services.vector_store import InMemoryVectorStore

client = TestClient(app)


# ── helpers ───────────────────────────────────────────────────────────────────


def make_token(role: str) -> str:
    return create_access_token({"sub": "test-user", "role": role})


def _txt_file(content: bytes = b"hello world", name: str = "doc.txt") -> dict:
    return {"file": (name, io.BytesIO(content), "text/plain")}


def _patch_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect all storage calls to a temporary directory."""
    monkeypatch.setattr(
        "app.services.document_service.get_settings",
        lambda: _MockSettings(tmp_path),
    )


class _MockSettings:
    def __init__(self, tmp_path: Path) -> None:
        from app.core.config import get_settings
        base = get_settings()
        self.secret_key = base.secret_key
        self.algorithm = base.algorithm
        self.access_token_expire_minutes = base.access_token_expire_minutes
        self.document_storage_path = str(tmp_path)
        self.chunk_size = 200
        self.chunk_overlap = 20


# ═══════════════════════════════════════════════════════════════════════════════
# 1. VALIDATION UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateFilename:
    def test_valid_txt(self) -> None:
        validate_filename("report.txt")  # must not raise

    def test_valid_pdf(self) -> None:
        validate_filename("company_info.pdf")

    def test_valid_docx(self) -> None:
        validate_filename("handbook.docx")

    def test_rejects_path_traversal(self) -> None:
        with pytest.raises(ValueError, match="path separators"):
            validate_filename("../secret.txt")

    def test_rejects_unsupported_extension(self) -> None:
        with pytest.raises(ValueError, match="Unsupported format"):
            validate_filename("virus.exe")

    def test_rejects_no_extension(self) -> None:
        with pytest.raises(ValueError, match="Unsupported format"):
            validate_filename("README")


class TestValidateSize:
    def test_accepts_within_limit(self) -> None:
        validate_size(b"x" * 100)  # must not raise

    def test_rejects_oversized(self) -> None:
        with pytest.raises(ValueError, match="MB limit"):
            validate_size(b"x" * (MAX_FILE_BYTES + 1))

    def test_accepts_exactly_at_limit(self) -> None:
        validate_size(b"x" * MAX_FILE_BYTES)  # must not raise


# ═══════════════════════════════════════════════════════════════════════════════
# 2. AUTHENTICATION / AUTHORISATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestReplaceAuth:
    def test_no_auth_returns_401(self) -> None:
        response = client.put("/documents", files=_txt_file())
        assert response.status_code == 401

    def test_non_admin_returns_403(self) -> None:
        token = make_token("User")
        response = client.put(
            "/documents",
            files=_txt_file(),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 3. REPLACE ENDPOINT — HTTP-LEVEL TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestReplaceEndpoint:
    def _admin_headers(self) -> dict:
        return {"Authorization": f"Bearer {make_token('Admin')}"}

    def test_valid_txt_returns_200(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_storage(monkeypatch, tmp_path)
        response = client.put(
            "/documents",
            files=_txt_file(b"Company overview text here."),
            headers=self._admin_headers(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["accepted"] is True
        assert body["filename"] == "doc.txt"
        assert "chunk" in body["message"]

    def test_empty_file_returns_422(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_storage(monkeypatch, tmp_path)
        response = client.put(
            "/documents",
            files=_txt_file(b""),
            headers=self._admin_headers(),
        )
        assert response.status_code == 422

    def test_oversized_file_returns_422(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_storage(monkeypatch, tmp_path)
        response = client.put(
            "/documents",
            files=_txt_file(b"x" * (MAX_FILE_BYTES + 1)),
            headers=self._admin_headers(),
        )
        assert response.status_code == 422

    def test_invalid_extension_returns_422(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_storage(monkeypatch, tmp_path)
        response = client.put(
            "/documents",
            files={"file": ("bad.exe", io.BytesIO(b"bad"), "application/octet-stream")},
            headers=self._admin_headers(),
        )
        assert response.status_code == 422

    def test_path_traversal_returns_422(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_storage(monkeypatch, tmp_path)
        response = client.put(
            "/documents",
            files={"file": ("../escape.txt", io.BytesIO(b"data"), "text/plain")},
            headers=self._admin_headers(),
        )
        assert response.status_code == 422
        assert not (tmp_path.parent / "escape.txt").exists()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. REPLACE + RE-INDEX SERVICE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestReplaceAndReindex:
    def test_replace_stores_exactly_one_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_storage(monkeypatch, tmp_path)
        replace_document("first.txt", b"first document content")
        replace_document("second.txt", b"second document content")
        stored = list(tmp_path.iterdir())
        assert len(stored) == 1
        assert stored[0].name == "second.txt"

    def test_reindex_populates_vector_store(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_storage(monkeypatch, tmp_path)
        content = b"The company was founded in 2010. We build great software."
        replace_document("info.txt", content)

        store = InMemoryVectorStore()
        monkeypatch.setattr("app.services.document_service.get_vector_store", lambda: store)

        count = reindex_document("info.txt")
        assert count > 0
        assert store.chunk_count == count

    def test_reindex_missing_file_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_storage(monkeypatch, tmp_path)
        with pytest.raises(FileNotFoundError):
            reindex_document("ghost.txt")

    def test_replacement_refreshes_vector_store(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After replacement, the store should reflect the NEW document."""
        _patch_storage(monkeypatch, tmp_path)
        store = InMemoryVectorStore()
        monkeypatch.setattr("app.services.document_service.get_vector_store", lambda: store)

        # Index first document
        replace_document("v1.txt", b"Original company policy document content here.")
        reindex_document("v1.txt")
        first_count = store.chunk_count

        # Replace with second document (different content, different filename)
        replace_document("v2.txt", b"Updated company policy with many more details added.")
        reindex_document("v2.txt")
        second_count = store.chunk_count

        # Store must have been fully replaced (not appended to)
        assert second_count > 0
        # All chunks must reference v2 not v1
        with store._lock:
            sources = {c.metadata["source"] for c in store._chunks}
        assert sources == {"v2.txt"}
        assert "v1.txt" not in sources

    def test_reindex_updates_chunk_metadata_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_storage(monkeypatch, tmp_path)
        store = InMemoryVectorStore()
        monkeypatch.setattr("app.services.document_service.get_vector_store", lambda: store)

        replace_document("handbook.txt", b"Employee handbook content for the company.")
        reindex_document("handbook.txt")

        with store._lock:
            for chunk in store._chunks:
                assert chunk.metadata["source"] == "handbook.txt"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. STARTUP INDEXING
# ═══════════════════════════════════════════════════════════════════════════════


class TestStartupIndexing:
    def test_startup_indexes_existing_document(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_storage(monkeypatch, tmp_path)
        # Pre-place a document in the storage directory
        (tmp_path / "company.txt").write_text(
            "Acme Corp was founded in 1985. We make everything.", encoding="utf-8"
        )
        store = InMemoryVectorStore()
        monkeypatch.setattr("app.services.document_service.get_vector_store", lambda: store)

        index_startup_document()

        assert store.chunk_count > 0

    def test_startup_noop_when_no_document(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_storage(monkeypatch, tmp_path)
        store = InMemoryVectorStore()
        monkeypatch.setattr("app.services.document_service.get_vector_store", lambda: store)

        index_startup_document()  # must not raise

        assert store.chunk_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 6. VECTOR STORE UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestInMemoryVectorStore:
    def _make_chunk(self, idx: int, text: str = "chunk text") -> DocumentChunk:
        return DocumentChunk(id=f"chunk-{idx}", text=text, metadata={"chunk_index": idx})

    def test_upsert_and_search_basic(self) -> None:
        store = InMemoryVectorStore()
        chunks = [self._make_chunk(i) for i in range(3)]
        vectors = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
        store.upsert(chunks, vectors)

        results = store.search([1.0, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0].chunk_id == "chunk-0"

    def test_upsert_replaces_previous_contents(self) -> None:
        store = InMemoryVectorStore()
        store.upsert([self._make_chunk(0)], [[1.0, 0.0]])
        store.upsert([self._make_chunk(1), self._make_chunk(2)], [[0.0, 1.0], [1.0, 0.0]])
        assert store.chunk_count == 2

    def test_search_empty_store_returns_empty(self) -> None:
        store = InMemoryVectorStore()
        assert store.search([1.0, 0.0]) == []

    def test_clear_empties_store(self) -> None:
        store = InMemoryVectorStore()
        store.upsert([self._make_chunk(0)], [[1.0, 0.0]])
        store.clear()
        assert store.chunk_count == 0

    def test_upsert_mismatched_lengths_raises(self) -> None:
        store = InMemoryVectorStore()
        with pytest.raises(ValueError):
            store.upsert([self._make_chunk(0)], [[1.0], [0.0]])

    def test_cosine_identical_vectors(self) -> None:
        score = InMemoryVectorStore._cosine([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        assert math.isclose(score, 1.0, rel_tol=1e-6)

    def test_cosine_orthogonal_vectors(self) -> None:
        score = InMemoryVectorStore._cosine([1.0, 0.0], [0.0, 1.0])
        assert math.isclose(score, 0.0, abs_tol=1e-9)

    def test_cosine_zero_vector(self) -> None:
        score = InMemoryVectorStore._cosine([0.0, 0.0], [1.0, 0.0])
        assert score == 0.0

    def test_search_respects_top_k(self) -> None:
        store = InMemoryVectorStore()
        chunks = [self._make_chunk(i) for i in range(10)]
        vectors = [[float(i), 0.0] for i in range(10)]
        store.upsert(chunks, vectors)
        results = store.search([1.0, 0.0], top_k=3)
        assert len(results) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 7. CHUNKER UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestChunker:
    def test_short_text_produces_one_chunk(self) -> None:
        chunks = chunk_text("Hello world.", "test.txt", chunk_size=500)
        assert len(chunks) >= 1
        assert chunks[0].text == "Hello world."

    def test_chunks_respect_chunk_size(self) -> None:
        long_text = " ".join(["word"] * 500)
        chunks = chunk_text(long_text, "test.txt", chunk_size=100)
        for chunk in chunks:
            assert len(chunk.text) <= 150  # allow slight overhead at merge boundary

    def test_chunk_metadata_source(self) -> None:
        chunks = chunk_text("Some text content.", "myfile.txt")
        assert all(c.metadata["source"] == "myfile.txt" for c in chunks)

    def test_chunk_metadata_index_sequential(self) -> None:
        text = "\n\n".join([f"Paragraph {i}." for i in range(10)])
        chunks = chunk_text(text, "test.txt", chunk_size=50)
        indices = [c.metadata["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_empty_text_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            chunk_text("   ", "test.txt")

    def test_invalid_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_size"):
            chunk_text("Some text.", "test.txt", chunk_size=0)

    def test_chunks_cover_all_text(self) -> None:
        """Every word in the source must appear in at least one chunk."""
        original = "The quick brown fox jumps over the lazy dog."
        chunks = chunk_text(original, "test.txt", chunk_size=20, chunk_overlap=5)
        combined = " ".join(c.text for c in chunks)
        for word in original.split():
            assert word in combined

    def test_chunk_ids_are_unique(self) -> None:
        text = "\n\n".join([f"Section {i} with some content." for i in range(20)])
        chunks = chunk_text(text, "test.txt", chunk_size=50)
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))


# ═══════════════════════════════════════════════════════════════════════════════
# 8. DOCUMENT PARSER UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDocumentParser:
    def test_parse_txt(self, tmp_path: Path) -> None:
        doc = tmp_path / "sample.txt"
        doc.write_text("This is a test document.", encoding="utf-8")
        text = parse_document(doc)
        assert "test document" in text

    def test_parse_unsupported_raises(self, tmp_path: Path) -> None:
        doc = tmp_path / "file.csv"
        doc.write_text("a,b,c")
        with pytest.raises(ValueError, match="Unsupported format"):
            parse_document(doc)

    def test_parse_empty_txt_raises(self, tmp_path: Path) -> None:
        doc = tmp_path / "empty.txt"
        doc.write_text("   \n  ", encoding="utf-8")
        with pytest.raises(ValueError, match="no extractable text"):
            parse_document(doc)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. EMBEDDING UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestHashEmbeddingProvider:
    def test_embed_returns_correct_count(self) -> None:
        provider = HashEmbeddingProvider(dims=64)
        texts = ["hello world", "foo bar", "baz"]
        vectors = provider.embed_texts(texts)
        assert len(vectors) == 3

    def test_embed_returns_correct_dims(self) -> None:
        provider = HashEmbeddingProvider(dims=32)
        vectors = provider.embed_texts(["test"])
        assert len(vectors[0]) == 32

    def test_embed_is_deterministic(self) -> None:
        provider = HashEmbeddingProvider(dims=64)
        v1 = provider.embed_texts(["hello world"])
        v2 = provider.embed_texts(["hello world"])
        assert v1 == v2

    def test_different_texts_produce_different_vectors(self) -> None:
        provider = HashEmbeddingProvider(dims=64)
        v1 = provider.embed_texts(["company overview"])[0]
        v2 = provider.embed_texts(["unrelated content"])[0]
        assert v1 != v2

    def test_vectors_are_unit_normalised(self) -> None:
        provider = HashEmbeddingProvider(dims=64)
        vec = provider.embed_texts(["normalisation test"])[0]
        norm = math.sqrt(sum(x * x for x in vec))
        assert math.isclose(norm, 1.0, rel_tol=1e-5)