"""Sinh audio còn thiếu cho TOÀN BỘ dữ liệu đã có.

Dùng khi thêm một giọng mới (vd giọng nam vừa được bổ sung): các thẻ tạo trước đó chỉ
có giọng cũ, và `generate_audio_for_items` chỉ chạy cho những mục vừa được enrich nên
không bao giờ quay lại chỗ dữ liệu cũ.

Chạy được nhiều lần: mục nào đã có đường dẫn thì bỏ qua. Không đụng tới thẻ hay lịch ôn.

    docker compose exec backend python scripts/backfill_audio.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models.lexical import ExampleSentence, LexicalItem  # noqa: E402
from app.services.tts import synthesize_many  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill_audio")

# Xử lý theo lô: một lô lớn giữ transaction mở quá lâu, và nếu process chết giữa chừng
# thì mất sạch công đã tổng hợp. Lô nhỏ commit thường xuyên → chạy lại là tiếp tục.
BATCH = 40


async def _fill(model, text_column: str) -> None:
    label = "từ" if model is LexicalItem else "câu"
    while True:
        async with AsyncSessionLocal() as session:
            rows = (
                (
                    await session.execute(
                        select(model)
                        .where(
                            or_(
                                model.audio_path.is_(None),
                                model.audio_path_male.is_(None),
                            )
                        )
                        .limit(BATCH)
                    )
                )
                .scalars()
                .all()
            )
            if not rows:
                return

            texts = [getattr(row, text_column) for row in rows]
            for voice, column in (
                (settings.tts_voice, "audio_path"),
                (settings.tts_voice_male, "audio_path_male"),
            ):
                missing = [i for i, r in enumerate(rows) if getattr(r, column) is None]
                if not missing:
                    continue
                paths = await synthesize_many([texts[i] for i in missing], voice=voice)
                for i, path in zip(missing, paths):
                    if path:
                        setattr(rows[i], column, path)
            await session.commit()
            logger.info("%s: xong một lô %d mục", label, len(rows))


async def main() -> None:
    if not settings.tts_enabled:
        logger.error("TTS_ENABLED=false — không có gì để sinh.")
        return
    await _fill(LexicalItem, "surface_form")
    await _fill(ExampleSentence, "sentence")
    logger.info("Xong. Mọi mục từ và câu ví dụ đều đã có audio cả hai giọng.")


if __name__ == "__main__":
    asyncio.run(main())
