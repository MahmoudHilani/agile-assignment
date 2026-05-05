from types import SimpleNamespace

import bcrypt
from fastapi.testclient import TestClient

from app.core.security import decode_token
from app.main import app

client = TestClient(app)


def _admin_settings(password_hash: str) -> SimpleNamespace:
    return SimpleNamespace(admin_username="admin", admin_password_hash=password_hash)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def test_admin_login_returns_bearer_token(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.auth.get_settings", lambda: _admin_settings(_hash_password("secret")))

    response = client.post("/auth/login", json={"username": "admin", "password": "secret"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    payload = decode_token(body["access_token"])
    assert payload["sub"] == "admin"
    assert payload["role"] == "Admin"


def test_admin_login_rejects_invalid_password(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.auth.get_settings", lambda: _admin_settings(_hash_password("secret")))

    response = client.post("/auth/login", json={"username": "admin", "password": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_admin_login_rejects_missing_password_hash(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.auth.get_settings", lambda: _admin_settings(""))

    response = client.post("/auth/login", json={"username": "admin", "password": "secret"})

    assert response.status_code == 401


def test_admin_login_rejects_malformed_password_hash(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.auth.get_settings", lambda: _admin_settings("not-a-bcrypt-hash"))

    response = client.post("/auth/login", json={"username": "admin", "password": "secret"})

    assert response.status_code == 401
