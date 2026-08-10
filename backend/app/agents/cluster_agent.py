"""Confusion Cluster Agent.

Implement: `docs/03_AI_AGENTS_SPEC_VA_PROMPT.md` → mục "Agent 3: Confusion Cluster
Agent". System prompt: `app/agents/prompts.py::CLUSTER_SYSTEM_PROMPT` (copy nguyên văn).

Bước tiền lọc bằng similarity (ghi chú kỹ thuật cuối mục Agent 3) nằm ở
`app/services/similarity.py` — LLM chỉ nhận các nhóm đã được lọc, không nhận cả deck.
"""

from __future__ import annotations

from app.agents.prompts import CLUSTER_SYSTEM_PROMPT
from app.agents.runner import BaseAgent
from app.schemas.agent_io import ClusterInput, ClusterOutput


class ClusterAgent(BaseAgent[ClusterInput, ClusterOutput]):
    agent_name = "cluster"
    system_prompt = CLUSTER_SYSTEM_PROMPT
    input_model = ClusterInput
    output_model = ClusterOutput

    def is_cacheable(self, payload: ClusterInput) -> bool:
        # Input chứa `sense_id` (khác nhau giữa các user cho cùng một từ) nên cache
        # gần như không bao giờ hit, mà lại phình bảng. Tắt cache cho agent này.
        return False
