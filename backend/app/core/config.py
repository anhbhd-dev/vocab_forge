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
    deepseek_model: str = "deepseek-v4-flash"
    # V4 bật thinking mặc định (effort=high). Agent ở đây chỉ cần JSON đúng schema,
    # reasoning chỉ làm chậm và đắt thêm → tắt. Đặt True nếu muốn bật lại.
    deepseek_thinking: bool = False

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.0-flash"

    # Text-to-speech (Kokoro-82M chạy local, API tương thích OpenAI).
    # Audio sinh SẴN ở vòng agent rồi phục vụ tĩnh — vòng review không gọi TTS.
    tts_enabled: bool = True
    tts_base_url: str = "http://tts:8880/v1"
    tts_model: str = "kokoro"
    # af_heart: giọng nữ Mỹ, rõ chữ — hợp để nghe mẫu phát âm từ vựng.
    tts_voice: str = "af_heart"
    # Giọng nam sinh SONG SONG với giọng nữ, không thay thế: nghe một từ bằng hai chất
    # giọng khác nhau là cách rẻ nhất để tách âm vị ra khỏi đặc trưng của người nói —
    # người học nhận ra từ đó khi người khác đọc chứ không chỉ khi af_heart đọc.
    tts_voice_male: str = "am_michael"
    # Chậm hơn realtime một chút: người học cần nghe rõ từng âm, không phải nghe kể chuyện.
    tts_speed: float = 0.9
    tts_timeout_seconds: float = 120.0
    audio_dir: str = "/app/audio"

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
