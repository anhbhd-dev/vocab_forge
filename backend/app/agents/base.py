"""LLMProvider — interface chung cho mọi provider.

File 03 mục 0: "Provider pattern: mỗi agent gọi qua interface chung
`LLMProvider.complete(system_prompt, user_input, response_schema)`, cho phép swap
DeepSeek ↔ Gemini không đổi code gọi."

File 04 (STACK): abstract base class + factory, KHÔNG hardcode provider cụ thể vào
business logic.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class LLMError(RuntimeError):
    """Lỗi tầng provider (network, auth, rate limit, response rỗng)."""


class AgentSchemaError(RuntimeError):
    """LLM trả về JSON không khớp schema sau khi đã retry hết số lần cho phép."""


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    # None nếu provider không trả usage
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class LLMProvider(ABC):
    """Mọi provider phải trả về TEXT thô; việc parse/validate JSON do `runner.py` lo."""

    name: str = "base"

    @property
    @abstractmethod
    def model(self) -> str: ...

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_input: str | dict[str, Any],
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Gọi LLM một lượt, trả về text thô.

        `user_input` có thể là dict (sẽ được serialize JSON) hoặc string đã dựng sẵn.
        `response_schema`: JSON Schema mong đợi; provider dùng để bật JSON mode và/hoặc
        nhắc lại schema trong prompt.
        """

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _render_user_message(
        user_input: str | dict[str, Any], response_schema: dict[str, Any] | None
    ) -> str:
        body = (
            user_input
            if isinstance(user_input, str)
            else json.dumps(user_input, ensure_ascii=False, indent=2)
        )
        if not response_schema:
            return body
        schema_text = json.dumps(response_schema, ensure_ascii=False, indent=2)
        return (
            f"INPUT:\n{body}\n\n"
            f"OUTPUT JSON SCHEMA (bắt buộc khớp chính xác):\n{schema_text}\n\n"
            "Trả về CHỈ JSON object hợp lệ, không markdown, không giải thích."
        )
