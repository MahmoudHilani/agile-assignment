from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Agile Assignment API"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    company_document_dir: Path = BASE_DIR / "data" / "company_docs"
    company_document_filename: str = "company_document.txt"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def canonical_company_document_path(self) -> Path:
        return self.company_document_dir / self.company_document_filename


@lru_cache
def get_settings() -> Settings:
    return Settings()
