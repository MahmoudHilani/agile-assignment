import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_query_requires_no_auth(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.query.run_rag_query", lambda query, top_k: ("answer", []))
    response = client.post("/query", json={"query": "What does the company do?"})
    assert response.status_code == 200


def test_voice_requires_no_auth(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.voice.transcribe_audio", lambda audio_bytes, language: "hello")
    response = client.post(
        "/voice",
        data={"locale": "en-US"},
        files={"audio": ("recording.wav", io.BytesIO(b"wav-bytes"), "audio/wav")},
    )
    assert response.status_code == 200


def test_document_replace_requires_admin_auth() -> None:
    response = client.put(
        "/documents",
        files={"file": ("doc.txt", io.BytesIO(b"hello world"), "text/plain")},
    )
    assert response.status_code == 401
