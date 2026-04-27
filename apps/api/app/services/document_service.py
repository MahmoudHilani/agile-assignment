from pathlib import Path

from app.core.config import get_settings

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


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
    storage = Path(get_settings().document_storage_path)
    storage.mkdir(parents=True, exist_ok=True)
    for existing in storage.iterdir():
        existing.unlink()
    (storage / filename).write_bytes(content)


def reindex_document(filename: str) -> None:
    # TODO: integrate with embedding/vector-store pipeline (SCRUM-28)
    pass
