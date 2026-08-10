"""Chống trùng từ vựng — một chỗ duy nhất quyết định "từ này đã có chưa".

Có hai câu hỏi khác nhau, hay bị gộp làm một nên phải nói rõ:

1. **"User này đã học từ này chưa?"** → `existing_surface_forms()`.
   Dùng để KHÔNG đề xuất lại một từ ở màn hình duyệt candidate. Phạm vi theo user, vì
   deck là của riêng từng người.

2. **"Trong DB đã có bản ghi cho từ này chưa?"** → `get_or_create_lexical_item()`.
   Dùng để KHÔNG tạo thêm hàng `lexical_items` trùng lặp. Phạm vi TOÀN CỤC, vì
   `lexical_items` cố ý dùng chung giữa các user (xem ghi chú ở `api/decks.py`): nghĩa,
   ví dụ, phiên âm và audio của "mitigate" giống nhau với mọi người học, sinh lại là
   đốt tiền LLM và mấy phút TTS cho cùng một kết quả.

Câu 1 lọc ở tầng đề xuất, câu 2 lọc ở tầng ghi. Thiếu câu 1 thì user thấy lại từ đã
thuộc; thiếu câu 2 thì mỗi lần import lại đẻ thêm một bản sao của cùng một từ.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobs import IngestionCandidate, IngestionJob
from app.models.lexical import LexicalItem, Sense
from app.models.srs import Card


def normalize(text: str) -> str:
    """Khoá so trùng: gộp khoảng trắng + hạ chữ thường.

    Cố ý KHÔNG lemmatize: "effect" và "effects" là hai mục từ khác nhau về mặt học
    thuật, còn "Detrimental Effect" và "detrimental  effect" thì không.
    """
    return " ".join((text or "").lower().split())


async def existing_surface_forms(session: AsyncSession, user_id: str) -> list[str]:
    """Những từ KHÔNG nên đề xuất lại cho user này.

    Gồm hai nhóm, và nhóm thứ hai mới là chỗ trước đây bị hở:

    * đã có card (đang học) — hiển nhiên;
    * đã bấm duyệt — thường sẽ thành card, nhưng giữa lúc duyệt và lúc enrich xong có
      một khoảng trống, và nếu enrich hỏng thì không bao giờ có card;
    * đang chờ duyệt ở một job khác — chỗ trước đây bị hở. Import bài thứ hai có cùng
      từ sẽ đề xuất lại y nguyên, duyệt cả hai lần là học trùng.

    Từ đã bị user BỎ QUA thì cố ý vẫn được đề xuất lại: bỏ qua có thể chỉ vì hôm đó
    chưa muốn học, không phải vì từ đó vô dụng. Nhận diện "bỏ qua" bằng cách nhìn cả
    job: job nào đã có ít nhất một candidate được duyệt nghĩa là user đã xem xong danh
    sách đó, nên những candidate còn lại trong job là bị loại chứ không phải chờ.
    """
    learning = (
        select(LexicalItem.surface_form)
        .join(Sense, Sense.lexical_item_id == LexicalItem.id)
        .join(Card, Card.sense_id == Sense.id)
        .where(Card.user_id == user_id)
    )

    reviewed_jobs = (
        select(IngestionCandidate.job_id)
        .where(IngestionCandidate.is_approved.is_(True))
        .distinct()
    )
    from_candidates = (
        select(LexicalItem.surface_form)
        .join(IngestionCandidate, IngestionCandidate.lexical_item_id == LexicalItem.id)
        .join(IngestionJob, IngestionJob.id == IngestionCandidate.job_id)
        .where(
            IngestionJob.user_id == user_id,
            # Đã duyệt, HOẶC nằm trong job chưa ai duyệt gì (tức là đang chờ).
            IngestionCandidate.is_approved.is_(True)
            | IngestionCandidate.job_id.notin_(reviewed_jobs),
        )
    )
    rows = (await session.execute(learning.union(from_candidates))).scalars()
    return list(rows)


async def find_lexical_item(
    session: AsyncSession, surface_form: str, item_type: str
) -> LexicalItem | None:
    """Bản ghi sẵn có cho từ này, ưu tiên bản ĐÃ enrich.

    Có thể còn sót nhiều bản trùng do dữ liệu cũ tạo trước khi có lớp chống trùng này,
    nên phải chọn có chủ đích thay vì lấy bừa hàng đầu tiên: bản đã có sense là bản
    dùng lại được ngay (không tốn lượt gọi agent nào), bản chưa có sense thì tái dùng
    cũng vẫn phải enrich.

    So trùng theo `surface_form`, KHÔNG bắt buộc trùng `item_type`: cùng một cụm có thể
    được agent xếp là `collocation` ở bài này và `phrasal_verb` ở bài kia — đó là ranh
    giới vốn mờ, không phải hai mục từ khác nhau. Bắt khớp cả hai trường sẽ để lọt đúng
    những ca trùng mà lớp này sinh ra để chặn. `item_type` chỉ dùng để ưu tiên khi có
    nhiều lựa chọn ngang nhau.
    """
    key = normalize(surface_form)
    if not key:
        return None

    rows = (
        (
            await session.execute(
                select(LexicalItem)
                .where(func.lower(LexicalItem.surface_form) == key)
                .order_by(LexicalItem.created_at)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return None
    rows.sort(key=lambda row: row.item_type != item_type)

    enriched = (
        (
            await session.execute(
                select(Sense.lexical_item_id)
                .where(Sense.lexical_item_id.in_([row.id for row in rows]))
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    enriched_ids = set(enriched)
    for row in rows:
        if row.id in enriched_ids:
            return row
    return rows[0]


async def get_or_create_lexical_item(
    session: AsyncSession,
    *,
    surface_form: str,
    item_type: str,
    cefr_level: str | None = None,
    deck_id: str | None = None,
) -> tuple[LexicalItem, bool]:
    """Trả về (item, reused). `reused=True` nghĩa là dùng lại bản ghi có sẵn.

    Khi tái dùng, chỉ ĐIỀN THÊM các trường còn trống chứ không ghi đè: bản ghi cũ có
    thể đã được enrich kỹ hơn, và `cefr_level` do Extraction Agent đoán ở lần này không
    có lý do gì đáng tin hơn lần trước.
    """
    existing = await find_lexical_item(session, surface_form, item_type)
    if existing is not None:
        if existing.cefr_level is None and cefr_level:
            existing.cefr_level = cefr_level
        if existing.source_deck_id is None and deck_id:
            existing.source_deck_id = deck_id
        return existing, True

    item = LexicalItem(
        surface_form=surface_form.strip(),
        item_type=item_type,
        cefr_level=cefr_level,
        source_deck_id=deck_id,
    )
    session.add(item)
    await session.flush()
    return item, False


async def user_has_cards_for_item(
    session: AsyncSession, user_id: str, lexical_item_id: str
) -> bool:
    """User đã có card cho mục từ này chưa — dùng để chặn thêm tay lần hai."""
    found = (
        await session.execute(
            select(Card.id)
            .join(Sense, Sense.id == Card.sense_id)
            .where(Card.user_id == user_id, Sense.lexical_item_id == lexical_item_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    return found is not None


__all__ = [
    "existing_surface_forms",
    "find_lexical_item",
    "get_or_create_lexical_item",
    "normalize",
    "user_has_cards_for_item",
]
