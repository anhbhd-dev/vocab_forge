"""Smoke test với LLM THẬT — chạy tay, không nằm trong pytest.

    python -m scripts.smoke_llm            # dùng provider trong .env
    python -m scripts.smoke_llm gemini     # ép provider cụ thể

Gọi đúng một lượt mỗi agent để kiểm chứng: API key hoạt động, model chịu trả JSON
thuần, và response khớp schema Pydantic.
"""

from __future__ import annotations

import asyncio
import json
import sys

from app.agents.base import AgentSchemaError, LLMError
from app.agents.context_agent import DEFAULT_ESSAY_TYPES, ContextAgent
from app.agents.extraction_agent import ExtractionAgent
from app.agents.factory import build_provider
from app.agents.mnemonic_agent import MnemonicAgent
from app.agents.production_grading_agent import ProductionGradingAgent
from app.agents.sense_agent import SenseAgent
from app.core.config import settings
from app.schemas.agent_io import (
    ContextInput,
    ExtractionInput,
    MnemonicInput,
    ProductionGradingInput,
    SenseInput,
)

READING = (
    "Excessive screen time among teenagers has a detrimental effect on both their "
    "sleep quality and academic performance. Governments should address this concern "
    "before it undermines public health across an entire generation."
)


async def main() -> int:
    provider_name = sys.argv[1] if len(sys.argv) > 1 else settings.llm_provider
    provider = build_provider(provider_name)
    print(f"Provider: {provider.name} / model {provider.model}\n")

    checks = [
        (
            "Extraction Agent",
            ExtractionAgent(provider=provider),
            ExtractionInput(text=READING, target_ielts_band=7.0),
        ),
        (
            "Sense Agent (mở rộng)",
            SenseAgent(provider=provider),
            SenseInput(
                surface_form="have a detrimental effect on",
                item_type="collocation",
                sentence_context=READING,
            ),
        ),
        (
            "Context Agent",
            ContextAgent(provider=provider),
            ContextInput(
                surface_form="have a detrimental effect on",
                definition_en="to cause harm or damage to something",
                essay_types=DEFAULT_ESSAY_TYPES,  # type: ignore[arg-type]
            ),
        ),
        (
            "Mnemonic Agent",
            MnemonicAgent(provider=provider),
            MnemonicInput(
                surface_form="detrimental",
                definition_en="causing harm or damage",
            ),
        ),
        (
            "Production Grading Agent",
            ProductionGradingAgent(provider=provider),
            ProductionGradingInput(
                target_surface_form="detrimental",
                target_definition="causing harm or damage",
                # Câu này sai giới từ ("for" thay vì "to") — agent phải bắt được
                # error_type = "collocation".
                user_sentence="Too much screen time is detrimental for teenagers.",
            ),
        ),
    ]

    failures = 0
    for label, agent, payload in checks:
        print(f"--- {label} ---")
        try:
            # session=None: bỏ qua agent_cache để lần nào cũng gọi thật.
            result = await agent.run(None, payload)
        except (LLMError, AgentSchemaError) as exc:
            failures += 1
            print(f"LỖI: {exc}\n")
            continue
        print(f"(model={result.model}, số lần thử={result.attempts})")
        print(
            json.dumps(result.output.model_dump(), ensure_ascii=False, indent=2)[:1500]
        )
        print()

    print("=" * 60)
    print(f"{len(checks) - failures}/{len(checks)} agent chạy được.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
