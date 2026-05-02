import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.domain.models import ChatTurn, SearchResult
from app.main import create_app
from app.services import query_service


class RecordingChatProvider:
    def __init__(self, answer: str = "Generated answer") -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def generate(self, prompt: str, context: list[SearchResult], history: list[ChatTurn]) -> str:
        self.prompts.append(prompt)
        return self.answer


class FailingChatProvider:
    def generate(self, prompt: str, context: list[SearchResult], history: list[ChatTurn]) -> str:
        raise RuntimeError("upstream unavailable")


def _admin_headers() -> dict[str, str]:
    token = create_access_token({"sub": "test-user", "role": "Admin"})
    return {"Authorization": f"Bearer {token}"}


def _settings(tmp_path: Path):
    from app.core.config import Settings

    return Settings(
        document_storage_path=str(tmp_path / "documents"),
        chroma_db_path=str(tmp_path / "chroma"),
        chroma_collection_name="company-documents-test",
    )


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = _settings(tmp_path)
    monkeypatch.setattr("app.services.document_service.get_settings", lambda: settings)
    return TestClient(create_app(settings))


def _upload_company_document(client: TestClient, content: bytes) -> None:
    response = client.put(
        "/documents",
        files={"file": ("company.txt", io.BytesIO(content), "text/plain")},
        headers=_admin_headers(),
    )
    assert response.status_code == 200


def test_query_remains_public(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = RecordingChatProvider("Public answer")
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: provider)
    _upload_company_document(client, b"Acme builds clinical AI tools for hospitals.")

    response = client.post("/query", json={"query": "What does Acme build?", "top_k": 1})

    assert response.status_code == 200
    assert response.json()["answer"] == "Public answer"
    assert response.json()["sources"] == ["company.txt#0"]


def test_rag_prompt_includes_retrieved_chunks_and_user_query(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = RecordingChatProvider()
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: provider)
    _upload_company_document(client, b"Acme builds clinical AI tools for hospitals.")

    response = client.post("/query", json={"query": "Which users does Acme serve?", "top_k": 1})

    assert response.status_code == 200
    assert len(provider.prompts) == 1
    assert "Acme builds clinical AI tools for hospitals." in provider.prompts[0]
    assert "Which users does Acme serve?" in provider.prompts[0]


def test_llm_provider_failure_returns_controlled_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: FailingChatProvider())
    _upload_company_document(client, b"Acme builds clinical AI tools for hospitals.")

    response = client.post("/query", json={"query": "What does Acme build?", "top_k": 1})

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM provider failed"
