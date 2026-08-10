"""Production Grading — file 01 mục 2 (có gọi LLM, async).

    POST   /api/production/attempts   -> trả attempt_id NGAY, status=pending
    GET    /api/production/attempts/{id}  -> poll tới khi graded_at khác NULL
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.models.production import ProductionAttempt
from app.models.srs import Card
from app.schemas.api import ProductionAttemptCreate
from app.services.production_service import grade_attempt

router = APIRouter(prefix="/api/production", tags=["production"])


@router.post("/attempts", status_code=202)
async def submit_attempt(
    payload: ProductionAttemptCreate,
    user: CurrentUser,
    session: SessionDep,
    background: BackgroundTasks,
) -> dict:
    card = await session.get(Card, payload.card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy thẻ")
    if not payload.user_sentence.strip():
        raise HTTPException(status_code=422, detail="Câu viết không được để trống")

    attempt = ProductionAttempt(
        card_id=card.id, user_sentence=payload.user_sentence.strip()
    )
    session.add(attempt)
    await session.commit()

    # Chấm chạy nền: user đi tiếp thẻ sau, không bị chặn (file 00 mục 4.2).
    background.add_task(grade_attempt, attempt.id, payload.essay_context)
    return {"attempt_id": attempt.id, "status": "pending"}


@router.get("/attempts/{attempt_id}")
async def get_attempt(
    attempt_id: str, user: CurrentUser, session: SessionDep
) -> dict:
    attempt = await session.get(ProductionAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy attempt")
    card = await session.get(Card, attempt.card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy attempt")

    return {
        "id": attempt.id,
        "card_id": attempt.card_id,
        "user_sentence": attempt.user_sentence,
        "submitted_at": attempt.submitted_at,
        "status": "graded" if attempt.graded_at else "pending",
        "is_correct": attempt.is_correct,
        "error_type": attempt.error_type,
        "feedback_text": attempt.feedback_text,
        "corrected_sentence": attempt.corrected_sentence,
        "graded_by_model": attempt.graded_by_model,
        "graded_at": attempt.graded_at,
    }
