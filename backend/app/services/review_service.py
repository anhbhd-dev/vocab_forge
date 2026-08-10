"""Vòng review — FAST PATH.

File 00 mục 4.1 + file 04 yêu cầu #2: KHÔNG được gọi bất kỳ LLM API nào trong luồng
này. Mọi dữ liệu hiển thị (nghĩa, ví dụ, mnemonic, cluster) đã được agent sinh sẵn và
lưu DB trước khi thẻ vào hàng đợi.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import from_iso, to_iso, utcnow
from app.models.lexical import (
    ConfusionClusterMember,
    ExampleSentence,
    LexicalItem,
    Mnemonic,
    Sense,
)
from app.models.srs import Card, ReviewLog
from app.models.user import User
from app.services.tts import audio_url_for
from app.srs.engine import CardState, get_engine, next_interval_preview

# Retention chỉ tính trên các lần review THỰC SỰ kiểm tra trí nhớ: thẻ đã được hẹn
# lịch từ >= 1 ngày trước. Các bước learning trong cùng buổi (1 phút, 10 phút) không
# phản ánh khả năng nhớ dài hạn, tính vào sẽ làm retention méo mó.
MIN_SCHEDULED_DAYS_FOR_RETENTION = 1.0


def to_card_state(card: Card) -> CardState:
    return CardState(
        state=card.state,
        stability=card.stability,
        difficulty=card.difficulty,
        due_at=from_iso(card.due_at),
        last_reviewed_at=from_iso(card.last_reviewed_at),
        reps=card.reps or 0,
        lapses=card.lapses or 0,
        is_leech=bool(card.is_leech),
        learning_step=card.learning_step,
    )


async def count_new_cards_introduced_today(
    session: AsyncSession, user_id: str, now=None
) -> int:
    """Số thẻ MỚI đã được đưa vào học hôm nay (dùng để chặn theo daily goal)."""
    now = now or utcnow()
    day_start = to_iso(now.replace(hour=0, minute=0, second=0, microsecond=0))

    first_reviews = (
        select(ReviewLog.card_id, func.min(ReviewLog.reviewed_at).label("first_at"))
        .group_by(ReviewLog.card_id)
        .subquery()
    )
    stmt = (
        select(func.count())
        .select_from(first_reviews)
        .join(Card, Card.id == first_reviews.c.card_id)
        .where(Card.user_id == user_id, first_reviews.c.first_at >= day_start)
    )
    return int((await session.execute(stmt)).scalar_one() or 0)


async def _senses_ready_for_production(
    session: AsyncSession, user_id: str
) -> set[str]:
    """Sense mà thẻ nhận diện đã tốt nghiệp sang state 'review'.

    Chỉ khi đó card `production` mới được đưa vào hàng đợi (xem card_factory): bắt user
    viết câu với từ chưa nhận diện nổi là lãng phí review budget.
    """
    rows = (
        await session.execute(
            select(Card.sense_id)
            .where(
                Card.user_id == user_id,
                Card.card_direction.in_(("en_to_vi", "vi_to_en")),
                Card.state == "review",
            )
            .distinct()
        )
    ).scalars()
    return set(rows)


async def build_queue(
    session: AsyncSession, user: User, limit: int = 30
) -> dict:
    """Hàng đợi review: thẻ đến hạn trước, sau đó bổ sung thẻ mới theo daily goal."""
    now = utcnow()
    now_iso = to_iso(now)
    ready_for_production = await _senses_ready_for_production(session, user.id)

    def _usable(card: Card) -> bool:
        if card.card_direction != "production":
            return True
        return card.sense_id in ready_for_production

    due_rows = (
        (
            await session.execute(
                select(Card)
                .where(
                    Card.user_id == user.id,
                    Card.state != "new",
                    Card.due_at <= now_iso,
                    Card.is_leech.is_(False),
                )
                .order_by(Card.due_at)
                .limit(limit * 3)
            )
        )
        .scalars()
        .all()
    )
    due_cards = [c for c in due_rows if _usable(c)][:limit]

    remaining = max(0, limit - len(due_cards))
    introduced_today = await count_new_cards_introduced_today(session, user.id, now)
    new_budget = max(0, (user.daily_new_word_goal or 10) - introduced_today)

    new_cards: list[Card] = []
    if remaining and new_budget:
        new_rows = (
            (
                await session.execute(
                    select(Card)
                    .where(Card.user_id == user.id, Card.state == "new")
                    .order_by(Card.created_at)
                    .limit((remaining + new_budget) * 3)
                )
            )
            .scalars()
            .all()
        )
        new_cards = [c for c in new_rows if _usable(c)][: min(remaining, new_budget)]

    cards = due_cards + new_cards
    payload = await hydrate_cards(session, cards)

    total_due = (
        await session.execute(
            select(func.count())
            .select_from(Card)
            .where(
                Card.user_id == user.id,
                Card.state != "new",
                Card.due_at <= now_iso,
                Card.is_leech.is_(False),
            )
        )
    ).scalar_one()

    return {
        "cards": payload,
        "due_count": int(total_due or 0),
        "new_count": new_budget,
        "daily_new_word_goal": user.daily_new_word_goal or 10,
    }


async def hydrate_cards(session: AsyncSession, cards: list[Card]) -> list[dict]:
    """Nạp toàn bộ nội dung thẻ bằng MỘT nhóm query (tránh N+1)."""
    if not cards:
        return []

    sense_ids = list({c.sense_id for c in cards})

    sense_rows = (
        await session.execute(
            select(Sense, LexicalItem)
            .join(LexicalItem, LexicalItem.id == Sense.lexical_item_id)
            .where(Sense.id.in_(sense_ids))
        )
    ).all()
    sense_map = {s.id: (s, li) for s, li in sense_rows}

    examples: dict[str, list[ExampleSentence]] = defaultdict(list)
    for row in (
        (
            await session.execute(
                select(ExampleSentence).where(ExampleSentence.sense_id.in_(sense_ids))
            )
        )
        .scalars()
        .all()
    ):
        examples[row.sense_id].append(row)

    mnemonics: dict[str, list[Mnemonic]] = defaultdict(list)
    for row in (
        (
            await session.execute(
                select(Mnemonic).where(Mnemonic.sense_id.in_(sense_ids))
            )
        )
        .scalars()
        .all()
    ):
        mnemonics[row.sense_id].append(row)

    cluster_map = dict(
        (
            await session.execute(
                select(
                    ConfusionClusterMember.sense_id, ConfusionClusterMember.cluster_id
                ).where(ConfusionClusterMember.sense_id.in_(sense_ids))
            )
        ).all()
    )

    engine = get_engine()
    out: list[dict] = []
    for card in cards:
        entry = sense_map.get(card.sense_id)
        if entry is None:
            continue
        sense, item = entry
        out.append(
            {
                "id": card.id,
                "sense_id": card.sense_id,
                "card_direction": card.card_direction,
                "state": card.state,
                "due_at": card.due_at,
                "last_reviewed_at": card.last_reviewed_at,
                "is_leech": bool(card.is_leech),
                "reps": card.reps or 0,
                "lapses": card.lapses or 0,
                # D/S/R lộ ra để UI vẽ đường cong quên bằng dữ liệu THẬT của thẻ
                # (signature element của design system), không phải hình trang trí.
                "stability": card.stability or 0.0,
                "difficulty": card.difficulty or 0.0,
                "retrievability": engine.retrievability(to_card_state(card)),
                "surface_form": item.surface_form,
                "item_type": item.item_type,
                "ipa": item.ipa,
                # Chỉ ghép chuỗi, không đụng vào đĩa hay mạng — fast path vẫn sạch.
                "audio_url": audio_url_for(item.audio_path),
                "cefr_level": item.cefr_level,
                "definition_en": sense.definition_en,
                "definition_vi": sense.definition_vi,
                "part_of_speech": sense.part_of_speech,
                "register": sense.register,
                "examples": [
                    {
                        "id": e.id,
                        "sentence": e.sentence,
                        "essay_type": e.essay_type,
                        "source": e.source,
                        "audio_url": audio_url_for(e.audio_path),
                    }
                    for e in examples.get(card.sense_id, [])
                ],
                "mnemonics": [
                    {
                        "id": m.id,
                        "mnemonic_text": m.mnemonic_text,
                        "mnemonic_type": m.mnemonic_type,
                    }
                    for m in mnemonics.get(card.sense_id, [])
                ],
                "cluster_id": cluster_map.get(card.sense_id),
                "interval_preview_days": next_interval_preview(
                    to_card_state(card), engine
                ),
            }
        )
    return out


async def recent_ratings(
    session: AsyncSession, card_id: str, limit: int = 5
) -> list[int]:
    rows = (
        await session.execute(
            select(ReviewLog.rating)
            .where(ReviewLog.card_id == card_id)
            .order_by(ReviewLog.reviewed_at.desc())
            .limit(limit)
        )
    ).scalars()
    return list(rows)


async def apply_answer(
    session: AsyncSession, card: Card, rating: int, error_type: str | None
) -> dict:
    """Chấm một lần review — pseudocode file 02 mục 6, KHÔNG gọi LLM."""
    engine = get_engine()
    history = await recent_ratings(session, card.id)

    outcome = engine.process_review(
        to_card_state(card),
        rating=rating,
        error_type=None if error_type in (None, "none") else error_type,
        recent_ratings=history,
    )

    session.add(
        ReviewLog(
            card_id=card.id,
            reviewed_at=to_iso(outcome.last_reviewed_at),
            rating=rating,
            elapsed_days=outcome.elapsed_days,
            scheduled_days=outcome.scheduled_days,
            error_type=error_type,
        )
    )

    card.state = outcome.state
    card.stability = outcome.stability
    card.difficulty = outcome.difficulty
    card.due_at = to_iso(outcome.due_at)
    card.last_reviewed_at = to_iso(outcome.last_reviewed_at)
    card.reps = outcome.reps
    card.lapses = outcome.lapses
    card.is_leech = outcome.is_leech
    card.learning_step = outcome.learning_step

    return {
        "card_id": card.id,
        "state": outcome.state,
        "due_at": to_iso(outcome.due_at),
        "interval_days": round(outcome.interval_days, 6),
        "stability": outcome.stability,
        "difficulty": outcome.difficulty,
        "reps": outcome.reps,
        "lapses": outcome.lapses,
        "is_leech": outcome.is_leech,
        "became_leech": outcome.became_leech,
        "adjustments": outcome.adjustments,
        "followups": outcome.followups,
    }


# ------------------------------------------------------------------ thống kê
async def retention_rate(
    session: AsyncSession, user_id: str, days: int
) -> float | None:
    since = to_iso(utcnow() - timedelta(days=days))
    stmt = (
        select(
            func.count(),
            func.sum(case((ReviewLog.rating >= 2, 1), else_=0)),
        )
        .select_from(ReviewLog)
        .join(Card, Card.id == ReviewLog.card_id)
        .where(
            Card.user_id == user_id,
            ReviewLog.reviewed_at >= since,
            ReviewLog.scheduled_days >= MIN_SCHEDULED_DAYS_FOR_RETENTION,
        )
    )
    total, passed = (await session.execute(stmt)).one()
    if not total:
        return None
    return float(passed or 0) / float(total)


async def daily_retention(
    session: AsyncSession, user_id: str, days: int = 7
) -> list[float]:
    """Retention theo từng ngày, mới nhất đứng đầu — đầu vào cho ramp-up (file 02 §7)."""
    since = to_iso(utcnow() - timedelta(days=days))
    # Ngày = 10 ký tự đầu của chuỗi ISO. Phải dùng CÙNG một object biểu thức cho cả
    # GROUP BY lẫn ORDER BY: PostgreSQL không nhận alias ở GROUP BY rồi lại thấy biểu
    # thức gốc ở ORDER BY (SQLite thì dễ dãi, nên lỗi chỉ lộ ra trên Postgres).
    day = func.substr(ReviewLog.reviewed_at, 1, 10)
    rows = (
        await session.execute(
            select(
                day.label("day"),
                func.count(),
                func.sum(case((ReviewLog.rating >= 2, 1), else_=0)),
            )
            .select_from(ReviewLog)
            .join(Card, Card.id == ReviewLog.card_id)
            .where(
                Card.user_id == user_id,
                ReviewLog.reviewed_at >= since,
                ReviewLog.scheduled_days >= MIN_SCHEDULED_DAYS_FOR_RETENTION,
            )
            .group_by(day)
            .order_by(day.desc())
        )
    ).all()
    return [float(passed or 0) / float(total) for _day, total, passed in rows if total]


async def streak_days(session: AsyncSession, user_id: str) -> int:
    """Số ngày liên tiếp (tính tới hôm nay hoặc hôm qua) có ít nhất 1 lần review."""
    day = func.substr(ReviewLog.reviewed_at, 1, 10)
    rows = (
        await session.execute(
            select(day.label("day"))
            .select_from(ReviewLog)
            .join(Card, Card.id == ReviewLog.card_id)
            .where(Card.user_id == user_id)
            .group_by(day)
            .order_by(day.desc())
            .limit(400)
        )
    ).scalars()
    days = list(rows)
    if not days:
        return 0

    today = utcnow().date()
    first = _parse_day(days[0])
    if first is None or (today - first).days > 1:
        # Đứt chuỗi nếu hôm qua và hôm nay đều không review.
        return 0

    streak = 1
    previous = first
    for raw in days[1:]:
        current = _parse_day(raw)
        if current is None:
            break
        if (previous - current).days == 1:
            streak += 1
            previous = current
        else:
            break
    return streak


def _parse_day(value: str):
    from datetime import date

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


async def review_stats(session: AsyncSession, user: User) -> dict:
    now = utcnow()
    now_iso = to_iso(now)
    day_start = to_iso(now.replace(hour=0, minute=0, second=0, microsecond=0))

    due_today = (
        await session.execute(
            select(func.count())
            .select_from(Card)
            .where(
                Card.user_id == user.id,
                Card.state != "new",
                Card.due_at <= now_iso,
                Card.is_leech.is_(False),
            )
        )
    ).scalar_one()

    total_cards = (
        await session.execute(
            select(func.count()).select_from(Card).where(Card.user_id == user.id)
        )
    ).scalar_one()

    leech_count = (
        await session.execute(
            select(func.count())
            .select_from(Card)
            .where(Card.user_id == user.id, Card.is_leech.is_(True))
        )
    ).scalar_one()

    reviewed_today = (
        await session.execute(
            select(func.count())
            .select_from(ReviewLog)
            .join(Card, Card.id == ReviewLog.card_id)
            .where(Card.user_id == user.id, ReviewLog.reviewed_at >= day_start)
        )
    ).scalar_one()

    introduced_today = await count_new_cards_introduced_today(session, user.id, now)

    return {
        "due_today": int(due_today or 0),
        "new_available": max(0, (user.daily_new_word_goal or 10) - introduced_today),
        "reviewed_today": int(reviewed_today or 0),
        "streak_days": await streak_days(session, user.id),
        "retention_rate_7d": await retention_rate(session, user.id, 7),
        "retention_rate_30d": await retention_rate(session, user.id, 30),
        "total_cards": int(total_cards or 0),
        "leech_count": int(leech_count or 0),
    }
