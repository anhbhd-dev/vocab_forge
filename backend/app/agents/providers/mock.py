"""Mock provider — dùng cho test và dev khi chưa có API key.

Không phải provider thật; chỉ sinh response hợp lệ theo schema để chạy được toàn bộ
pipeline offline (đặc biệt cho `tests/`, nơi tuyệt đối không được gọi mạng).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from app.agents.base import LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(
        self,
        responses: dict[str, Any] | None = None,
        handler: Callable[[str, str | dict[str, Any]], Any] | None = None,
    ) -> None:
        """`responses`: map agent_name → object trả về. `handler`: hàm tuỳ biến."""
        self._responses = responses or {}
        self._handler = handler
        self.calls: list[tuple[str, str | dict[str, Any]]] = []

    @property
    def model(self) -> str:
        return "mock-model"

    async def complete(
        self,
        system_prompt: str,
        user_input: str | dict[str, Any],
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.calls.append((system_prompt, user_input))

        if self._handler is not None:
            payload = self._handler(system_prompt, user_input)
        else:
            payload = self._match_by_prompt(system_prompt)

        return LLMResponse(
            text=json.dumps(payload, ensure_ascii=False),
            model=self.model,
            provider=self.name,
        )

    def _match_by_prompt(self, system_prompt: str) -> Any:
        for key, value in self._responses.items():
            if key in system_prompt:
                return value
        # Fallback: phát hiện agent qua một câu đặc trưng trong system prompt.
        if "trích xuất các đơn vị từ vựng" in system_prompt:
            return {
                "candidates": [
                    {
                        "surface_form": "have a detrimental effect on",
                        "item_type": "collocation",
                        "cefr_level": "C1",
                        "reason": "high-frequency academic collocation",
                        "sentence_context": "Excessive screen time has a detrimental effect on sleep.",
                    }
                ]
            }
        if "viết câu ví dụ minh" in system_prompt:
            return {
                "examples": [
                    {
                        "sentence": "Excessive screen time among teenagers has a detrimental effect on both their sleep quality and academic performance.",
                        "essay_type": "opinion",
                    }
                ]
            }
        if "kỹ thuật ghi nhớ" in system_prompt:
            return {
                "mnemonic_text": "detrimental ~ 'đe doạ mental' — hình dung màn hình phát sáng bào mòn não.",
                "mnemonic_type": "keyword_dual_coding",
            }
        if "phân tích một nhóm" in system_prompt:
            return {"clusters": []}
        if "giám khảo chấm IELTS Writing" in system_prompt:
            return {
                "is_correct": True,
                "error_type": "none",
                "feedback_text": "Câu dùng đúng collocation và đúng văn phong academic.",
                "corrected_sentence": None,
            }
        if "định nghĩa" in system_prompt:
            return {
                "senses": [
                    {
                        "definition_en": "to cause harm or damage to something",
                        "definition_vi": "gây tác động tiêu cực tới",
                        "part_of_speech": "verb phrase",
                        "register": "academic",
                        "needs_mnemonic": True,
                    }
                ]
            }
        return {}
