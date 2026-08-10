"""Analytics — thành phần 7 (file 00 mục 5), endpoint ở file 01 mục 2.

Điểm nhấn: `error-breakdown` là dữ liệu KHÁC BIỆT của sản phẩm (file 02 mục 5) — thống
kê theo LOẠI LỖI chứ không chỉ đúng/sai.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.cache import cache_stats
from app.core.time import to_iso, utcnow
from app.models.lexical import LexicalItem, Mnemonic, Sense
from app.models.production import ProductionAttempt
from app.models.srs import Card, ReviewLog
from app.models.user import User
from app.services.review_service import (
    daily_retention,
    retention_rate,
    streak_days,
)
from app.srs.rampup import evaluate_daily_goal


async def overview(session: AsyncSession, user: User) -> dict:
    now = utcnow()
    since_7d = to_iso(now - timedelta(days=7))
    now_iso = to_iso(now)

    total_items = (
        await session.execute(
            select(func.count(func.distinct(Sense.lexical_item_id)))
            .select_from(Sense)
            .join(Card, Card.sense_id == Sense.id)
            .where(Card.user_id == user.id)
        )
    ).scalar_one()

    state_rows = (
        await session.execute(
            select(Card.state, func.count())
            .where(Card.user_id == user.id)
            .group_by(Card.state)
        )
    ).all()
    cards_by_state = {state: int(count) for state, count in state_rows}

    reviews_7d = (
        await session.execute(
            select(func.count())
            .select_from(ReviewLog)
            .join(Card, Card.id == ReviewLog.card_id)
            .where(Card.user_id == user.id, ReviewLog.reviewed_at >= since_7d)
        )
    ).scalar_one()

    due_today = (
        await session.execute(
            select(func.count())
            .select_from(Card)
            .where(
                Card.user_id == user.id,
                Card.state != "new",
                Card.due_at <= now_iso,
            )
        )
    ).scalar_one()

    r7 = await retention_rate(session, user.id, 7)
    decision = evaluate_daily_goal(
        current_goal=user.daily_new_word_goal or 10,
        retention_7d=r7,
        due_count_today=int(due_today or 0),
        daily_retention_desc=await daily_retention(session, user.id, days=7),
    )

    return {
        "total_lexical_items": int(total_items or 0),
        "total_cards": sum(cards_by_state.values()),
        "cards_by_state": cards_by_state,
        "reviews_last_7d": int(reviews_7d or 0),
        "retention_rate_7d": r7,
        "retention_rate_30d": await retention_rate(session, user.id, 30),
        "streak_days": await streak_days(session, user.id),
        "daily_new_word_goal": user.daily_new_word_goal or 10,
        "ramp_up": {
            "action": decision.action,
            "recommended_goal": decision.recommended_goal,
            "reason": decision.reason,
        },
        "agent_cache": await cache_stats(session),
    }


async def error_breakdown(session: AsyncSession, user_id: str, days: int = 30) -> dict:
    since = to_iso(utcnow() - timedelta(days=days))

    review_rows = (
        await session.execute(
            select(ReviewLog.error_type, func.count())
            .select_from(ReviewLog)
            .join(Card, Card.id == ReviewLog.card_id)
            .where(
                Card.user_id == user_id,
                ReviewLog.reviewed_at >= since,
                ReviewLog.error_type.is_not(None),
            )
            .group_by(ReviewLog.error_type)
        )
    ).all()

    production_rows = (
        await session.execute(
            select(ProductionAttempt.error_type, func.count())
            .select_from(ProductionAttempt)
            .join(Card, Card.id == ProductionAttempt.card_id)
            .where(
                Card.user_id == user_id,
                ProductionAttempt.submitted_at >= since,
                ProductionAttempt.error_type.is_not(None),
            )
            .group_by(ProductionAttempt.error_type)
        )
    ).all()

    return {
        "review_errors": _with_share(review_rows),
        "production_errors": _with_share(production_rows),
        "total_reviews_with_error_type": sum(int(c) for _t, c in review_rows),
        "total_production_attempts": sum(int(c) for _t, c in production_rows),
    }


def _with_share(rows) -> list[dict]:
    total = sum(int(c) for _t, c in rows) or 1
    return [
        {"error_type": t or "unknown", "count": int(c), "share": int(c) / total}
        for t, c in sorted(rows, key=lambda r: -r[1])
    ]


async def leeches(session: AsyncSession, user_id: str) -> list[dict]:
    """Danh sách thẻ leech + mnemonic mới nhất (để user thấy agent đã thử cách khác)."""
    rows = (
        await session.execute(
            select(Card, Sense, LexicalItem)
            .join(Sense, Sense.id == Card.sense_id)
            .join(LexicalItem, LexicalItem.id == Sense.lexical_item_id)
            .where(Card.user_id == user_id, Card.is_leech.is_(True))
            .order_by(Card.lapses.desc())
        )
    ).all()

    out: list[dict] = []
    for card, sense, item in rows:
        mnemonic_rows = (
            (
                await session.execute(
                    select(Mnemonic.mnemonic_text).where(
                        Mnemonic.sense_id == sense.id
                    )
                )
            )
            .scalars()
            .all()
        )
        out.append(
            {
                "card_id": card.id,
                "sense_id": sense.id,
                "surface_form": item.surface_form,
                "definition_en": sense.definition_en,
                "card_direction": card.card_direction,
                "lapses": card.lapses or 0,
                "reps": card.reps or 0,
                "latest_mnemonic": mnemonic_rows[-1] if mnemonic_rows else None,
                # >1 mnemonic nghĩa là Mnemonic Agent đã được trigger lại sau khi thẻ
                # thành leech (file 02 mục 4, bước 2).
                "mnemonic_regenerated": len(mnemonic_rows) > 1,
            }
        )
    return out
