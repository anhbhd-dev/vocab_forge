"""Review — file 01 mục 2, phần "Review (SRS core — fast path, không gọi LLM)".

    GET    /api/review/queue?limit=30
    POST   /api/review/cards/{card_id}/answer
    GET    /api/review/stats

RÀNG BUỘC TUYỆT ĐỐI (file 04 yêu cầu #2): không endpoint nào ở đây được gọi LLM.
Ngoại lệ duy nhất là job NỀN sinh lại mnemonic khi thẻ vừa thành leech — nó chạy sau
khi response đã trả về nên không nằm trong độ trễ mà user cảm nhận.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.api.deps import CurrentUser, SessionDep
from app.models.srs import Card
from app.schemas.api import (
    AnswerRequest,
    AnswerResponse,
    ReviewQueueOut,
    ReviewStatsOut,
)
from app.services.leech_service import regenerate_mnemonic
from app.services.review_service import apply_answer, build_queue, review_stats

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/queue", response_model=ReviewQueueOut)
async def get_queue(
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(default=30, ge=1, le=200),
) -> dict:
    return await build_queue(session, user, limit=limit)


@router.post("/cards/{card_id}/answer", response_model=AnswerResponse)
async def answer_card(
    card_id: str,
    payload: AnswerRequest,
    user: CurrentUser,
    session: SessionDep,
    background: BackgroundTasks,
) -> dict:
    card = await session.get(Card, card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy thẻ")

    result = await apply_answer(session, card, payload.rating, payload.error_type)
    await session.commit()

    # File 02 mục 4 bước 2: thẻ vừa thành leech → sinh mnemonic MỚI. Chạy nền để
    # không phá vỡ fast path.
    if result["became_leech"]:
        background.add_task(regenerate_mnemonic, card.sense_id)

    return result


@router.get("/stats", response_model=ReviewStatsOut)
async def get_stats(user: CurrentUser, session: SessionDep) -> dict:
    return await review_stats(session, user)
