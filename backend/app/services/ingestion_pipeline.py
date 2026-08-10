"""Orchestration của enrichment pipeline — file 03 mục 6.

    User import bài đọc
          │
          ▼
    [Extraction Agent] → danh sách candidates
          │
          ▼
    User duyệt (KHÔNG tự động thêm hết — chờ endpoint approve)
          │
          ▼
    Với mỗi lexical_item được duyệt, chạy SONG SONG (asyncio.gather):
          ├─→ [Context Agent]  → 3-4 example_sentences
          ├─→ [Mnemonic Agent] → chỉ khi từ "khó hình dung"
          └─→ [Cluster Agent]  → theo BATCH khi có >= 5 sense mới, không per-item
          │
          ▼
    Ghi DB → tạo cards → sẵn sàng vào hàng đợi review

GHI CHÚ VỀ `status` CỦA JOB
---------------------------
Schema file 01 chỉ cho phép 5 giá trị: pending/extracting/enriching/done/failed — không
có trạng thái "chờ user duyệt". Nên job đi qua 'done' HAI lần:
    pending → extracting → done   (candidates đã sẵn sàng, chờ duyệt)
    approve → enriching  → done   (đã enrich xong, cards đã tạo)
Để UI phân biệt được hai lần 'done' mà không phải thêm giá trị mới vào CHECK
constraint, `GET /api/ingestion/jobs/{id}` trả kèm `candidate_count` và
`approved_count`.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentSchemaError, LLMError
from app.agents.context_agent import DEFAULT_ESSAY_TYPES, ContextAgent
from app.agents.extraction_agent import ExtractionAgent
from app.agents.mnemonic_agent import MnemonicAgent
from app.agents.sense_agent import SenseAgent
from app.core.db import AsyncSessionLocal
from app.core.time import to_iso, utcnow
from app.models.jobs import IngestionCandidate, IngestionJob
from app.models.lexical import ExampleSentence, LexicalItem, Mnemonic, Sense
from app.schemas.agent_io import (
    ContextInput,
    ExtractionInput,
    MnemonicInput,
    SenseInput,
)
from app.services.card_factory import create_cards_for_sense
from app.services.cluster_service import maybe_run_cluster_batch
from app.services.content_ingestion import IngestionError, resolve_text
from app.services.phonetics import to_ipa
from app.services.tts import synthesize_many

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Bước 1: Extraction
# --------------------------------------------------------------------------
async def run_extraction_job(
    job_id: str, band_min: float = 5.0, band_max: float = 8.0
) -> None:
    """Background task: lấy text → Extraction Agent → ghi candidates chờ duyệt."""
    async with AsyncSessionLocal() as session:
        job = await session.get(IngestionJob, job_id)
        if job is None:
            logger.error("run_extraction_job: không tìm thấy job %s", job_id)
            return

        job.status = "extracting"
        await session.commit()

        try:
            text = await resolve_text(
                job.source_type or "pasted_text", job.raw_text, _url_of(job)
            )
            job.raw_text = text

            existing = await _existing_surface_forms(session, job.user_id)
            agent = ExtractionAgent()
            output = await agent.run_filtered(
                session,
                ExtractionInput(
                    text=text,
                    band_min=band_min,
                    band_max=band_max,
                    existing_items=existing,
                ),
            )

            for candidate in output.candidates:
                item = LexicalItem(
                    surface_form=candidate.surface_form,
                    item_type=candidate.item_type,
                    cefr_level=candidate.cefr_level,
                    source_deck_id=job.deck_id,
                )
                session.add(item)
                await session.flush()
                session.add(
                    IngestionCandidate(
                        job_id=job.id,
                        lexical_item_id=item.id,
                        reason=candidate.reason,
                        sentence_context=candidate.sentence_context,
                        is_approved=False,
                    )
                )

            job.status = "done"
            job.error_message = None
            await session.commit()
            logger.info(
                "job %s: extraction xong, %d candidates chờ duyệt",
                job_id,
                len(output.candidates),
            )
        except (IngestionError, LLMError, AgentSchemaError) as exc:
            await session.rollback()
            await _fail_job(session, job_id, str(exc))
        except Exception as exc:  # pragma: no cover - lỗi ngoài dự kiến
            logger.exception("job %s: extraction lỗi", job_id)
            await session.rollback()
            await _fail_job(session, job_id, f"Lỗi không mong đợi: {exc}")


# --------------------------------------------------------------------------
# Bước 2: Enrichment (sau khi user duyệt)
# --------------------------------------------------------------------------
async def run_enrichment_job(
    job_id: str | None,
    user_id: str,
    lexical_item_ids: list[str],
    target_ielts_band: float = 7.0,
) -> None:
    """Background task: enrich các item đã duyệt rồi tạo card.

    `job_id=None` khi item được thêm thủ công qua `POST /api/lexical-items`
    (file 01 mục 2) — luồng enrich giống hệt, chỉ không gắn với job nào.
    """
    async with AsyncSessionLocal() as session:
        if job_id:
            job = await session.get(IngestionJob, job_id)
            if job is not None:
                job.status = "enriching"
                await session.commit()

        try:
            # asyncio.gather trên từng item: các item độc lập nhau nên chạy song song
            # (file 03 mục 6). Mỗi item mở session riêng để tránh tranh chấp
            # AsyncSession — SQLAlchemy AsyncSession KHÔNG an toàn khi dùng đồng thời.
            results = await asyncio.gather(
                *(
                    enrich_lexical_item(item_id, user_id, target_ielts_band)
                    for item_id in lexical_item_ids
                ),
                return_exceptions=True,
            )
            failures = [r for r in results if isinstance(r, Exception)]
            for failure in failures:
                logger.error("enrichment lỗi cho 1 item: %s", failure)

            # Cluster Agent chạy theo BATCH (không per-item) vì cần so sánh chéo deck.
            await maybe_run_cluster_batch(session, user_id)
            await session.commit()

            if job_id:
                job = await session.get(IngestionJob, job_id)
                if job is not None:
                    if failures and len(failures) == len(lexical_item_ids):
                        job.status = "failed"
                        job.error_message = f"Enrich thất bại toàn bộ: {failures[0]}"
                    else:
                        job.status = "done"
                        job.error_message = (
                            f"{len(failures)}/{len(lexical_item_ids)} item enrich lỗi"
                            if failures
                            else None
                        )
                    job.completed_at = to_iso(utcnow())
                    await session.commit()
        except Exception as exc:  # pragma: no cover
            logger.exception("job %s: enrichment lỗi", job_id)
            await session.rollback()
            if job_id:
                await _fail_job(session, job_id, f"Lỗi enrichment: {exc}")


async def enrich_lexical_item(
    lexical_item_id: str, user_id: str, target_ielts_band: float = 7.0
) -> str:
    """Enrich MỘT lexical item: sense → (context ∥ mnemonic) → cards.

    Mở session riêng để có thể gọi đồng thời nhiều item bằng asyncio.gather.
    """
    # --- Pha 1: đọc dữ liệu cần thiết rồi ĐÓNG session ngay ---
    # Tuyệt đối không giữ session mở xuyên suốt các lời gọi LLM: SQLite chỉ cho một
    # writer tại một thời điểm, mà pipeline này chạy nhiều item song song. Giữ
    # transaction ghi trong lúc chờ mạng sẽ khoá toàn bộ các task còn lại.
    async with AsyncSessionLocal() as session:
        item = await session.get(LexicalItem, lexical_item_id)
        if item is None:
            raise ValueError(f"Không tìm thấy lexical_item {lexical_item_id}")
        surface_form = item.surface_form
        item_type = item.item_type

        sentence_context = (
            await session.execute(
                select(IngestionCandidate.sentence_context)
                .where(IngestionCandidate.lexical_item_id == lexical_item_id)
                .limit(1)
            )
        ).scalar_one_or_none()

    # --- Pha 2: gọi agent (không giữ transaction nào) ---
    # Bước bổ sung: sinh sense/definition (xem app/agents/sense_agent.py).
    sense_result = await _run_sense_agent(
        surface_form, item_type, sentence_context, target_ielts_band
    )
    if not sense_result.output.senses:
        raise AgentSchemaError(
            f"Sense Agent không trả về nghĩa nào cho '{surface_form}'"
        )

    # Context Agent ∥ Mnemonic Agent, song song trên TOÀN BỘ sense (file 03 mục 6).
    async def _enrich_one(definition):
        tasks = [_run_context_agent(surface_form, definition.definition_en)]
        if definition.needs_mnemonic:
            tasks.append(_run_mnemonic_agent(surface_form, definition.definition_en))
        return await asyncio.gather(*tasks, return_exceptions=True)

    enriched = await asyncio.gather(
        *(_enrich_one(d) for d in sense_result.output.senses)
    )

    # --- Pha 2b: phiên âm + audio phát âm ---
    # Cả hai đều chạy local, KHÔNG phải LLM: IPA lấy từ từ điển phát âm (CMUdict/espeak),
    # audio do Kokoro tổng hợp. Đặt ở đây — vòng agent chạy nền — để vòng review sau này
    # chỉ việc trả về một URL tĩnh, đúng ràng buộc "review không I/O ngoài" (file 00 mục 4).
    ipa = to_ipa(surface_form)

    spoken: list[str] = []
    if sentence_context:
        spoken.append(sentence_context)
    for outcomes in enriched:
        if not isinstance(outcomes[0], Exception):
            spoken.extend(e.sentence for e in outcomes[0].output.examples)
    # dict.fromkeys: bỏ trùng nhưng giữ thứ tự, để map lại đúng kết quả bên dưới.
    unique_spoken = list(dict.fromkeys(spoken))

    item_audio, *sentence_audio = await synthesize_many([surface_form, *unique_spoken])
    audio_by_sentence = dict(zip(unique_spoken, sentence_audio))

    # --- Pha 3: ghi toàn bộ kết quả trong MỘT transaction ngắn ---
    async with AsyncSessionLocal() as session:
        item = await session.get(LexicalItem, lexical_item_id)
        if item is not None:
            item.ipa = ipa
            item.audio_path = item_audio

        for index, (definition, outcomes) in enumerate(
            zip(sense_result.output.senses, enriched)
        ):
            sense = Sense(
                lexical_item_id=lexical_item_id,
                definition_en=definition.definition_en,
                definition_vi=definition.definition_vi,
                part_of_speech=definition.part_of_speech,
                register=definition.register,
            )
            session.add(sense)
            await session.flush()

            # Câu gốc trong bài đọc là ví dụ CÓ THẬT — quý hơn câu agent sinh ra, lưu
            # cho sense đầu tiên (sense khớp ngữ cảnh, theo prompt của Sense Agent).
            if sentence_context and index == 0:
                session.add(
                    ExampleSentence(
                        sense_id=sense.id,
                        sentence=sentence_context,
                        essay_type="general",
                        source="user_reading",
                        generated_by_model=None,
                        audio_path=audio_by_sentence.get(sentence_context),
                    )
                )

            context_result = outcomes[0]
            if isinstance(context_result, Exception):
                logger.warning(
                    "Context Agent lỗi cho '%s': %s", surface_form, context_result
                )
            else:
                for example in context_result.output.examples:
                    session.add(
                        ExampleSentence(
                            sense_id=sense.id,
                            sentence=example.sentence,
                            essay_type=example.essay_type,
                            source="agent_generated",
                            generated_by_model=context_result.model,
                            audio_path=audio_by_sentence.get(example.sentence),
                        )
                    )

            if len(outcomes) > 1:
                mnemonic_result = outcomes[1]
                if isinstance(mnemonic_result, Exception):
                    logger.warning(
                        "Mnemonic Agent lỗi cho '%s': %s",
                        surface_form,
                        mnemonic_result,
                    )
                else:
                    session.add(
                        Mnemonic(
                            sense_id=sense.id,
                            mnemonic_text=mnemonic_result.output.mnemonic_text,
                            mnemonic_type=mnemonic_result.output.mnemonic_type,
                            generated_by_model=mnemonic_result.model,
                        )
                    )

            await create_cards_for_sense(session, sense.id, user_id)

        await session.commit()
    return lexical_item_id


async def _run_sense_agent(
    surface_form: str,
    item_type: str,
    sentence_context: str | None,
    target_ielts_band: float,
):
    async with AsyncSessionLocal() as session:
        result = await SenseAgent().run(
            session,
            SenseInput(
                surface_form=surface_form,
                item_type=item_type,  # type: ignore[arg-type]
                sentence_context=sentence_context,
                target_ielts_band=target_ielts_band,
            ),
        )
        await session.commit()
        return result


async def _run_context_agent(surface_form: str, definition_en: str):
    async with AsyncSessionLocal() as session:
        result = await ContextAgent().run(
            session,
            ContextInput(
                surface_form=surface_form,
                definition_en=definition_en,
                essay_types=DEFAULT_ESSAY_TYPES,  # type: ignore[arg-type]
            ),
        )
        await session.commit()
        return result


async def _run_mnemonic_agent(surface_form: str, definition_en: str):
    async with AsyncSessionLocal() as session:
        result = await MnemonicAgent().run(
            session,
            MnemonicInput(
                surface_form=surface_form,
                definition_en=definition_en,
                is_regeneration=False,
                previous_mnemonic=None,
            ),
        )
        await session.commit()
        return result


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _url_of(job: IngestionJob) -> str | None:
    """Với source_type='url', URL được lưu tạm trong raw_text lúc tạo job."""
    if job.source_type in ("url", "pdf") and job.raw_text:
        candidate = job.raw_text.strip()
        if candidate.startswith(("http://", "https://")):
            return candidate
    return None


async def _existing_surface_forms(session: AsyncSession, user_id: str) -> list[str]:
    """Các từ user đã có (để Extraction Agent không đề xuất trùng — nguyên tắc #4)."""
    from app.models.srs import Card

    rows = (
        await session.execute(
            select(LexicalItem.surface_form)
            .join(Sense, Sense.lexical_item_id == LexicalItem.id)
            .join(Card, Card.sense_id == Sense.id)
            .where(Card.user_id == user_id)
            .distinct()
        )
    ).scalars()
    return list(rows)


async def _fail_job(session: AsyncSession, job_id: str, message: str) -> None:
    job = await session.get(IngestionJob, job_id)
    if job is None:
        return
    job.status = "failed"
    job.error_message = message[:2000]
    job.completed_at = to_iso(utcnow())
    await session.commit()
