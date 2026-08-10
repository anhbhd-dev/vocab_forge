"""Factory chọn provider theo config — business logic KHÔNG import provider cụ thể.

File 04 (STACK): "abstract base class + factory, KHÔNG hardcode provider cụ thể vào
business logic".
"""

from __future__ import annotations

from app.agents.base import LLMError, LLMProvider, LLMResponse
from app.agents.providers.deepseek import DeepSeekProvider
from app.agents.providers.gemini import GeminiProvider
from app.agents.providers.mock import MockProvider
from app.core.config import settings

_REGISTRY: dict[str, type[LLMProvider]] = {
    "deepseek": DeepSeekProvider,
    "gemini": GeminiProvider,
    "mock": MockProvider,
}

# Cho phép test/app inject provider thay thế mà không phải sửa config toàn cục.
_override: LLMProvider | None = None


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    _REGISTRY[name] = cls


def set_provider_override(provider: LLMProvider | None) -> None:
    global _override
    _override = provider


def build_provider(name: str | None = None) -> LLMProvider:
    if _override is not None:
        return _override
    key = (name or settings.llm_provider).lower()
    if key not in _REGISTRY:
        raise LLMError(
            f"Provider không hỗ trợ: {key}. Có: {', '.join(sorted(_REGISTRY))}"
        )
    return _REGISTRY[key]()


class FallbackProvider(LLMProvider):
    """Thử provider chính, lỗi thì chuyển sang provider dự phòng.

    File 00 mục 3: DeepSeek là chính, Gemini "dự phòng/đối chiếu".
    """

    name = "fallback"

    def __init__(self, primary: LLMProvider, secondary: LLMProvider) -> None:
        self.primary = primary
        self.secondary = secondary
        self.last_used: LLMProvider = primary

    @property
    def model(self) -> str:
        return self.last_used.model

    async def complete(self, system_prompt, user_input, response_schema=None) -> LLMResponse:  # type: ignore[override]
        try:
            self.last_used = self.primary
            return await self.primary.complete(
                system_prompt, user_input, response_schema
            )
        except LLMError:
            self.last_used = self.secondary
            return await self.secondary.complete(
                system_prompt, user_input, response_schema
            )


def get_provider() -> LLMProvider:
    """Provider mặc định của app (kèm fallback nếu có cấu hình)."""
    if _override is not None:
        return _override
    primary = build_provider(settings.llm_provider)
    fallback_name = settings.llm_fallback_provider
    if fallback_name and fallback_name != settings.llm_provider:
        try:
            return FallbackProvider(primary, build_provider(fallback_name))
        except LLMError:
            return primary
    return primary
