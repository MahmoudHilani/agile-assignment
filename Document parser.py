"""Parse supported document formats into plain text.

Supported formats
-----------------
.txt  – read as UTF-8
.pdf  – extract text page by page via pypdf (optional dependency)
.docx – extract paragraph text via python-docx (optional dependency)

Both PDF and DOCX parsers degrade gracefully: if the optional library is not
installed a clear ImportError is raised so the caller can surface a helpful
error message rather than a cryptic AttributeError.
"""

from __future__ import annotations

from pathlib import Path


SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}


def parse_document(path: Path) -> str:
    """Return the full text content of *path*.

    Raises
    ------
    ValueError
        If the file extension is not supported or the file yields no text.
    ImportError
        If a required optional library is missing for .pdf or .docx files.
    """
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported format '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if ext == ".txt":
        text = _parse_txt(path)
    elif ext == ".pdf":
        text = _parse_pdf(path)
    else:
        text = _parse_docx(path)

    text = text.strip()
    if not text:
        raise ValueError("Document contains no extractable text.")
    return text


# ── format-specific helpers ───────────────────────────────────────────────────

def _parse_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "pypdf is required to parse PDF files. Install it with: pip install pypdf"
        ) from exc

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _parse_docx(path: Path) -> str:
    try:
        import docx  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "python-docx is required to parse DOCX files. "
            "Install it with: pip install python-docx"
        ) from exc

    doc = docx.Document(str(path))
    return "\n".join(para.text for para in doc.paragraphs)