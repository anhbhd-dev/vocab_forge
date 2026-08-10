"""Khung chạy chung cho mọi agent: cache → gọi LLM → parse → validate → retry.

Triển khai file 04 yêu cầu #4:
  - Cache lookup TRƯỚC khi gọi LLM.
  - Response validate bằng Pydantic; JSON không khớp schema → retry tối đa 2 lần với
    prompt nhắc lại yêu cầu format; sau đó raise lỗi rõ ràng.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentSchemaError, LLMProvider
from app.agents.cache import get_cached, make_cache_key, store_cached
from app.agents.factory import get_provider
from app.core.config import settings

logger = logging.getLogger(__name__)

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def extract_json(text: str) -> Any:
    """Lấy JSON object từ response.

    Spec yêu cầu LLM trả JSON thuần, nhưng thực tế model vẫn thỉnh thoảng bọc markdown
    hoặc thêm lời dẫn — dọn ở đây thay vì để retry tốn thêm một lượt gọi.
    """
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        return json.loads(cleaned[start : end + 1])
    raise json.JSONDecodeError("Không tìm thấy JSON object trong response", cleaned, 0)


@dataclass
class AgentResult(Generic[OutputT]):
    output: OutputT
    model: str
    from_cache: bool = False
    attempts: int = 1


class BaseAgent(Generic[InputT, OutputT]):
    """Lớp cha cho 5 agent trong file 03 (+ Sense Agent mở rộng)."""

    agent_name: str = "base"
    system_prompt: str = ""
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider

    @property
    def provider(self) -> LLMProvider:
        # Lấy provider lười (lazy) để test có thể override sau khi agent đã khởi tạo.
        return self._provider or get_provider()

    # -------------------------------------------------------------- overridable

    def cache_payload(self, payload: InputT) -> Any:
        """Phần input tham gia vào cache key.

        Mặc định là toàn bộ input. Agent nào có trường không ảnh hưởng kết quả
        (vd `existing_items` của Extraction) thì override để tăng tỉ lệ cache hit.
        """
        return payload.model_dump()

    def target_band(self, payload: InputT) -> float | None:
        return getattr(payload, "target_ielts_band", None)

    def is_cacheable(self, payload: InputT) -> bool:
        return True

    # ---------------------------------------------------------------- main call

    async def run(
        self,
        session: AsyncSession | None,
        payload: InputT,
        use_cache: bool = True,
    ) -> AgentResult[OutputT]:
        cache_key = make_cache_key(
            self.agent_name, self.cache_payload(payload), self.target_band(payload)
        )
        cacheable = use_cache and session is not None and self.is_cacheable(payload)

        if cacheable:
            cached = await get_cached(session, cache_key)  # type: ignore[arg-type]
            if cached is not None:
                envelope = cached if isinstance(cached, dict) else {}
                data = envelope.get("output", cached)
                try:
                    return AgentResult(
                        output=self.output_model.model_validate(data),  # type: ignore[return-value]
                        model=envelope.get("model", "cache"),
                        from_cache=True,
                        attempts=0,
                    )
                except ValidationError:
                    logger.warning(
                        "agent_cache entry hỏng schema, bỏ qua: %s/%s",
                        self.agent_name,
                        cache_key[:12],
                    )

        schema = self.output_model.model_json_schema()
        user_input: str | dict[str, Any] = payload.model_dump()
        last_error: str | None = None

        # 1 lần gọi đầu + `llm_schema_retries` lần retry (mặc định 2).
        for attempt in range(1, settings.llm_schema_retries + 2):
            message: str | dict[str, Any] = user_input
            if last_error:
                message = (
                    f"{json.dumps(payload.model_dump(), ensure_ascii=False, indent=2)}\n\n"
                    f"LẦN TRƯỚC BẠN TRẢ VỀ SAI ĐỊNH DẠNG: {last_error}\n"
                    "Hãy trả về CHỈ một JSON object hợp lệ khớp CHÍNH XÁC schema đã "
                    "cho. Không markdown, không code block, không lời dẫn."
                )

            response = await self.provider.complete(
                self.system_prompt, message, schema
            )

            try:
                data = extract_json(response.text)
            except json.JSONDecodeError as exc:
                last_error = f"không parse được JSON ({exc.msg})"
                logger.warning(
                    "%s attempt %d: %s", self.agent_name, attempt, last_error
                )
                continue

            try:
                output = self.output_model.model_validate(data)
            except ValidationError as exc:
                last_error = f"JSON không khớp schema: {exc.errors()[:3]}"
                logger.warning(
                    "%s attempt %d: %s", self.agent_name, attempt, last_error
                )
                continue

            if cacheable:
                await store_cached(
                    session,  # type: ignore[arg-type]
                    cache_key,
                    self.agent_name,
                    {"output": output.model_dump(), "model": response.model},
                )

            return AgentResult(
                output=output,  # type: ignore[arg-type]
                model=response.model,
                from_cache=False,
                attempts=attempt,
            )

        raise AgentSchemaError(
            f"{self.agent_name}: LLM không trả về JSON hợp lệ sau "
            f"{settings.llm_schema_retries + 1} lần thử. Lỗi cuối: {last_error}"
        )
