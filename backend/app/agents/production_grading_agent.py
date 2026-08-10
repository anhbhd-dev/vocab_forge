"""Production Grading Agent.

Implement: `docs/03_AI_AGENTS_SPEC_VA_PROMPT.md` → mục "Agent 5: Production Grading
Agent". System prompt: `app/agents/prompts.py::PRODUCTION_GRADING_SYSTEM_PROMPT`
(copy nguyên văn).

Đây là NGOẠI LỆ duy nhất được gọi LLM trong lúc user đang tương tác (file 00 mục 4.2):
endpoint trả `attempt_id` ngay, việc chấm chạy nền, UI poll lại — vòng review không bị
chặn.
"""

from __future__ import annotations

from app.agents.prompts import PRODUCTION_GRADING_SYSTEM_PROMPT
from app.agents.runner import BaseAgent
from app.schemas.agent_io import ProductionGradingInput, ProductionGradingOutput


class ProductionGradingAgent(BaseAgent[ProductionGradingInput, ProductionGradingOutput]):
    agent_name = "production_grading"
    system_prompt = PRODUCTION_GRADING_SYSTEM_PROMPT
    input_model = ProductionGradingInput
    output_model = ProductionGradingOutput

    def is_cacheable(self, payload: ProductionGradingInput) -> bool:
        # Câu do user tự viết gần như không lặp lại giữa các lần/giữa user, cache chỉ
        # làm phình bảng mà không tiết kiệm được gì.
        return False
