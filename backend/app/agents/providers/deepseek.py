"""DeepSeek provider — API tương thích OpenAI (`/chat/completions`).

Provider CHÍNH theo file 00 mục 3 (rẻ nhất cho khối lượng gọi hằng ngày).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.agents.base import LLMError, LLMProvider, LLMResponse
from app.core.config import settings


class DeepSeekProvider(LLMProvider):
    name = "deepseek"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.deepseek_api_key
        self._base_url = (base_url or settings.deepseek_base_url).rstrip("/")
        self._model = model or settings.deepseek_model
        self._timeout = timeout or settings.llm_timeout_seconds

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        system_prompt: str,
        user_input: str | dict[str, Any],
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        if not self._api_key:
            raise LLMError(
                "Thiếu DEEPSEEK_API_KEY — đặt biến môi trường hoặc đổi LLM_PROVIDER."
            )

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": self._render_user_message(user_input, response_schema),
                },
            ],
            # Mọi agent bắt buộc trả JSON thuần (file 03 mục 0).
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise LLMError(f"DeepSeek network error: {exc}") from exc

        if resp.status_code >= 400:
            raise LLMError(f"DeepSeek HTTP {resp.status_code}: {resp.text[:500]}")

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"DeepSeek trả response lạ: {str(data)[:500]}") from exc

        usage = data.get("usage") or {}
        return LLMResponse(
            text=text or "",
            model=data.get("model", self._model),
            provider=self.name,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
