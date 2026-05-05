from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_documents_endpoint_is_reserved() -> None:
    response = client.post("/documents", json={"source_name": "placeholder.txt"})

    assert response.status_code == 501
    assert response.json()["code"] == "NOT_IMPLEMENTED"


def test_query_endpoint_is_reserved() -> None:
    response = client.post("/query", json={"query": "What should this project do?"})

    assert response.status_code == 501
    assert response.json()["code"] == "NOT_IMPLEMENTED"


def test_voice_websocket_is_reserved() -> None:
    with client.websocket_connect("/voice/ws") as websocket:
        payload = websocket.receive_json()

    assert payload["code"] == "NOT_IMPLEMENTED"
