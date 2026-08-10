"""Xử lý leech — file 02 mục 4.

Khác biệt với Anki: Anki chỉ suspend thẻ. Ở đây khi thẻ vừa thành leech, hệ thống:
  1. đánh dấu leech (đã làm trong SRS engine),
  2. TRIGGER LẠI Mnemonic Agent để sinh mnemonic MỚI, khác hẳn cách cũ — vì cách cũ
     rõ ràng không hiệu quả với người học này,
  3. hiển thị trong `/api/analytics/leeches` để user tự thêm ghi chú/tạm ẩn.

Bước 2 chạy NỀN (BackgroundTasks) — không nằm trong fast path của vòng review.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.agents.base import AgentSchemaError, LLMError
from app.agents.mnemonic_agent import MnemonicAgent
from app.core.db import AsyncSessionLocal
from app.models.lexical import LexicalItem, Mnemonic, Sense
from app.schemas.agent_io import MnemonicInput

logger = logging.getLogger(__name__)


async def regenerate_mnemonic(sense_id: str) -> str | None:
    """Sinh mnemonic mới cho một sense bị leech. Trả về mnemonic_text hoặc None."""
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(Sense, LexicalItem)
                .join(LexicalItem, LexicalItem.id == Sense.lexical_item_id)
                .where(Sense.id == sense_id)
            )
        ).first()
        if row is None:
            logger.warning("regenerate_mnemonic: không tìm thấy sense %s", sense_id)
            return None
        sense, item = row

        previous = (
            await session.execute(
                select(Mnemonic.mnemonic_text)
                .where(Mnemonic.sense_id == sense_id)
                .order_by(Mnemonic.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        try:
            result = await MnemonicAgent().run(
                session,
                MnemonicInput(
                    surface_form=item.surface_form,
                    definition_en=sense.definition_en,
                    # Bắt buộc True: prompt yêu cầu agent đổi hẳn cách tiếp cận, và
                    # cờ này cũng tắt cache (xem MnemonicAgent.is_cacheable).
                    is_regeneration=True,
                    previous_mnemonic=previous,
                ),
                use_cache=False,
            )
        except (LLMError, AgentSchemaError) as exc:
            logger.warning("regenerate_mnemonic lỗi cho sense %s: %s", sense_id, exc)
            return None

        session.add(
            Mnemonic(
                sense_id=sense_id,
                mnemonic_text=result.output.mnemonic_text,
                mnemonic_type=result.output.mnemonic_type,
                generated_by_model=result.model,
            )
        )
        await session.commit()
        logger.info("Đã sinh mnemonic mới cho sense %s (leech)", sense_id)
        return result.output.mnemonic_text
