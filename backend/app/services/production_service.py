"""Production grading — file 00 mục 4.2, file 03 Agent 5.

Đây là NGOẠI LỆ duy nhất được gọi LLM trong lúc user đang tương tác. Cách xử lý theo
spec: endpoint trả `attempt_id` NGAY (status pending), việc chấm chạy nền, UI poll —
không chặn toàn bộ session review, user đi tiếp thẻ sau trong lúc chờ.

Kết quả chấm còn được đưa NGƯỢC vào lịch ôn: `error_type` do agent phân loại được áp
vào SRS engine đúng như một lần review (file 02 mục 5).
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.agents.base import AgentSchemaError, LLMError
from app.agents.production_grading_agent import ProductionGradingAgent
from app.core.db import AsyncSessionLocal
from app.core.time import to_iso, utcnow
from app.models.lexical import LexicalItem, Sense
from app.models.production import ProductionAttempt
from app.models.srs import Card
from app.schemas.agent_io import ProductionGradingInput

logger = logging.getLogger(__name__)

# Map error_type của agent → rating SRS. `grammar` không phải lỗi về TỪ mục tiêu nên
# vẫn coi như nhớ được (Good); `meaning` là quên thật sự (Again).
_ERROR_TO_RATING = {
    "none": 3,
    "grammar": 3,
    "register": 2,
    "collocation": 2,
    "meaning": 1,
}
# error_type của production (file 01) có 'grammar' nhưng review_logs thì không —
# map về NULL để không vi phạm CHECK constraint của review_logs.
_ERROR_TO_REVIEW_ERROR = {
    "none": "none",
    "grammar": None,
    "register": "register",
    "collocation": "collocation",
    "meaning": "meaning",
}


async def grade_attempt(attempt_id: str, essay_context: str | None = None) -> None:
    """Background task: gọi Agent 5, ghi kết quả, rồi cập nhật lịch ôn của thẻ."""
    async with AsyncSessionLocal() as session:
        attempt = await session.get(ProductionAttempt, attempt_id)
        if attempt is None:
            logger.error("grade_attempt: không tìm thấy attempt %s", attempt_id)
            return

        row = (
            await session.execute(
                select(Card, Sense, LexicalItem)
                .join(Sense, Sense.id == Card.sense_id)
                .join(LexicalItem, LexicalItem.id == Sense.lexical_item_id)
                .where(Card.id == attempt.card_id)
            )
        ).first()
        if row is None:
            logger.error("grade_attempt: không tìm thấy card %s", attempt.card_id)
            return
        card, sense, item = row

        try:
            result = await ProductionGradingAgent().run(
                session,
                ProductionGradingInput(
                    target_surface_form=item.surface_form,
                    target_definition=sense.definition_en,
                    user_sentence=attempt.user_sentence,
                    essay_context=essay_context,
                ),
            )
        except (LLMError, AgentSchemaError) as exc:
            logger.warning("Chấm attempt %s lỗi: %s", attempt_id, exc)
            attempt.feedback_text = f"Chưa chấm được, thử lại sau. ({exc})"
            attempt.graded_at = None
            await session.commit()
            return

        output = result.output
        attempt.is_correct = output.is_correct
        attempt.error_type = output.error_type
        attempt.feedback_text = output.feedback_text
        attempt.corrected_sentence = output.corrected_sentence
        attempt.graded_by_model = result.model
        attempt.graded_at = to_iso(utcnow())

        # Đưa kết quả chấm vào lịch ôn: production cũng là một lần review của thẻ đó.
        from app.services.review_service import apply_answer

        await apply_answer(
            session,
            card,
            rating=_ERROR_TO_RATING.get(output.error_type, 3),
            error_type=_ERROR_TO_REVIEW_ERROR.get(output.error_type),
        )

        await session.commit()
        logger.info(
            "Đã chấm attempt %s: error_type=%s", attempt_id, output.error_type
        )
