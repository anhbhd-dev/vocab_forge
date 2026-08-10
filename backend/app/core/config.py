"""Cấu hình tập trung (pydantic-settings), đọc từ biến môi trường / file .env."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["deepseek", "gemini", "mock"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "VocabForge Pro"
    debug: bool = True
    # PostgreSQL là DB chính (chạy trong Docker). Có thể trỏ về
    # "sqlite+aiosqlite:///./vocabforge.db" để chạy nhanh trên máy không có Docker.
    database_url: str = (
        "postgresql+asyncpg://vocabforge:vocabforge@localhost:5432/vocabforge"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Auth
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    # LLM providers
    llm_provider: ProviderName = "deepseek"
    llm_fallback_provider: ProviderName | None = None
    llm_timeout_seconds: float = 120.0
    llm_schema_retries: int = 2

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.0-flash"

    # SRS
    fsrs_desired_retention: float = 0.9
    fsrs_maximum_interval: int = 36500
    fsrs_enable_fuzzing: bool = True

    # Cluster pre-filter
    cluster_similarity_threshold: float = 0.75
    cluster_min_new_senses: int = 5

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("llm_fallback_provider", mode="before")
    @classmethod
    def _empty_means_no_fallback(cls, value):
        # LLM_FALLBACK_PROVIDER="" trong .env nghĩa là "không dùng fallback".
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
