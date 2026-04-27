import bcrypt
from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    s = get_settings()
    credentials_valid = (
        body.username == s.admin_username
        and bool(s.admin_password_hash)
        and bcrypt.checkpw(body.password.encode(), s.admin_password_hash.encode())
    )
    if not credentials_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": body.username, "role": "Admin"})
    return TokenResponse(access_token=token)
