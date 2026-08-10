"""Extraction Agent.

Implement: `docs/03_AI_AGENTS_SPEC_VA_PROMPT.md` → mục "Agent 1: Extraction Agent".
System prompt: `app/agents/prompts.py::EXTRACTION_SYSTEM_PROMPT` (copy nguyên văn).
"""

from __future__ import annotations

from typing import Any

from app.agents.prompts import EXTRACTION_SYSTEM_PROMPT
from app.agents.runner import BaseAgent
from app.schemas.agent_io import ExtractionInput, ExtractionOutput

MAX_CANDIDATES = 15  # file 03, Agent 1, nguyên tắc #6


class ExtractionAgent(BaseAgent[ExtractionInput, ExtractionOutput]):
    agent_name = "extraction"
    system_prompt = EXTRACTION_SYSTEM_PROMPT
    input_model = ExtractionInput
    output_model = ExtractionOutput

    def cache_payload(self, payload: ExtractionInput) -> Any:
        # `existing_items` bị loại khỏi cache key: nó chỉ để agent tránh trùng deck của
        # riêng user, không đổi bản chất "bài đọc này có những cụm nào đáng học". Giữ
        # nó trong key sẽ khiến 2 user cùng dán một bài đọc không bao giờ share cache.
        # Bù lại, kết quả cache được lọc lại theo existing_items ở `run_filtered`.
        #
        # Khoảng band thì BẮT BUỘC phải nằm trong key: cùng một bài đọc nhưng quét band
        # 5–6 và band 7–8 phải ra hai tập từ khác nhau. Thiếu nó thì lần quét thứ hai sẽ
        # ăn cache của lần đầu và trả về sai mức độ.
        return {
            "text": payload.text,
            "band_min": payload.band_min,
            "band_max": payload.band_max,
        }

    async def run_filtered(
        self, session, payload: ExtractionInput, use_cache: bool = True
    ) -> ExtractionOutput:
        """Chạy agent rồi áp lại 2 ràng buộc mà spec yêu cầu ở phía kết quả:
        loại trùng `existing_items` và cắt còn tối đa 15 ứng viên."""
        result = await self.run(session, payload, use_cache=use_cache)
        existing = {_normalize(s) for s in payload.existing_items}

        kept = []
        seen: set[str] = set()
        for candidate in result.output.candidates:
            key = _normalize(candidate.surface_form)
            if not key or key in existing or key in seen:
                continue
            seen.add(key)
            kept.append(candidate)
            if len(kept) >= MAX_CANDIDATES:
                break
        return ExtractionOutput(candidates=kept)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())
