import io
import asyncio
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
        self.histories: list[list[ChatTurn]] = []

    def generate(self, prompt: str, context: list[SearchResult], history: list[ChatTurn]) -> str:
        self.prompts.append(prompt)
        self.histories.append(list(history))
        return self.answer

    async def generate_stream(self, prompt: str, context: list[SearchResult], history: list[ChatTurn]):
        self.prompts.append(prompt)
        self.histories.append(list(history))
        yield self.answer


class FailingChatProvider:
    def generate(self, prompt: str, context: list[SearchResult], history: list[ChatTurn]) -> str:
        raise RuntimeError("upstream unavailable")


class FailingStreamChatProvider:
    def generate(self, prompt: str, context: list[SearchResult], history: list[ChatTurn]) -> str:
        return "This should not be returned"

    async def generate_stream(self, prompt: str, context: list[SearchResult], history: list[ChatTurn]):
        raise RuntimeError("upstream unavailable with internal details")
        yield "unreachable"


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


def test_query_request_accepts_missing_history(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = RecordingChatProvider("Single-turn answer")
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: provider)
    _upload_company_document(client, b"Acme builds clinical AI tools for hospitals.")

    response = client.post("/query", json={"query": "What does Acme build?", "top_k": 1})

    assert response.status_code == 200
    assert provider.histories == [[]]


def test_query_request_rejects_unbounded_prompt_inputs(client: TestClient) -> None:
    response = client.post("/query", json={"query": "x" * 1001})

    assert response.status_code == 422


def test_query_request_rejects_unbounded_history(client: TestClient) -> None:
    response = client.post(
        "/query",
        json={
            "query": "What services does the company offer?",
            "history": [
                {"role": "user" if index % 2 == 0 else "assistant", "content": f"message {index}"}
                for index in range(13)
            ],
        },
    )

    assert response.status_code == 422


def test_query_request_rejects_unbounded_history_content(client: TestClient) -> None:
    response = client.post(
        "/query",
        json={
            "query": "What services does the company offer?",
            "history": [{"role": "user", "content": "x" * 2001}],
        },
    )

    assert response.status_code == 422


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
    assert "If the answer requires counting items explicitly listed in the context, count them." in provider.prompts[0]


def test_rag_prompt_includes_prior_conversation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = RecordingChatProvider()
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: provider)
    _upload_company_document(client, b"Acme builds clinical AI tools for hospitals.")

    response = client.post(
        "/query",
        json={
            "query": "What services should I ask about next?",
            "top_k": 1,
            "history": [
                {"role": "user", "content": "What does Acme build?"},
                {"role": "assistant", "content": "Acme builds clinical AI tools."},
            ],
        },
    )

    assert response.status_code == 200
    prompt = provider.prompts[0]
    assert "Conversation so far:" in prompt
    assert "User: What does Acme build?" in prompt
    assert "Assistant: Acme builds clinical AI tools." in prompt
    assert provider.histories[0] == [
        ChatTurn(role="user", content="What does Acme build?"),
        ChatTurn(role="assistant", content="Acme builds clinical AI tools."),
    ]


def test_short_answer_to_assistant_follow_up_uses_prior_conversation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = RecordingChatProvider("React is a reasonable frontend choice.")
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: provider)
    _upload_company_document(client, b"Acme builds web applications and customer-facing websites.")

    response = client.post(
        "/query",
        json={
            "query": "react probably",
            "top_k": 1,
            "history": [
                {"role": "user", "content": "I have a plumbing company and I want a website"},
                {
                    "role": "assistant",
                    "content": (
                        "What specific features do you want to include on the website, "
                        "and what are your expectations for the technology stack?"
                    ),
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "React is a reasonable frontend choice."
    assert provider.histories[0] == [
        ChatTurn(role="user", content="I have a plumbing company and I want a website"),
        ChatTurn(
            role="assistant",
            content=(
                "What specific features do you want to include on the website, "
                "and what are your expectations for the technology stack?"
            ),
        ),
    ]


@pytest.mark.parametrize(
    "customer_reply",
    [
        "a hero section on the landing page",
        "modern and friendly",
        "something simple for local customers",
    ],
)
def test_short_answers_to_project_follow_up_stay_in_scope(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, customer_reply: str
) -> None:
    provider = RecordingChatProvider("I can help refine that into a website direction.")
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: provider)
    _upload_company_document(client, b"Acme builds websites and digital products for businesses.")

    response = client.post(
        "/query",
        json={
            "query": customer_reply,
            "top_k": 1,
            "history": [
                {"role": "user", "content": "I run a local business and want a website"},
                {
                    "role": "assistant",
                    "content": (
                        "What features, design style, tone, or customer actions should the website support?"
                    ),
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "I can help refine that into a website direction."
    assert provider.histories[0][-1] == ChatTurn(
        role="assistant",
        content="What features, design style, tone, or customer actions should the website support?",
    )


def test_query_history_accepts_recent_message_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = RecordingChatProvider()
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: provider)
    _upload_company_document(client, b"Acme provides web apps, AI assistants, and automation services.")
    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": f"message {index}"}
        for index in range(12)
    ]

    response = client.post(
        "/query",
        json={"query": "What services does Acme offer?", "top_k": 1, "history": history},
    )

    assert response.status_code == 200
    assert [turn.content for turn in provider.histories[0]] == [f"message {index}" for index in range(12)]
    prompt_lines = provider.prompts[0].splitlines()
    assert "User: message 0" in prompt_lines
    assert "Assistant: message 11" in prompt_lines


def test_stream_query_passes_prior_conversation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = RecordingChatProvider("Streamed answer")
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: provider)
    _upload_company_document(client, b"Acme builds clinical AI tools for hospitals.")

    response = client.post(
        "/query/stream",
        json={
            "query": "Which services are relevant?",
            "top_k": 1,
            "history": [
                {"role": "user", "content": "Can Acme help hospitals?"},
                {"role": "assistant", "content": "Yes, Acme builds clinical AI tools."},
            ],
        },
    )

    assert response.status_code == 200
    assert response.text == "Streamed answer"
    assert provider.histories[0] == [
        ChatTurn(role="user", content="Can Acme help hospitals?"),
        ChatTurn(role="assistant", content="Yes, Acme builds clinical AI tools."),
    ]


def test_rag_prompt_guides_customer_facing_company_responses(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = RecordingChatProvider()
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: provider)
    _upload_company_document(client, b"Acme develops web apps, AI assistants, and workflow automation.")

    response = client.post("/query", json={"query": "Can you help build my booking app?", "top_k": 1})

    assert response.status_code == 200
    prompt = provider.prompts[0]
    assert "You are a customer-facing company overview assistant" in prompt
    assert "You are an AI assistant, not a company employee" in prompt
    assert "Do not claim to be part of the company" in prompt
    assert "not contacting you" in prompt
    assert "helpful, cheerful, and professional" in prompt
    assert "give prospective customers a clear overview of the company" in prompt
    assert "its members or team when available in the company knowledge" in prompt
    assert "connect the company's relevant services to the project at a high level" in prompt
    assert "stay within the retrieved context" in prompt
    assert "Do not invent services, experience, prices, timelines, guarantees, or contact details" in prompt
    assert "Use the retrieved context as internal company knowledge" in prompt
    assert "Do not mention sources, documents, chunks, retrieved context, or file names" in prompt
    assert "Do not say the user provided the company knowledge" in prompt
    assert "treat the user's reply as in-scope project context" in prompt
    assert "Do not run an extended discovery or sales-closing conversation" in prompt
    assert "encourage the user to contact the team for tailored advice" in prompt


@pytest.mark.parametrize(
    "customer_query",
    [
        "Can I hire you?",
        "Are you available next month?",
        "Can you integrate Stripe?",
    ],
)
def test_customer_project_unknowns_reach_rag_contact_fallback_prompt(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, customer_query: str
) -> None:
    provider = RecordingChatProvider("Please contact the team to discuss the project.")
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: provider)
    _upload_company_document(client, b"Acme develops web apps, AI assistants, and workflow automation.")

    response = client.post("/query", json={"query": customer_query, "top_k": 1})

    assert response.status_code == 200
    assert response.json()["answer"] == "Please contact the team to discuss the project."
    assert len(provider.prompts) == 1
    assert customer_query in provider.prompts[0]
    assert "If the context does not contain the answer, say you do not know" in provider.prompts[0]
    assert "contact the company through the available website channels" in provider.prompts[0]


def test_off_topic_query_returns_customer_scope_refusal_without_calling_llm(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = RecordingChatProvider("This should not be returned")
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: provider)

    response = client.post("/query", json={"query": "Explain Python classes", "top_k": 1})

    assert response.status_code == 200
    assert response.json() == {
        "answer": query_service.OFF_TOPIC_RESPONSE,
        "sources": [],
    }
    assert provider.prompts == []


def test_off_topic_stream_returns_customer_scope_refusal_without_calling_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = RecordingChatProvider("This should not be returned")
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: provider)

    async def collect_chunks() -> list[str]:
        return [
            chunk async for chunk in query_service.run_rag_query_stream("Explain Python classes", top_k=1)
        ]

    chunks = asyncio.run(collect_chunks())

    assert "".join(chunks) == query_service.OFF_TOPIC_RESPONSE
    assert provider.prompts == []


def test_stream_provider_failure_returns_safe_customer_message(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: FailingStreamChatProvider())
    _upload_company_document(client, b"Acme develops web apps and workflow automation.")

    response = client.post("/query/stream", json={"query": "What services does Acme offer?", "top_k": 1})

    assert response.status_code == 200
    assert response.text == query_service.STREAM_ERROR_RESPONSE
    assert "upstream unavailable" not in response.text


def test_llm_provider_failure_returns_controlled_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(query_service, "get_chat_provider", lambda _settings=None: FailingChatProvider())
    _upload_company_document(client, b"Acme builds clinical AI tools for hospitals.")

    response = client.post("/query", json={"query": "What does Acme build?", "top_k": 1})

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM provider failed"
