from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_documents_endpoint_is_reserved() -> None:
    response = client.post("/documents", json={"source_name": "placeholder.txt"})

    assert response.status_code == 501
    assert response.json()["code"] == "NOT_IMPLEMENTED"


def test_voice_websocket_is_reserved() -> None:
    with client.websocket_connect("/voice") as websocket:
        payload = websocket.receive_json()

    assert payload["code"] == "NOT_IMPLEMENTED"


def test_voice_endpoint_transcribes_uploaded_audio(monkeypatch) -> None:
    def fake_transcribe_audio(audio_bytes: bytes, language: str) -> str:
        assert audio_bytes == b"wav-bytes"
        assert language == "en-IE"
        return "hello from voice"

    monkeypatch.setattr("app.api.routes.voice.transcribe_audio", fake_transcribe_audio)

    response = client.post(
        "/voice",
        data={"locale": "en-IE"},
        files={"audio": ("recording.wav", b"wav-bytes", "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "hello from voice"}


def test_voice_endpoint_returns_422_for_unreadable_audio(monkeypatch) -> None:
    def fake_transcribe_audio(_: bytes, language: str) -> str:
        raise ValueError("Could not understand the audio")

    monkeypatch.setattr("app.api.routes.voice.transcribe_audio", fake_transcribe_audio)

    response = client.post(
        "/voice",
        files={"audio": ("recording.wav", b"wav-bytes", "audio/wav")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Could not understand the audio"
