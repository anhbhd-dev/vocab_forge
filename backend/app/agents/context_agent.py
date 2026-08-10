"""Context Generation Agent.

Implement: `docs/03_AI_AGENTS_SPEC_VA_PROMPT.md` → mục "Agent 2: Context Generation
Agent". System prompt: `app/agents/prompts.py::CONTEXT_SYSTEM_PROMPT` (copy nguyên văn).
"""

from __future__ import annotations

from app.agents.prompts import CONTEXT_SYSTEM_PROMPT
from app.agents.runner import BaseAgent
from app.schemas.agent_io import ContextInput, ContextOutput

# File 03 mục 6: mỗi item được duyệt sinh 3-4 example_sentences.
DEFAULT_ESSAY_TYPES = ["opinion", "discussion", "problem_solution", "advantage_disadvantage"]


class ContextAgent(BaseAgent[ContextInput, ContextOutput]):
    agent_name = "context"
    system_prompt = CONTEXT_SYSTEM_PROMPT
    input_model = ContextInput
    output_model = ContextOutput
