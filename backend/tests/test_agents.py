"""Test tầng agent: prompt trung thành với spec, cache, retry, provider pattern."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.agents.base import AgentSchemaError, LLMError, LLMResponse
from app.agents.cache import make_cache_key, normalize_input
from app.agents.context_agent import ContextAgent
from app.agents.extraction_agent import ExtractionAgent
from app.agents.factory import FallbackProvider, build_provider
from app.agents.mnemonic_agent import MnemonicAgent
from app.agents.production_grading_agent import ProductionGradingAgent
from app.agents.providers.deepseek import DeepSeekProvider
from app.agents.providers.gemini import GeminiProvider
from app.agents.providers.mock import MockProvider
from app.agents.runner import extract_json
from app.schemas.agent_io import (
    ContextInput,
    ExtractionInput,
    MnemonicInput,
    ProductionGradingInput,
)

SPEC = Path(__file__).resolve().parents[2] / "docs" / "03_AI_AGENTS_SPEC_VA_PROMPT.md"


class TestPromptFidelity:
    """File 04 yêu cầu #4: system prompt phải COPY CHÍNH XÁC từ spec."""

    def test_prompts_match_spec_file_verbatim(self):
        from app.agents import prompts

        blocks = re.findall(
            r"### System prompt:\n\n```\n(.*?)\n```", SPEC.read_text(), re.S
        )
        assert len(blocks) == 5, "spec phải có đúng 5 system prompt"

        expected = dict(
            zip(
                [
                    prompts.EXTRACTION_SYSTEM_PROMPT,
                    prompts.CONTEXT_SYSTEM_PROMPT,
                    prompts.CLUSTER_SYSTEM_PROMPT,
                    prompts.MNEMONIC_SYSTEM_PROMPT,
                    prompts.PRODUCTION_GRADING_SYSTEM_PROMPT,
                ],
                blocks,
            )
        )
        for actual, spec_text in expected.items():
            assert actual.strip() == spec_text.strip()

    def test_every_agent_docstring_cites_the_spec(self):
        from app.agents import (
            cluster_agent,
            context_agent,
            extraction_agent,
            mnemonic_agent,
            production_grading_agent,
        )

        # File 04 yêu cầu #8: mỗi file agent trích dẫn đúng mục trong file 03.
        for module in (
            extraction_agent,
            context_agent,
            cluster_agent,
            mnemonic_agent,
            production_grading_agent,
        ):
            assert "03_AI_AGENTS_SPEC_VA_PROMPT.md" in (module.__doc__ or "")


class TestJSONExtraction:
    def test_plain_json(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_markdown_fenced(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_with_preamble(self):
        assert extract_json('Đây là kết quả:\n{"a": 1}\nHy vọng giúp ích') == {"a": 1}

    def test_garbage_raises(self):
        with pytest.raises(json.JSONDecodeError):
            extract_json("không có json ở đây")


class TestCacheKey:
    def test_normalization_is_stable(self):
        assert normalize_input({"b": 1, "a": 2}) == normalize_input({"a": 2, "b": 1})
        assert normalize_input("  Detrimental   Effect ") == "detrimental effect"

    def test_same_input_same_key(self):
        a = make_cache_key("context", {"surface_form": "X"}, 7.0)
        b = make_cache_key("context", {"surface_form": "X"}, 7.0)
        assert a == b

    def test_band_changes_key(self):
        a = make_cache_key("context", {"surface_form": "X"}, 7.0)
        b = make_cache_key("context", {"surface_form": "X"}, 8.0)
        assert a != b


class TestRunnerBehaviour:
    async def test_retries_then_succeeds(self, session):
        """Sai schema 1 lần → retry → thành công (file 04 yêu cầu #4)."""
        attempts = {"n": 0}

        def handler(_system, _user):
            attempts["n"] += 1
            if attempts["n"] == 1:
                return {"wrong_key": []}
            return {
                "examples": [
                    {"sentence": "A" * 30, "essay_type": "opinion"}
                ]
            }

        agent = ContextAgent(provider=MockProvider(handler=handler))
        result = await agent.run(
            session,
            ContextInput(
                surface_form="have a detrimental effect on",
                definition_en="to harm",
                essay_types=["opinion"],
            ),
        )
        assert attempts["n"] == 2
        assert result.attempts == 2
        assert len(result.output.examples) == 1

    async def test_raises_after_retry_budget(self, session):
        agent = ContextAgent(
            provider=MockProvider(handler=lambda *_: {"nope": True})
        )
        with pytest.raises(AgentSchemaError) as exc:
            await agent.run(
                session,
                ContextInput(
                    surface_form="x", definition_en="y", essay_types=["opinion"]
                ),
            )
        assert "không trả về JSON hợp lệ" in str(exc.value)

    async def test_cache_prevents_second_llm_call(self, session):
        """File 03 mục 0: mọi response phải qua cache TRƯỚC khi gọi LLM thật."""
        calls = {"n": 0}

        def handler(_s, _u):
            calls["n"] += 1
            return {"examples": [{"sentence": "S" * 30, "essay_type": "opinion"}]}

        provider = MockProvider(handler=handler)
        payload = ContextInput(
            surface_form="substantial increase",
            definition_en="a large rise",
            essay_types=["opinion"],
        )

        first = await ContextAgent(provider=provider).run(session, payload)
        await session.commit()
        second = await ContextAgent(provider=provider).run(session, payload)

        assert calls["n"] == 1
        assert first.from_cache is False
        assert second.from_cache is True
        assert second.output.examples[0].sentence == first.output.examples[0].sentence

    async def test_mnemonic_regeneration_bypasses_cache(self, session):
        """File 02 mục 4: sinh lại mnemonic phải KHÁC cách cũ → không được đọc cache."""
        outputs = iter(
            [
                {"mnemonic_text": "cách cũ", "mnemonic_type": "keyword_dual_coding"},
                {"mnemonic_text": "cách mới hẳn", "mnemonic_type": "story_link"},
            ]
        )
        provider = MockProvider(handler=lambda *_: next(outputs))
        agent = MnemonicAgent(provider=provider)

        first = await agent.run(
            session, MnemonicInput(surface_form="abstract", definition_en="not concrete")
        )
        await session.commit()
        second = await agent.run(
            session,
            MnemonicInput(
                surface_form="abstract",
                definition_en="not concrete",
                is_regeneration=True,
                previous_mnemonic=first.output.mnemonic_text,
            ),
        )
        assert second.from_cache is False
        assert second.output.mnemonic_text != first.output.mnemonic_text

    async def test_production_grading_is_not_cached(self, session):
        calls = {"n": 0}

        def handler(_s, _u):
            calls["n"] += 1
            return {
                "is_correct": False,
                "error_type": "collocation",
                "feedback_text": 'Sai giới từ: "detrimental for" → "detrimental to".',
                "corrected_sentence": "It is detrimental to health.",
            }

        agent = ProductionGradingAgent(provider=MockProvider(handler=handler))
        payload = ProductionGradingInput(
            target_surface_form="detrimental",
            target_definition="harmful",
            user_sentence="It is detrimental for health.",
        )
        await agent.run(session, payload)
        await agent.run(session, payload)
        assert calls["n"] == 2


class TestExtractionFiltering:
    async def test_drops_existing_items_and_caps_at_fifteen(self, session):
        many = {
            "candidates": [
                {
                    "surface_form": f"collocation number {i}",
                    "item_type": "collocation",
                    "cefr_level": "C1",
                    "reason": "test",
                    "sentence_context": None,
                }
                for i in range(25)
            ]
            + [
                {
                    "surface_form": "Already Known",
                    "item_type": "single_word",
                    "cefr_level": "B2",
                    "reason": "test",
                    "sentence_context": None,
                }
            ]
        }
        agent = ExtractionAgent(provider=MockProvider(handler=lambda *_: many))
        output = await agent.run_filtered(
            session,
            ExtractionInput(
                text="bài đọc mẫu",
                target_ielts_band=7.0,
                existing_items=["already known"],
            ),
        )
        assert len(output.candidates) == 15
        forms = {c.surface_form.lower() for c in output.candidates}
        assert "already known" not in forms


class TestProviderPattern:
    def test_factory_builds_each_provider(self):
        assert isinstance(build_provider("deepseek"), DeepSeekProvider)
        assert isinstance(build_provider("gemini"), GeminiProvider)
        assert isinstance(build_provider("mock"), MockProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(LLMError):
            build_provider("chatgpt-5000")

    async def test_missing_api_key_raises_clear_error(self):
        provider = DeepSeekProvider(api_key="")
        with pytest.raises(LLMError) as exc:
            await provider.complete("system", {"a": 1})
        assert "DEEPSEEK_API_KEY" in str(exc.value)

    async def test_fallback_switches_provider_on_failure(self):
        class Broken(MockProvider):
            async def complete(self, *_args, **_kwargs):
                raise LLMError("provider chính chết")

        secondary = MockProvider(handler=lambda *_: {"ok": True})
        provider = FallbackProvider(Broken(), secondary)
        response = await provider.complete("system", {"x": 1})
        assert isinstance(response, LLMResponse)
        assert provider.last_used is secondary

    def test_schema_is_included_in_user_message(self):
        rendered = MockProvider()._render_user_message(
            {"surface_form": "x"}, {"type": "object"}
        )
        assert "OUTPUT JSON SCHEMA" in rendered
        assert "surface_form" in rendered
