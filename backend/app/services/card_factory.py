"""Sinh card từ sense.

File 01 mục 3 (`card_direction`): "cho phép cùng 1 sense sinh ra nhiều loại card
(nhận diện xuôi/ngược, production, phân biệt cluster) — đây là chỗ để mở rộng độ khó
dần theo thời gian".

Chiến lược mặc định (Phase 1-3 gộp):
  - `en_to_vi` + `vi_to_en`: tạo ngay khi sense được enrich.
  - `production`: tạo ngay nhưng chỉ đưa vào hàng đợi SAU khi thẻ nhận diện đã tốt
    nghiệp (state='review') — xem `review_service.build_queue`. Lý do: bắt user sản
    xuất một từ chưa nhận diện nổi là lãng phí và gây nản.
  - `cluster_discrimination`: chỉ tạo khi sense được xếp vào một confusion cluster.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import to_iso, utcnow
from app.models.srs import Card

RECOGNITION_DIRECTIONS = ("en_to_vi", "vi_to_en")
DEFAULT_DIRECTIONS = ("en_to_vi", "vi_to_en", "production")


async def create_cards_for_sense(
    session: AsyncSession,
    sense_id: str,
    user_id: str,
    directions: Sequence[str] = DEFAULT_DIRECTIONS,
) -> list[Card]:
    """Tạo card cho một sense, bỏ qua direction đã tồn tại (idempotent)."""
    existing = set(
        (
            await session.execute(
                select(Card.card_direction).where(
                    Card.sense_id == sense_id, Card.user_id == user_id
                )
            )
        )
        .scalars()
        .all()
    )

    now = to_iso(utcnow())
    created: list[Card] = []
    for direction in directions:
        if direction in existing:
            continue
        card = Card(
            sense_id=sense_id,
            user_id=user_id,
            card_direction=direction,
            state="new",
            stability=0.0,
            difficulty=0.0,
            # Thẻ mới due ngay để lọt vào hàng đợi hôm nay; số lượng thẻ mới thực sự
            # được phát mỗi ngày do `daily_new_word_goal` khống chế ở review_service.
            due_at=now,
            learning_step=0,
        )
        session.add(card)
        created.append(card)
    return created
