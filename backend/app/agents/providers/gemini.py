"""Gemini provider — dùng làm dự phòng/đối chiếu (file 00 mục 3)."""

from __future__ import annotations

from typing import Any

import httpx

from app.agents.base import LLMError, LLMProvider, LLMResponse
from app.core.config import settings


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.gemini_api_key
        self._base_url = (base_url or settings.gemini_base_url).rstrip("/")
        self._model = model or settings.gemini_model
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
                "Thiếu GEMINI_API_KEY — đặt biến môi trường hoặc đổi LLM_PROVIDER."
            )

        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": self._render_user_message(
                                user_input, response_schema
                            )
                        }
                    ],
                }
            ],
            # Chỉ bật JSON mime type, KHÔNG truyền responseSchema: Gemini chỉ chấp nhận
            # một tập con OpenAPI (không hỗ trợ $defs/anyOf phức tạp mà Pydantic sinh
            # ra), truyền vào sẽ bị 400. Schema đã được nhắc trong prompt qua
            # `_render_user_message`, phần validate chặt do runner.py đảm nhiệm.
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.7,
            },
        }

        url = f"{self._base_url}/models/{self._model}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    url,
                    headers={
                        "x-goog-api-key": self._api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise LLMError(f"Gemini network error: {exc}") from exc

        if resp.status_code >= 400:
            raise LLMError(f"Gemini HTTP {resp.status_code}: {resp.text[:500]}")

        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Gemini trả response lạ: {str(data)[:500]}") from exc

        usage = data.get("usageMetadata") or {}
        return LLMResponse(
            text=text,
            model=self._model,
            provider=self.name,
            prompt_tokens=usage.get("promptTokenCount"),
            completion_tokens=usage.get("candidatesTokenCount"),
        )
