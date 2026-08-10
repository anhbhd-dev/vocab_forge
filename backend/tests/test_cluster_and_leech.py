"""Test confusion cluster (Agent 3 + tiền lọc) và xử lý leech (file 02 mục 4)."""

from __future__ import annotations

import random

import pytest
from sqlalchemy import select

from app.agents.factory import set_provider_override
from app.agents.providers.mock import MockProvider
from app.models.lexical import (
    ConfusionCluster,
    ConfusionClusterMember,
    ExampleSentence,
    LexicalItem,
    Mnemonic,
    Sense,
)
from app.models.srs import Card
from app.models.user import User
from app.services.cluster_service import (
    _blank_out,
    build_discrimination_exercise,
    maybe_run_cluster_batch,
)
from app.services.leech_service import regenerate_mnemonic
from app.services.similarity import SenseVector, group_similar_senses


class TestSimilarityPrefilter:
    def test_groups_near_synonyms(self):
        senses = [
            SenseVector("s1", "significant", "large enough to be noticed or important"),
            SenseVector("s2", "substantial", "large enough to be important or noticed"),
            SenseVector("s3", "detrimental", "causing harm or damage to health"),
        ]
        groups = group_similar_senses(senses, threshold=0.5)
        assert len(groups) == 1
        assert {s.sense_id for s in groups[0]} == {"s1", "s2"}

    def test_no_group_when_all_distinct(self):
        senses = [
            SenseVector("s1", "detrimental", "causing harm or damage"),
            SenseVector("s2", "urbanisation", "growth of cities and towns"),
            SenseVector("s3", "curriculum", "subjects taught in a school"),
        ]
        assert group_similar_senses(senses, threshold=0.75) == []

    def test_single_sense_returns_nothing(self):
        assert group_similar_senses([SenseVector("s1", "x", "y")]) == []

    def test_stopwords_do_not_create_false_matches(self):
        """Định nghĩa từ điển đầy 'to/of/the' — không được vì thế mà coi là cận nghĩa."""
        senses = [
            SenseVector("s1", "a", "to be in the state of the thing of a group"),
            SenseVector("s2", "b", "to be in the state of the thing of a group of it"),
        ]
        # Hai câu này gần trùng nhau thật nên PHẢI khớp; kiểm tra ngược lại:
        distinct = [
            SenseVector("s3", "c", "the process of moving to the city"),
            SenseVector("s4", "d", "a period of the year in the school"),
        ]
        assert group_similar_senses(senses, threshold=0.75)
        assert group_similar_senses(distinct, threshold=0.75) == []


class TestBlankOut:
    def test_exact_match(self):
        assert _blank_out("This is significant growth.", "significant") == (
            "This is _____ growth."
        )

    def test_case_insensitive(self):
        assert _blank_out("Significant growth", "significant") == "_____ growth"

    def test_split_collocation_falls_back_to_head_word(self):
        result = _blank_out(
            "Screen time has a detrimental effect on sleep.",
            "have a detrimental effect on",
        )
        assert result is not None and "_____" in result

    def test_returns_none_when_absent(self):
        assert _blank_out("Nothing here.", "xyzzy") is None


class TestClusterBatch:
    @pytest.fixture
    def cluster_provider(self):
        def handler(system_prompt, user_input):
            if "phân tích một nhóm" in system_prompt:
                ids = [s["sense_id"] for s in user_input["candidate_senses"]]
                return {
                    "clusters": [
                        {
                            "cluster_label": "Degree adjectives: 'large amount/degree'",
                            "members": [
                                {
                                    "sense_id": sid,
                                    "distinguishing_note": f"note cho {sid}",
                                }
                                for sid in ids
                            ],
                            "discrimination_exercise_hint": "điền từ vào chỗ trống",
                        }
                    ]
                }
            return {}

        provider = MockProvider(handler=handler)
        set_provider_override(provider)
        yield provider
        set_provider_override(None)

    async def test_batch_creates_cluster_and_practice_cards(
        self, session, cluster_provider
    ):
        user = await _make_user(session, "cluster@test.com")
        await _make_sense(
            session, user, "significant", "large enough to be noticed or important"
        )
        await _make_sense(
            session, user, "substantial", "large enough to be important or noticed"
        )
        await session.commit()

        created = await maybe_run_cluster_batch(session, user.id)
        await session.commit()
        assert created == 1

        members = (
            (
                await session.execute(
                    select(ConfusionClusterMember).join(
                        ConfusionCluster,
                        ConfusionCluster.id == ConfusionClusterMember.cluster_id,
                    ).where(ConfusionCluster.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(members) == 2
        assert all(m.distinguishing_note for m in members)

        practice_cards = (
            (
                await session.execute(
                    select(Card).where(
                        Card.user_id == user.id,
                        Card.card_direction == "cluster_discrimination",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(practice_cards) == 2

    async def test_skips_when_not_enough_new_senses(self, session, cluster_provider):
        user = await _make_user(session, "few@test.com")
        await _make_sense(session, user, "significant", "large enough to matter")
        await session.commit()
        assert await maybe_run_cluster_batch(session, user.id) == 0

    async def test_discrimination_exercise_needs_no_llm(
        self, session, cluster_provider
    ):
        user = await _make_user(session, "ex@test.com")
        s1 = await _make_sense(
            session, user, "significant", "large enough to be noticed or important"
        )
        await _make_sense(
            session, user, "substantial", "large enough to be important or noticed"
        )
        session.add(
            ExampleSentence(
                sense_id=s1.id,
                sentence="There was a significant increase in crime rates.",
                essay_type="opinion",
                source="agent_generated",
            )
        )
        await session.commit()
        await maybe_run_cluster_batch(session, user.id)
        await session.commit()

        cluster = (
            await session.execute(
                select(ConfusionCluster).where(ConfusionCluster.user_id == user.id)
            )
        ).scalar_one()

        calls_before = len(cluster_provider.calls)
        exercise = await build_discrimination_exercise(
            session, cluster.id, user.id, rng=random.Random(0)
        )
        assert exercise is not None
        assert "_____" in exercise["question_sentence"]
        assert len(exercise["options"]) == 2
        assert exercise["correct_sense_id"] == s1.id
        # Bài tập dựng từ dữ liệu có sẵn — không được gọi LLM.
        assert len(cluster_provider.calls) == calls_before

    async def test_exercise_returns_none_for_foreign_cluster(
        self, session, cluster_provider
    ):
        user = await _make_user(session, "owner@test.com")
        other = await _make_user(session, "other@test.com")
        cluster = ConfusionCluster(user_id=user.id, cluster_label="x")
        session.add(cluster)
        await session.commit()
        assert (
            await build_discrimination_exercise(session, cluster.id, other.id) is None
        )


class TestLeechHandling:
    async def test_regenerate_mnemonic_uses_different_approach(self, db_ready):
        from app.core.db import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            user = await _make_user(session, "leech@test.com")
            sense = await _make_sense(
                session, user, "abstract", "existing only as an idea, not physical"
            )
            session.add(
                Mnemonic(
                    sense_id=sense.id,
                    mnemonic_text="cách cũ không hiệu quả",
                    mnemonic_type="keyword_dual_coding",
                    generated_by_model="mock-model",
                )
            )
            await session.commit()
            sense_id = sense.id

        seen: dict = {}

        def handler(system_prompt, user_input):
            seen.update(user_input)
            return {
                "mnemonic_text": "cách tiếp cận hoàn toàn khác: gốc Latin abs-trahere",
                "mnemonic_type": "etymology",
            }

        provider = MockProvider(handler=handler)
        set_provider_override(provider)
        try:
            text = await regenerate_mnemonic(sense_id)
        finally:
            set_provider_override(None)

        assert text and "Latin" in text
        # Prompt phải biết đây là lần sinh lại và biết mnemonic cũ là gì.
        assert seen["is_regeneration"] is True
        assert seen["previous_mnemonic"] == "cách cũ không hiệu quả"

        async with AsyncSessionLocal() as session:
            rows = (
                (
                    await session.execute(
                        select(Mnemonic).where(Mnemonic.sense_id == sense_id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 2
            assert {r.mnemonic_type for r in rows} == {
                "keyword_dual_coding",
                "etymology",
            }

    async def test_regenerate_on_missing_sense_is_safe(self, db_ready):
        assert await regenerate_mnemonic("khong-ton-tai") is None


# ------------------------------------------------------------------ helpers
async def _make_user(session, email: str) -> User:
    user = User(email=email, password_hash="x")
    session.add(user)
    await session.flush()
    return user


async def _make_sense(session, user: User, surface_form: str, definition: str) -> Sense:
    item = LexicalItem(surface_form=surface_form, item_type="single_word")
    session.add(item)
    await session.flush()
    sense = Sense(lexical_item_id=item.id, definition_en=definition)
    session.add(sense)
    await session.flush()
    session.add(
        Card(
            sense_id=sense.id,
            user_id=user.id,
            card_direction="en_to_vi",
            state="new",
            due_at=None,
        )
    )
    await session.flush()
    return sense
