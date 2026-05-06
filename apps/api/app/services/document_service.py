from __future__ import annotations

import io
import os
import re
import tempfile
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from app.core.config import Settings, get_settings
from app.domain.models import DocumentChunk, SearchResult
from app.services.embedding_providers import get_embedding_provider

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
PDF_CONTEXT_CHUNK_WORDS = 180
PDF_CONTEXT_CHUNK_OVERLAP = 30
PDF_CONTEXT_MAX_CHUNKS = 4
CURRENT_DOCUMENT_VERSION = "current"
_active_document_name: str | None = None
_pdf_contexts: dict[str, list[str]] = {}


class ChromaVectorStore:
    def __init__(self, path: str, collection_name: str) -> None:
        import chromadb

        Path(path).mkdir(parents=True, exist_ok=True)
        # Chroma PersistentClient stores local vector data on disk.
        # Source: https://docs.trychroma.com/reference/python/client#persistentclient
        self._client = chromadb.PersistentClient(path=path)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
        )

    def replace(self, chunks: list[DocumentChunk], vectors: list[list[float]]) -> None:
        self.clear()
        if not chunks:
            return

        # Chroma can store precomputed embeddings together with documents and metadata.
        # Source: https://docs.trychroma.com/docs/collections/add-data#adding-data
        self._collection.add(
            ids=[chunk.id for chunk in chunks],
            embeddings=vectors,
            documents=[chunk.text for chunk in chunks],
            metadatas=[chunk.metadata for chunk in chunks],
        )

    def search(self, query_vector: list[float], top_k: int) -> list[SearchResult]:
        # The query API accepts direct query embeddings when the collection has no embedding function.
        # Source: https://docs.trychroma.com/docs/querying-collections/query-and-get#query
        result = self._collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0] or []
        metadatas = result.get("metadatas", [[]])[0] or []
        distances = result.get("distances", [[]])[0] or []

        return [
            SearchResult(
                chunk_id=chunk_id,
                score=1.0 - distance,
                text=document,
                metadata=metadata or {},
            )
            for chunk_id, document, metadata, distance in zip(
                ids,
                documents,
                metadatas,
                distances,
                strict=True,
            )
        ]

    def clear(self) -> None:
        # Chroma supports deleting all records matching a metadata filter.
        # Source: https://docs.trychroma.com/docs/collections/delete-data
        self._collection.delete(where={"version": CURRENT_DOCUMENT_VERSION})

    @property
    def count(self) -> int:
        return self._collection.count()


def _vector_store(settings: Settings | None = None) -> ChromaVectorStore:
    resolved_settings = settings or get_settings()
    return ChromaVectorStore(
        path=resolved_settings.chroma_db_path,
        collection_name=resolved_settings.chroma_collection_name,
    )


def validate_filename(filename: str) -> None:
    path = Path(filename)
    if path.name != filename:
        raise ValueError("Filename must not include path separators")
    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def validate_size(content: bytes) -> None:
    if len(content) > MAX_FILE_BYTES:
        raise ValueError(f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MB limit")


def replace_document(filename: str, content: bytes) -> None:
    settings = get_settings()
    validate_filename(filename)
    validate_size(content)
    text = parse_document(filename, content)
    chunks = build_chunks(filename, text)
    vectors = get_embedding_provider(settings).embed_texts(
        [chunk.text for chunk in chunks],
        mode="document",
    )

    storage = Path(settings.document_storage_path)
    storage.mkdir(parents=True, exist_ok=True)
    target = storage / filename

    fd, temp_path = tempfile.mkstemp(prefix=".document-", suffix=Path(filename).suffix, dir=storage)
    os.close(fd)
    Path(temp_path).write_bytes(content)
    Path(temp_path).chmod(0o600)
    try:
        Path(temp_path).replace(target)
    finally:
        if Path(temp_path).exists():
            Path(temp_path).unlink()

    for existing in storage.iterdir():
        if existing.is_file() and existing.name != filename:
            existing.unlink()

    _vector_store(settings).replace(chunks, vectors)
    _set_active_document(filename)


def reindex_document(filename: str) -> None:
    settings = get_settings()
    storage = Path(settings.document_storage_path)
    path = storage / filename
    if not path.exists():
        raise ValueError("Document does not exist")
    text = parse_document(filename, path.read_bytes())
    chunks = build_chunks(filename, text)
    _vector_store(settings).replace(
        chunks,
        get_embedding_provider(settings).embed_texts(
            [chunk.text for chunk in chunks],
            mode="document",
        ),
    )
    _set_active_document(filename)


def initialize_document_index(settings: Settings | None = None) -> str | None:
    resolved_settings = settings or get_settings()
    storage = Path(resolved_settings.document_storage_path)
    if not storage.exists():
        reset_index(resolved_settings)
        return None

    candidates = sorted(
        path for path in storage.iterdir() if path.is_file() and not path.name.startswith(".")
    )
    if not candidates:
        reset_index(resolved_settings)
        return None

    path = candidates[0]
    text = parse_document(path.name, path.read_bytes())
    chunks = build_chunks(path.name, text)
    vectors = get_embedding_provider(resolved_settings).embed_texts(
        [chunk.text for chunk in chunks],
        mode="document",
    )
    _vector_store(resolved_settings).replace(chunks, vectors)
    _set_active_document(path.name)
    return path.name


def reset_index(settings: Settings | None = None) -> None:
    _vector_store(settings).clear()
    _set_active_document(None)


def search_documents(query: str, top_k: int = 5) -> list[SearchResult]:
    if _active_document_name is None:
        raise ValueError("No company document loaded")
    if not query.strip():
        raise ValueError("Query cannot be empty")
    if top_k < 1 or top_k > 25:
        raise ValueError("top_k must be between 1 and 25")

    settings = get_settings()
    query_vector = get_embedding_provider(settings).embed_texts([query], mode="query")[0]
    return _vector_store(settings).search(query_vector, top_k)


def parse_document(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".txt":
        text = _decode_text(content)
    elif ext == ".docx":
        text = _extract_docx_text(content)
    elif ext == ".pdf":
        text = _extract_pdf_text(content)
    else:
        raise ValueError(
            f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    if not text.strip():
        raise ValueError("Uploaded file is empty")
    return text


def store_pdf_context(text: str) -> str:
    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("Uploaded file is empty")

    context_id = str(uuid.uuid4())
    _pdf_contexts[context_id] = _chunk_pdf_context(normalized_text)
    return context_id


def get_pdf_context(context_id: str | None, query: str | None = None) -> str | None:
    if context_id is None:
        return None

    normalized_context_id = context_id.strip()
    if not normalized_context_id:
        return None

    chunks = _pdf_contexts.get(normalized_context_id)
    if chunks is None:
        raise ValueError("PDF context was not found. Please upload the PDF again.")
    return _select_pdf_context(chunks, query)


def _chunk_pdf_context(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []

    step = max(1, PDF_CONTEXT_CHUNK_WORDS - PDF_CONTEXT_CHUNK_OVERLAP)
    return [
        " ".join(words[start : start + PDF_CONTEXT_CHUNK_WORDS])
        for start in range(0, len(words), step)
    ]


def _select_pdf_context(chunks: list[str], query: str | None) -> str:
    if not chunks:
        return ""

    query_terms = _content_terms(query or "")
    if not query_terms:
        return "\n\n".join(chunks[:PDF_CONTEXT_MAX_CHUNKS])

    scored_chunks = [
        (_chunk_score(chunk, query_terms), index, chunk)
        for index, chunk in enumerate(chunks)
    ]
    scored_chunks.sort(key=lambda item: (-item[0], item[1]))

    selected = [
        (index, chunk)
        for score, index, chunk in scored_chunks
        if score > 0
    ][:PDF_CONTEXT_MAX_CHUNKS]
    if not selected:
        selected = [(index, chunk) for _, index, chunk in scored_chunks[:PDF_CONTEXT_MAX_CHUNKS]]

    selected.sort(key=lambda item: item[0])
    return "\n\n".join(chunk for _, chunk in selected)


def _chunk_score(chunk: str, query_terms: set[str]) -> int:
    chunk_terms = _content_terms(chunk)
    return sum(1 for term in query_terms if term in chunk_terms)


def _content_terms(text: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-zA-Z0-9]+", text.lower())
        if len(term) > 2
    }


def build_chunks(filename: str, text: str, max_words: int = 120, overlap: int = 20) -> list[DocumentChunk]:
    if max_words <= 0:
        raise ValueError("max_words must be greater than zero")
    if overlap < 0 or overlap >= max_words:
        raise ValueError("overlap must be less than max_words")

    words = text.split()
    step = max_words - overlap
    chunks: list[DocumentChunk] = []
    for index, start in enumerate(range(0, len(words), step)):
        chunk_text = " ".join(words[start : start + max_words])
        chunks.append(
            DocumentChunk(
                id=f"{CURRENT_DOCUMENT_VERSION}:{index}",
                text=chunk_text,
                metadata={
                    "source_name": filename,
                    "version": CURRENT_DOCUMENT_VERSION,
                    "chunk_index": index,
                },
            )
        )
    return chunks


def _decode_text(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Invalid document") from exc


def _extract_docx_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            xml_content = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ValueError("Invalid document") from exc

    try:
        root = ElementTree.fromstring(xml_content)
    except ElementTree.ParseError as exc:
        raise ValueError("Invalid document") from exc
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    return "\n".join(node.text or "" for node in root.iter(f"{namespace}t"))


def _extract_pdf_text(content: bytes) -> str:
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ValueError("PDF parsing support is unavailable") from exc

    try:
        with fitz.open(stream=content, filetype="pdf") as document:
            return "\n".join(page.get_text() for page in document)
    except Exception as exc:
        raise ValueError("Invalid document") from exc


def _set_active_document(filename: str | None) -> None:
    global _active_document_name
    _active_document_name = filename
