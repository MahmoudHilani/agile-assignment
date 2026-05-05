"""Company document service — single source of truth.

Responsibilities
----------------
1. Storage  – keep exactly one canonical document on disk.
2. Indexing – parse -> chunk -> embed -> upsert into the vector store.
3. Replacement – atomically swap the stored file and re-index.
4. Validation – reject empty, oversized, or unsupported files early.
5. Startup – if a document already exists on disk, index it automatically.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import get_settings
from app.services.chunker import chunk_text
from app.services.document_parser import SUPPORTED_EXTENSIONS, parse_document
from app.services.embeddings import HashEmbeddingProvider
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS: frozenset[str] = frozenset(SUPPORTED_EXTENSIONS)
MAX_FILE_BYTES: int = 10 * 1024 * 1024  # 10 MB

_embedder = HashEmbeddingProvider()


# ── validation ────────────────────────────────────────────────────────────────

def validate_filename(filename: str) -> None:
    """Raise ValueError if filename is unsafe or has an unsupported extension."""
    path = Path(filename)
    if path.name != filename:
        raise ValueError("Filename must not include path separators")
    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported format '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def validate_size(content: bytes) -> None:
    """Raise ValueError if content exceeds the maximum allowed size."""
    if len(content) > MAX_FILE_BYTES:
        raise ValueError(
            f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MB limit"
        )


# ── storage ───────────────────────────────────────────────────────────────────

def _storage_dir() -> Path:
    settings = get_settings()
    storage = Path(settings.document_storage_path)
    storage.mkdir(parents=True, exist_ok=True)
    return storage


def _get_canonical_path() -> Path | None:
    """Return the path of the current canonical document, or None."""
    storage = _storage_dir()
    files = [f for f in storage.iterdir() if f.is_file()]
    return files[0] if files else None


def _save_document(filename: str, content: bytes) -> Path:
    """Atomically replace any existing document with the new file."""
    storage = _storage_dir()
    for existing in storage.iterdir():
        if existing.is_file():
            existing.unlink()
    dest = storage / filename
    dest.write_bytes(content)
    logger.info("Saved canonical document: %s (%d bytes)", filename, len(content))
    return dest


# ── indexing pipeline ─────────────────────────────────────────────────────────

def _run_indexing(doc_path: Path) -> int:
    """Parse -> chunk -> embed -> store. Returns chunk count."""
    settings = get_settings()

    logger.info("Parsing document: %s", doc_path.name)
    text = parse_document(doc_path)

    logger.info(
        "Chunking document (chunk_size=%d, overlap=%d)",
        settings.chunk_size,
        settings.chunk_overlap,
    )
    chunks = chunk_text(
        text,
        source_name=doc_path.name,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    logger.info("Embedding %d chunks", len(chunks))
    vectors = _embedder.embed_texts([c.text for c in chunks])

    store = get_vector_store()
    store.upsert(chunks, vectors)
    logger.info("Indexed %d chunks into vector store", len(chunks))
    return len(chunks)


# ── public API ────────────────────────────────────────────────────────────────

def replace_document(filename: str, content: bytes) -> None:
    """Persist content as the new canonical document (does NOT re-index)."""
    _save_document(filename, content)


def reindex_document(filename: str) -> int:
    """Re-index the document currently stored under filename.

    Returns the number of chunks written to the vector store.

    Raises
    ------
    FileNotFoundError
        If no stored document matches filename.
    """
    doc_path = _storage_dir() / filename
    if not doc_path.exists():
        raise FileNotFoundError(
            f"Document '{filename}' not found in storage. "
            "Upload it first via PUT /documents."
        )
    return _run_indexing(doc_path)


def index_startup_document() -> None:
    """Index the canonical document present on disk at application startup.

    Called from the FastAPI lifespan handler. No-op if no document exists.
    """
    doc_path = _get_canonical_path()
    if doc_path is None:
        logger.info("No startup document found — vector store is empty.")
        return
    try:
        count = _run_indexing(doc_path)
        logger.info(
            "Startup indexing complete: %d chunks from '%s'", count, doc_path.name
        )
    except Exception:
        logger.exception("Startup indexing failed for '%s'", doc_path.name)