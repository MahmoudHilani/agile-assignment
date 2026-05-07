import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.services.document_service import MAX_FILE_BYTES, get_pdf_context, parse_document
from conftest import make_docx_bytes, make_pdf_bytes

client = TestClient(app)


def make_token(role: str) -> str:
    return create_access_token({"sub": "test-user", "role": role})


def _txt_file(content: bytes = b"hello world") -> dict:
    return {"file": ("doc.txt", io.BytesIO(content), "text/plain")}


def _pdf_file(text: str = "PDF context for queries") -> dict:
    content = make_pdf_bytes(text)
    return {"file": ("context.pdf", io.BytesIO(content), "application/pdf")}


def _docx_file(text: str = "DOCX company context") -> dict:
    content = make_docx_bytes(text)
    return {
        "file": (
            "company.docx",
            io.BytesIO(content),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }


def test_parse_document_supports_docx() -> None:
    text = parse_document("company.docx", make_docx_bytes("Company DOCX context"))

    assert "Company DOCX context" in text


def test_parse_pdf_valid_file_returns_text() -> None:
    response = client.post("/documents/parse-pdf", files=_pdf_file("Company PDF context"))

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "context.pdf"
    assert get_pdf_context(body["document_context_id"]) is not None
    assert "Company PDF context" in get_pdf_context(body["document_context_id"])
    assert body["mime_type"] == "application/pdf"


def test_parse_pdf_rejects_non_pdf() -> None:
    response = client.post("/documents/parse-pdf", files=_txt_file())

    assert response.status_code == 422


def test_parse_pdf_rejects_oversized_file() -> None:
    oversized = b"x" * (MAX_FILE_BYTES + 1)
    response = client.post(
        "/documents/parse-pdf",
        files={"file": ("big.pdf", io.BytesIO(oversized), "application/pdf")},
    )

    assert response.status_code == 422


def test_replace_no_auth_returns_401() -> None:
    response = client.put("/documents", files=_txt_file())
    assert response.status_code == 401


def test_replace_non_admin_returns_403() -> None:
    token = make_token("User")
    response = client.put(
        "/documents",
        files=_txt_file(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_replace_valid_admin_pdf_returns_200(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.document_service.get_settings", lambda: _settings(tmp_path))
    token = make_token("Admin")
    response = client.put(
        "/documents",
        files=_pdf_file("Company handbook content"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["filename"] == "context.pdf"


def test_replace_valid_admin_docx_returns_200(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.document_service.get_settings", lambda: _settings(tmp_path))
    token = make_token("Admin")
    response = client.put(
        "/documents",
        files=_docx_file("Company DOCX handbook content"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["filename"] == "company.docx"


def test_replace_admin_txt_returns_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.document_service.get_settings", lambda: _settings(tmp_path))
    token = make_token("Admin")
    response = client.put(
        "/documents",
        files=_txt_file(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_replace_invalid_format_returns_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.document_service.get_settings", lambda: _settings(tmp_path))
    token = make_token("Admin")
    response = client.put(
        "/documents",
        files={"file": ("malware.exe", io.BytesIO(b"bad"), "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_replace_path_traversal_filename_returns_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.document_service.get_settings", lambda: _settings(tmp_path))
    token = make_token("Admin")
    response = client.put(
        "/documents",
        files={"file": ("../escaped.txt", io.BytesIO(b"bad"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert not (tmp_path.parent / "escaped.txt").exists()


def test_replace_empty_file_returns_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.document_service.get_settings", lambda: _settings(tmp_path))
    token = make_token("Admin")
    response = client.put(
        "/documents",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_replace_oversized_file_returns_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.document_service.get_settings", lambda: _settings(tmp_path))
    token = make_token("Admin")
    oversized = b"x" * (MAX_FILE_BYTES + 1)
    response = client.put(
        "/documents",
        files={"file": ("big.pdf", io.BytesIO(oversized), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_replace_overwrites_old_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.document_service.get_settings", lambda: _settings(tmp_path))
    token = make_token("Admin")
    headers = {"Authorization": f"Bearer {token}"}

    client.put(
        "/documents",
        files={"file": ("old.pdf", io.BytesIO(make_pdf_bytes("old content")), "application/pdf")},
        headers=headers,
    )
    client.put(
        "/documents",
        files={"file": ("new.pdf", io.BytesIO(make_pdf_bytes("new content")), "application/pdf")},
        headers=headers,
    )

    stored = list(tmp_path.iterdir())
    assert len(stored) == 1
    assert stored[0].name == "new.pdf"


def test_startup_ignores_unsupported_existing_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.document_service import initialize_document_index

    monkeypatch.setattr("app.services.document_service.get_settings", lambda: _settings(tmp_path))
    (tmp_path / "company.xlsx").write_bytes(b"not a supported startup document")

    assert initialize_document_index() is None


class _settings:
    def __init__(self, tmp_path: Path) -> None:
        from app.core.config import get_settings
        base = get_settings()
        self.secret_key = base.secret_key
        self.algorithm = base.algorithm
        self.access_token_expire_minutes = base.access_token_expire_minutes
        self.document_storage_path = str(tmp_path)
        self.chroma_db_path = str(tmp_path.parent / f"{tmp_path.name}-chroma")
        self.chroma_collection_name = "company-documents-test"
        self.embedding_model_name = "nomic-ai/nomic-embed-text-v1.5"
        self.llm_timeout_seconds = 30.0
