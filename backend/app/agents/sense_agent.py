"""Sense/Definition Agent — AGENT MỞ RỘNG, không có trong file 03.

VÌ SAO PHẢI CÓ (khoảng trống trong spec):
  - Output của Extraction Agent (file 03, Agent 1) chỉ có `surface_form`, `item_type`,
    `cefr_level`, `reason`, `sentence_context` — KHÔNG có định nghĩa.
  - Nhưng bảng `senses` (file 01) bắt buộc `definition_en NOT NULL`, và Context Agent
    (Agent 2) lại NHẬN `definition_en` làm input, Mnemonic Agent (Agent 4) cũng vậy.
  - Nghĩa là giữa "duyệt candidate" và "chạy Context/Mnemonic song song" (file 03 mục 6)
    còn thiếu đúng một bước sinh sense/definition. Agent này lấp bước đó.

Nó cũng trả về `needs_mnemonic` — chính là "heuristic từ khó hình dung" mà file 03
mục 6 nhắc tới ("có thể để LLM tự đánh giá"), dùng để quyết định có chạy Mnemonic Agent
hay không thay vì chạy cho mọi từ (tiết kiệm chi phí).

System prompt: `app/agents/prompts.py::SENSE_SYSTEM_PROMPT`.
"""

from __future__ import annotations

from app.agents.prompts import SENSE_SYSTEM_PROMPT
from app.agents.runner import BaseAgent
from app.schemas.agent_io import SenseInput, SenseOutput


class SenseAgent(BaseAgent[SenseInput, SenseOutput]):
    agent_name = "sense"
    system_prompt = SENSE_SYSTEM_PROMPT
    input_model = SenseInput
    output_model = SenseOutput
