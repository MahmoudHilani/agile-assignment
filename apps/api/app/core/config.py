from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Agile Assignment API"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    log_level: str = "INFO"
    secret_key: str = "dev-secret-change-in-production!"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    document_storage_path: str = "data/documents"
    chroma_db_path: str = "data/chroma"
    chroma_collection_name: str = "company-documents"
    admin_username: str = "admin"
    admin_password_hash: str = ""
    ollama_url: str = ""
    model_name: str = ""
    embedding_model_name: str = "nomic-ai/nomic-embed-text-v1.5"
    embedding_trust_remote_code: bool = False
    trusted_remote_embedding_models: str = "nomic-ai/nomic-embed-text-v1.5"
    llm_timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
