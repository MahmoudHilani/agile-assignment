from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings


def create_access_token(data: dict) -> str:
    settings = get_settings()
    payload = {
        **data,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
