"""Cấu hình tập trung (pydantic-settings), đọc từ biến môi trường / file .env."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ProviderName = Literal["deepseek", "gemini", "mock"]

# Những giá trị JWT_SECRET đã nằm sẵn trong repo/tài liệu: ai đọc source cũng ký được
# token giả cho bất kỳ user nào. Chặn thẳng khi chạy production.
_PUBLIC_JWT_SECRETS = frozenset(
    {
        "dev-secret-change-me",
        "change-me-to-a-long-random-string",
        "change-me-to-a-long-random-string-at-least-32-chars",
        "doi-chuoi-nay-thanh-mot-chuoi-ngau-nhien-dai-it-nhat-32-ky-tu",
    }
)


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
    # Số lời gọi TTS chạy cùng lúc. Đây là van điều tiết giữa vòng agent và vòng review:
    # Kokoro bản CPU ăn ~120% CPU mỗi luồng, để 4 là nó nuốt trọn máy và làm API đứng
    # hình. 2 vẫn nhanh hơn realtime mà còn chừa chỗ cho request của người đang học.
    tts_max_concurrency: int = 2
    audio_dir: str = "/app/audio"

    # SRS
    fsrs_desired_retention: float = 0.9
    fsrs_maximum_interval: int = 36500
    fsrs_enable_fuzzing: bool = True

    # Cluster pre-filter
    cluster_similarity_threshold: float = 0.75
    cluster_min_new_senses: int = 5

    # CORS
    # NoDecode: tắt bước tự parse JSON của pydantic-settings để _parse_cors_origins bên
    # dưới nhận chuỗi thô — xem lý do ở đó.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # Regex origin bổ sung, áp dụng CẢ ở production (khác cors_lan_origin_regex vốn chỉ
    # bật khi DEBUG). Dùng khi FE có domain sinh tự động: mỗi PR trên Cloudflare/Vercel
    # là một subdomain mới nên không thể liệt kê sẵn trong cors_origins.
    # Vd: r"^https://[a-z0-9-]+\.vocab-forge\.pages\.dev$"
    # Để trống = không mở thêm origin nào.
    cors_origin_regex: str = ""

    # Ở chế độ DEBUG, chấp nhận thêm mọi origin nằm trong dải IP nội bộ (RFC 1918) trên
    # bất kỳ cổng nào. Đây là thứ cho phép mở app từ điện thoại cùng Wi-Fi mà không phải
    # ghi cứng IP LAN vào cấu hình — IP do router cấp và có thể đổi bất cứ lúc nào.
    # KHÔNG bật ở production: DEBUG=false thì regex này là None và chỉ còn cors_origins.
    cors_lan_origin_regex: str = (
        r"^http://(localhost|127\.0\.0\.1"
        r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|192\.168\.\d{1,3}\.\d{1,3}"
        r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?$"
    )

    @field_validator("llm_fallback_provider", mode="before")
    @classmethod
    def _empty_means_no_fallback(cls, value):
        # LLM_FALLBACK_PROVIDER="" trong .env nghĩa là "không dùng fallback".
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value):
        """Nhận CORS_ORIGINS ở cả dạng JSON lẫn danh sách phân tách bằng dấu phẩy.

        Mặc định pydantic-settings đòi JSON cho kiểu list, nên gõ
        `CORS_ORIGINS=https://a.dev,https://b.dev` vào ô biến môi trường của
        Railway/Render/Fly/Cloudflare là app crash ngay lúc khởi động với một thông báo
        khó hiểu. Đó là dạng người ta gõ tự nhiên nhất, nên nhận luôn cả hai.
        """
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                import json

                value = json.loads(text)
            else:
                value = text.split(",")
        if isinstance(value, list):
            # Trình duyệt gửi header `Origin` KHÔNG BAO GIỜ có dấu `/` ở cuối, mà
            # CORSMiddleware so khớp chuỗi chính xác — "https://x/" là lỗi im lặng kinh
            # điển: cấu hình nhìn đúng nhưng mọi request đều bị chặn.
            return [str(v).strip().rstrip("/") for v in value if str(v).strip()]
        return value

    @model_validator(mode="after")
    def _guard_production(self):
        """Chặn khởi động khi cấu hình production còn giá trị mặc định của dev.

        Fail nhanh lúc boot tốt hơn nhiều so với chạy được rồi mới phát hiện: JWT_SECRET
        công khai nghĩa là bất kỳ ai cũng ký được token cho bất kỳ tài khoản nào.
        """
        if self.debug:
            return self

        if self.jwt_secret in _PUBLIC_JWT_SECRETS or len(self.jwt_secret) < 32:
            raise ValueError(
                "DEBUG=false nhưng JWT_SECRET vẫn là giá trị mẫu (hoặc ngắn hơn 32 ký "
                "tự). Sinh chuỗi mới: python -c \"import secrets; "
                'print(secrets.token_urlsafe(48))"'
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
