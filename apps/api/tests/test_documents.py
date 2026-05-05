import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.services.document_service import MAX_FILE_BYTES

client = TestClient(app)


def make_token(role: str) -> str:
    return create_access_token({"sub": "test-user", "role": role})


def _txt_file(content: bytes = b"hello world") -> dict:
    return {"file": ("doc.txt", io.BytesIO(content), "text/plain")}


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


def test_replace_valid_admin_txt_returns_200(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.document_service.get_settings", lambda: _settings(tmp_path))
    token = make_token("Admin")
    response = client.put(
        "/documents",
        files=_txt_file(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["filename"] == "doc.txt"


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
        files=_txt_file(content=b""),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_replace_oversized_file_returns_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.document_service.get_settings", lambda: _settings(tmp_path))
    token = make_token("Admin")
    oversized = b"x" * (MAX_FILE_BYTES + 1)
    response = client.put(
        "/documents",
        files={"file": ("big.txt", io.BytesIO(oversized), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_replace_overwrites_old_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.document_service.get_settings", lambda: _settings(tmp_path))
    token = make_token("Admin")
    headers = {"Authorization": f"Bearer {token}"}

    client.put("/documents", files={"file": ("old.txt", io.BytesIO(b"old content"), "text/plain")}, headers=headers)
    client.put("/documents", files={"file": ("new.txt", io.BytesIO(b"new content"), "text/plain")}, headers=headers)

    stored = list(tmp_path.iterdir())
    assert len(stored) == 1
    assert stored[0].name == "new.txt"


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
