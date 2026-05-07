import base64

from fastapi.testclient import TestClient

from app.api.routes.tts_routes import get_tts_provider
from app.domain.models import AudioSynthesis
from app.main import app


client = TestClient(app)


class FakeTTSProvider:
    def synthesize(self, text: str) -> AudioSynthesis:
        return AudioSynthesis(audio_bytes=f"spoken:{text}".encode(), mime_type="audio/mpeg")


def test_tts_endpoint_returns_audio_response() -> None:
    app.dependency_overrides[get_tts_provider] = lambda: FakeTTSProvider()
    try:
        response = client.post("/tts", json={"text": "Hello world"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["mime_type"] == "audio/mpeg"
    assert base64.b64decode(payload["audio_b64"]) == b"spoken:Hello world"
    assert payload["chunk_count"] == 1


def test_removed_script_only_tts_routes_are_not_exposed() -> None:
    ask_response = client.post("/ask/stream", json={"text": "Hello world"})
    stream_response = client.post("/tts/stream", json={"text": "Hello world"})

    assert ask_response.status_code == 404
    assert stream_response.status_code == 404
