from hmac import compare_digest

import bcrypt
from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _password_matches(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    settings = get_settings()
    credentials_valid = (
        compare_digest(body.username, settings.admin_username)
        and _password_matches(body.password, settings.admin_password_hash)
    )
    if not credentials_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": body.username, "role": "Admin"})
    return TokenResponse(access_token=token)
