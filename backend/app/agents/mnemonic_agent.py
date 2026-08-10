"""Mnemonic Agent.

Implement: `docs/03_AI_AGENTS_SPEC_VA_PROMPT.md` → mục "Agent 4: Mnemonic Agent".
System prompt: `app/agents/prompts.py::MNEMONIC_SYSTEM_PROMPT` (copy nguyên văn).

Được gọi ở 2 chỗ:
  1. Enrichment pipeline, chỉ khi từ được đánh giá "khó hình dung" (file 03 mục 6).
  2. Khi thẻ vừa bị đánh dấu leech — sinh mnemonic MỚI, cách tiếp cận khác hẳn
     (file 02 mục 4), qua `is_regeneration=True`.
"""

from __future__ import annotations

from typing import Any

from app.agents.prompts import MNEMONIC_SYSTEM_PROMPT
from app.agents.runner import BaseAgent
from app.schemas.agent_io import MnemonicInput, MnemonicOutput


class MnemonicAgent(BaseAgent[MnemonicInput, MnemonicOutput]):
    agent_name = "mnemonic"
    system_prompt = MNEMONIC_SYSTEM_PROMPT
    input_model = MnemonicInput
    output_model = MnemonicOutput

    def is_cacheable(self, payload: MnemonicInput) -> bool:
        # Lần regenerate KHÔNG được đọc cache: mục đích của nó là tạo ra cách tiếp cận
        # khác với mnemonic cũ, mà cache thì luôn trả lại đúng cái cũ.
        return not payload.is_regeneration

    def cache_payload(self, payload: MnemonicInput) -> Any:
        return {
            "surface_form": payload.surface_form,
            "definition_en": payload.definition_en,
        }
