"""Test API end-to-end với MockProvider — không gọi mạng.

Bao trọn luồng file 03 mục 6: import bài đọc → Extraction → user duyệt → enrichment
song song → cards → review → production grading → analytics.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents.providers.mock import MockProvider
from app.agents.factory import set_provider_override
from app.models.srs import Card

READING = """
Excessive screen time among teenagers has a detrimental effect on both their sleep
quality and academic performance. Governments should address this concern before it
undermines public health.
"""


def scripted_provider() -> MockProvider:
    """Provider trả lời theo từng agent, đủ để chạy hết pipeline."""

    def handler(system_prompt: str, _user_input):
        if "trích xuất các đơn vị từ vựng" in system_prompt:
            return {
                "candidates": [
                    {
                        "surface_form": "have a detrimental effect on",
                        "item_type": "collocation",
                        "cefr_level": "C1",
                        "reason": "collocation academic tần suất cao",
                        "sentence_context": (
                            "Excessive screen time among teenagers has a detrimental "
                            "effect on both their sleep quality and academic performance."
                        ),
                    },
                    {
                        "surface_form": "address a concern",
                        "item_type": "collocation",
                        "cefr_level": "B2",
                        "reason": "'address' nghĩa academic khó đoán",
                        "sentence_context": "Governments should address this concern.",
                    },
                ]
            }
        if "biên soạn từ điển học thuật" in system_prompt:
            return {
                "senses": [
                    {
                        "definition_en": "to cause harm or damage to something",
                        "definition_vi": "gây tác động tiêu cực tới",
                        "part_of_speech": "verb phrase",
                        "register": "academic",
                        "needs_mnemonic": True,
                    }
                ]
            }
        if "viết câu ví dụ minh" in system_prompt:
            return {
                "examples": [
                    {
                        "sentence": (
                            "Prolonged exposure to air pollution has a detrimental "
                            "effect on the respiratory health of urban residents."
                        ),
                        "essay_type": "problem_solution",
                    },
                    {
                        "sentence": (
                            "In my view, unregulated tourism has a detrimental effect "
                            "on fragile coastal ecosystems across the region."
                        ),
                        "essay_type": "opinion",
                    },
                ]
            }
        if "kỹ thuật ghi nhớ" in system_prompt:
            return {
                "mnemonic_text": "detrimental ~ 'đe doạ mental': màn hình phát sáng bào mòn não.",
                "mnemonic_type": "keyword_dual_coding",
            }
        if "phân tích một nhóm" in system_prompt:
            return {"clusters": []}
        if "giám khảo chấm IELTS Writing" in system_prompt:
            return {
                "is_correct": False,
                "error_type": "collocation",
                "feedback_text": 'Sai giới từ: "detrimental for" nên là "detrimental to".',
                "corrected_sentence": "Smoking is detrimental to health.",
            }
        return {}

    return MockProvider(handler=handler)


@pytest.fixture
def scripted():
    provider = scripted_provider()
    set_provider_override(provider)
    yield provider
    set_provider_override(None)


class TestAuth:
    async def test_register_login_and_me(self, client):
        resp = await client.post(
            "/api/auth/register", json={"email": "a@b.com", "password": "secret123"}
        )
        assert resp.status_code == 201

        dup = await client.post(
            "/api/auth/register", json={"email": "a@b.com", "password": "secret123"}
        )
        assert dup.status_code == 409

        login = await client.post(
            "/api/auth/login", json={"email": "a@b.com", "password": "secret123"}
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        me = await client.get(
            "/api/users/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me.status_code == 200
        assert me.json()["email"] == "a@b.com"

    async def test_wrong_password_rejected(self, client):
        await client.post(
            "/api/auth/register", json={"email": "c@d.com", "password": "secret123"}
        )
        resp = await client.post(
            "/api/auth/login", json={"email": "c@d.com", "password": "wrongpass"}
        )
        assert resp.status_code == 401

    async def test_protected_endpoint_requires_token(self, client):
        assert (await client.get("/api/review/queue")).status_code == 401

    async def test_update_settings(self, auth_client):
        resp = await auth_client.patch(
            "/api/users/me/settings", json={"daily_new_word_goal": 25}
        )
        assert resp.status_code == 200
        assert resp.json()["daily_new_word_goal"] == 25


class TestFullPipeline:
    async def test_ingest_approve_enrich_review(self, auth_client, scripted, session):
        # --- 1. Tạo deck ---
        deck = await auth_client.post(
            "/api/decks", json={"name": "IELTS Reading", "description": "bài đọc"}
        )
        assert deck.status_code == 201
        deck_id = deck.json()["id"]

        # --- 2. Import bài đọc (Extraction chạy nền) ---
        job_resp = await auth_client.post(
            "/api/ingestion/jobs",
            json={
                "source_type": "pasted_text",
                "raw_text": READING,
                "deck_id": deck_id,
            },
        )
        assert job_resp.status_code == 202
        job_id = job_resp.json()["job_id"]

        status = await auth_client.get(f"/api/ingestion/jobs/{job_id}")
        assert status.json()["status"] == "done"
        assert status.json()["awaiting_approval"] is True
        assert status.json()["candidate_count"] == 2

        # --- 3. Xem candidates ---
        candidates = (
            await auth_client.get(f"/api/ingestion/jobs/{job_id}/candidates")
        ).json()
        assert len(candidates) == 2
        assert candidates[0]["reason"]
        assert all(c["is_approved"] is False for c in candidates)

        # --- 4. User duyệt CHỈ 1 từ (không tự động thêm hết) ---
        chosen = candidates[0]["lexical_item_id"]
        approve = await auth_client.post(
            f"/api/ingestion/jobs/{job_id}/approve",
            json={"selected_lexical_item_ids": [chosen]},
        )
        assert approve.status_code == 202

        final = (await auth_client.get(f"/api/ingestion/jobs/{job_id}")).json()
        assert final["status"] == "done"
        assert final["approved_count"] == 1

        # --- 5. Item đã được enrich: sense + ví dụ + mnemonic ---
        detail = (await auth_client.get(f"/api/lexical-items/{chosen}")).json()
        assert len(detail["senses"]) == 1
        sense = detail["senses"][0]
        assert sense["definition_en"]
        sources = {e["source"] for e in sense["examples"]}
        # Câu gốc trong bài đọc phải được giữ lại, không chỉ câu agent sinh.
        assert sources == {"user_reading", "agent_generated"}
        assert len(sense["mnemonics"]) == 1

        # --- 6. Từ chưa duyệt KHÔNG được enrich ---
        skipped = candidates[1]["lexical_item_id"]
        skipped_detail = (
            await auth_client.get(f"/api/lexical-items/{skipped}")
        ).json()
        assert skipped_detail["senses"] == []

        # --- 7. Cards đã sẵn sàng trong hàng đợi ---
        queue = (await auth_client.get("/api/review/queue?limit=30")).json()
        assert queue["cards"], "phải có thẻ để ôn sau khi enrich"
        card = queue["cards"][0]
        assert card["definition_en"]
        assert card["examples"]
        assert card["interval_preview_days"]["good"] > 0
        # production card chưa được phát vì thẻ nhận diện chưa tốt nghiệp
        assert {c["card_direction"] for c in queue["cards"]} <= {
            "en_to_vi",
            "vi_to_en",
        }

        # --- 8. Trả lời thẻ (fast path) ---
        answer = await auth_client.post(
            f"/api/review/cards/{card['id']}/answer", json={"rating": 3}
        )
        assert answer.status_code == 200
        body = answer.json()
        assert body["state"] == "learning"
        assert body["reps"] == 1
        assert body["due_at"] > card["due_at"]

        # --- 9. Stats ---
        stats = (await auth_client.get("/api/review/stats")).json()
        assert stats["reviewed_today"] == 1
        assert stats["streak_days"] == 1
        assert stats["total_cards"] >= 3

    async def test_error_type_answer_is_logged_and_adjusts(
        self, auth_client, scripted, session
    ):
        await _seed_one_item(auth_client)
        queue = (await auth_client.get("/api/review/queue")).json()
        card_id = queue["cards"][0]["id"]

        # Đưa thẻ lên state review trước
        for _ in range(4):
            await auth_client.post(
                f"/api/review/cards/{card_id}/answer", json={"rating": 4}
            )

        card = await session.get(Card, card_id)
        await session.refresh(card)
        assert card.state == "review"

        resp = await auth_client.post(
            f"/api/review/cards/{card_id}/answer",
            json={"rating": 1, "error_type": "spelling"},
        )
        body = resp.json()
        # Lỗi chính tả không phải quên nghĩa → giữ lịch, không tính lapse.
        assert body["lapses"] == 0
        assert body["state"] == "review"
        assert body["adjustments"]

    async def test_review_endpoint_never_calls_llm(self, auth_client, scripted):
        """file 04 yêu cầu #2 — fast path tuyệt đối không gọi LLM."""
        await _seed_one_item(auth_client)
        queue = (await auth_client.get("/api/review/queue")).json()
        calls_before = len(scripted.calls)

        await auth_client.get("/api/review/queue")
        await auth_client.post(
            f"/api/review/cards/{queue['cards'][0]['id']}/answer", json={"rating": 3}
        )
        await auth_client.get("/api/review/stats")

        assert len(scripted.calls) == calls_before


class TestProductionGrading:
    async def test_attempt_is_graded_in_background(self, auth_client, scripted):
        await _seed_one_item(auth_client)
        queue = (await auth_client.get("/api/review/queue")).json()
        card_id = queue["cards"][0]["id"]

        resp = await auth_client.post(
            "/api/production/attempts",
            json={"card_id": card_id, "user_sentence": "Smoking is detrimental for health."},
        )
        assert resp.status_code == 202
        attempt_id = resp.json()["attempt_id"]

        graded = (
            await auth_client.get(f"/api/production/attempts/{attempt_id}")
        ).json()
        assert graded["status"] == "graded"
        assert graded["error_type"] == "collocation"
        assert graded["corrected_sentence"]
        assert graded["is_correct"] is False

    async def test_empty_sentence_rejected(self, auth_client, scripted):
        await _seed_one_item(auth_client)
        queue = (await auth_client.get("/api/review/queue")).json()
        resp = await auth_client.post(
            "/api/production/attempts",
            json={"card_id": queue["cards"][0]["id"], "user_sentence": "   "},
        )
        assert resp.status_code == 422


class TestAnalytics:
    async def test_overview_and_error_breakdown(self, auth_client, scripted):
        await _seed_one_item(auth_client)
        queue = (await auth_client.get("/api/review/queue")).json()
        card_id = queue["cards"][0]["id"]
        await auth_client.post(
            f"/api/review/cards/{card_id}/answer",
            json={"rating": 2, "error_type": "collocation"},
        )

        overview = (await auth_client.get("/api/analytics/overview")).json()
        assert overview["total_cards"] >= 3
        assert overview["ramp_up"]["action"] in ("raise", "hold", "lower")
        assert any(c["agent_name"] == "context" for c in overview["agent_cache"])

        breakdown = (await auth_client.get("/api/analytics/error-breakdown")).json()
        types = {e["error_type"] for e in breakdown["review_errors"]}
        assert "collocation" in types

    async def test_leeches_endpoint(self, auth_client, scripted):
        assert (await auth_client.get("/api/analytics/leeches")).json() == []


class TestManualItem:
    async def test_manual_add_triggers_enrichment(self, auth_client, scripted):
        resp = await auth_client.post(
            "/api/lexical-items",
            json={"surface_form": "substantial contribution", "item_type": "collocation"},
        )
        assert resp.status_code == 202
        item_id = resp.json()["lexical_item_id"]

        detail = (await auth_client.get(f"/api/lexical-items/{item_id}")).json()
        assert detail["senses"], "enrichment nền phải chạy xong"
        assert detail["senses"][0]["examples"]


async def _seed_one_item(auth_client) -> str:
    """Tạo nhanh một lexical item đã enrich để test các luồng phía sau."""
    resp = await auth_client.post(
        "/api/lexical-items",
        json={"surface_form": "have a detrimental effect on", "item_type": "collocation"},
    )
    return resp.json()["lexical_item_id"]
