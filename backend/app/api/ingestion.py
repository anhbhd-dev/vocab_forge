"""Ingestion — file 01 mục 2, phần "Ingestion".

    POST   /api/ingestion/jobs
    GET    /api/ingestion/jobs/{job_id}
    GET    /api/ingestion/jobs/{job_id}/candidates
    POST   /api/ingestion/jobs/{job_id}/approve

Job chạy nền bằng FastAPI BackgroundTasks + bảng `ingestion_jobs` để track trạng thái
(file 04 STACK: KHÔNG dùng Celery/Redis ở giai đoạn này).
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models.jobs import IngestionCandidate, IngestionJob
from app.models.lexical import LexicalItem
from app.models.user import Deck
from app.schemas.api import ApproveRequest, CandidateOut, IngestionJobCreate
from app.services.ingestion_pipeline import run_enrichment_job, run_extraction_job

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


async def _owned_job(session, user, job_id: str) -> IngestionJob:
    job = await session.get(IngestionJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy job")
    return job


@router.post("/jobs", status_code=202)
async def create_job(
    payload: IngestionJobCreate,
    user: CurrentUser,
    session: SessionDep,
    background: BackgroundTasks,
) -> dict:
    if payload.deck_id:
        deck = await session.get(Deck, payload.deck_id)
        if deck is None or deck.user_id != user.id:
            raise HTTPException(status_code=404, detail="Không tìm thấy deck")

    if payload.source_type == "pasted_text" and not (payload.raw_text or "").strip():
        raise HTTPException(status_code=422, detail="`raw_text` là bắt buộc")
    if payload.source_type in ("url", "pdf") and not (payload.url or payload.raw_text):
        raise HTTPException(
            status_code=422, detail="Cần `url` (hoặc `raw_text` base64 cho PDF)"
        )

    job = IngestionJob(
        user_id=user.id,
        deck_id=payload.deck_id,
        source_type=payload.source_type,
        # Với url/pdf, URL được cất tạm trong raw_text và sẽ bị thay bằng text đã trích
        # khi extraction chạy xong (xem ingestion_pipeline._url_of).
        raw_text=payload.raw_text or payload.url,
        status="pending",
    )
    session.add(job)
    await session.commit()

    background.add_task(run_extraction_job, job.id, payload.target_ielts_band)
    return {"job_id": job.id, "status": "pending"}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, user: CurrentUser, session: SessionDep) -> dict:
    job = await _owned_job(session, user, job_id)

    total = int(
        (
            await session.execute(
                select(func.count())
                .select_from(IngestionCandidate)
                .where(IngestionCandidate.job_id == job_id)
            )
        ).scalar_one()
        or 0
    )
    approved = int(
        (
            await session.execute(
                select(func.count())
                .select_from(IngestionCandidate)
                .where(
                    IngestionCandidate.job_id == job_id,
                    IngestionCandidate.is_approved.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )

    return {
        "id": job.id,
        "deck_id": job.deck_id,
        "source_type": job.source_type,
        "status": job.status,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        # Hai trường dưới để UI phân biệt 2 lần job ở trạng thái 'done'
        # (xem docstring ingestion_pipeline.py).
        "candidate_count": total,
        "approved_count": approved,
        "awaiting_approval": job.status == "done" and total > 0 and approved == 0,
    }


@router.get("/jobs/{job_id}/candidates", response_model=list[CandidateOut])
async def list_candidates(
    job_id: str, user: CurrentUser, session: SessionDep
) -> list[dict]:
    await _owned_job(session, user, job_id)
    rows = (
        await session.execute(
            select(IngestionCandidate, LexicalItem)
            .join(LexicalItem, LexicalItem.id == IngestionCandidate.lexical_item_id)
            .where(IngestionCandidate.job_id == job_id)
            .order_by(IngestionCandidate.created_at)
        )
    ).all()
    return [
        {
            "id": candidate.id,
            "lexical_item_id": candidate.lexical_item_id,
            "surface_form": item.surface_form,
            "item_type": item.item_type,
            "cefr_level": item.cefr_level,
            "reason": candidate.reason,
            "sentence_context": candidate.sentence_context,
            "is_approved": bool(candidate.is_approved),
        }
        for candidate, item in rows
    ]


@router.post("/jobs/{job_id}/approve", status_code=202)
async def approve_candidates(
    job_id: str,
    payload: ApproveRequest,
    user: CurrentUser,
    session: SessionDep,
    background: BackgroundTasks,
) -> dict:
    """User duyệt từ muốn học → enrich NỀN (file 03 mục 6: KHÔNG tự động enrich hết)."""
    job = await _owned_job(session, user, job_id)

    rows = (
        (
            await session.execute(
                select(IngestionCandidate).where(
                    IngestionCandidate.job_id == job_id,
                    IngestionCandidate.lexical_item_id.in_(
                        payload.selected_lexical_item_ids
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=422,
            detail="Không có lexical_item_id hợp lệ nào thuộc job này",
        )

    for candidate in rows:
        candidate.is_approved = True
    job.status = "enriching"
    await session.commit()

    approved_ids = [c.lexical_item_id for c in rows]
    background.add_task(
        run_enrichment_job, job.id, user.id, approved_ids, payload.target_ielts_band
    )
    return {
        "job_id": job.id,
        "status": "enriching",
        "approved_count": len(approved_ids),
    }
