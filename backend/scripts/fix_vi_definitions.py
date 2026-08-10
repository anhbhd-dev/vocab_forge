"""Vá lại các nghĩa tiếng Việt bị model trả về bằng tiếng Trung.

    docker compose exec backend python -m scripts.fix_vi_definitions

DeepSeek thỉnh thoảng trôi về tiếng Trung ở `definition_vi` / `mnemonic_text`. Từ giờ
schema đã chặn (xem `_reject_cjk` trong app/schemas/agent_io.py) nên ca mới không lọt
nữa, nhưng những dòng ĐÃ lưu trước đó vẫn nằm trong DB — script này dọn phần tồn đọng.

Cách làm: gọi lại Sense Agent cho đúng mục từ đó rồi ghi đè `definition_vi`. Không tạo
sense mới, không tạo card mới — chỉ sửa tại chỗ, nên lịch ôn của người học giữ nguyên.
Entry cache cũ đã nhiễm sẽ tự bị bỏ qua vì không qua nổi validator mới.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.agents.sense_agent import SenseAgent
from app.core.db import AsyncSessionLocal
from app.models.lexical import LexicalItem, Mnemonic, Sense
from app.schemas.agent_io import _CJK_RE, SenseInput


async def _repair_sense(session, sense: Sense, item: LexicalItem) -> bool:
    result = await SenseAgent().run(
        session,
        SenseInput(
            surface_form=item.surface_form,
            item_type=item.item_type,  # type: ignore[arg-type]
            sentence_context=None,
            target_ielts_band=7.0,
        ),
    )

    # Ưu tiên sense có definition_en trùng khớp; không có thì lấy nghĩa đầu (nghĩa phổ
    # biến nhất theo prompt). Chỉ ghi đè definition_vi, các trường khác giữ nguyên để
    # không làm xáo trộn dữ liệu người học đã ôn.
    match = next(
        (s for s in result.output.senses if s.definition_en == sense.definition_en),
        result.output.senses[0],
    )
    if not match.definition_vi:
        return False

    print(f"  {item.surface_form!r}")
    print(f"    cũ : {sense.definition_vi}")
    print(f"    mới: {match.definition_vi}")
    sense.definition_vi = match.definition_vi
    return True


async def main() -> None:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Sense, LexicalItem).join(
                    LexicalItem, Sense.lexical_item_id == LexicalItem.id
                )
            )
        ).all()

        bad = [
            (s, i)
            for s, i in rows
            if s.definition_vi and _CJK_RE.search(s.definition_vi)
        ]
        print(f"Sense cần vá: {len(bad)}/{len(rows)}")

        fixed = 0
        for sense, item in bad:
            try:
                if await _repair_sense(session, sense, item):
                    fixed += 1
            except Exception as exc:  # một mục hỏng không được chặn các mục còn lại
                print(f"  LỖI với {item.surface_form!r}: {exc}")

        # Mnemonic nhiễm thì xoá hẳn: Mnemonic Agent sẽ sinh lại khi thẻ thành leech,
        # và một mẹo nhớ bằng tiếng Trung thì vô dụng hơn là không có mẹo nào.
        mnemonics = (await session.execute(select(Mnemonic))).scalars().all()
        dropped = 0
        for m in mnemonics:
            if _CJK_RE.search(m.mnemonic_text):
                await session.delete(m)
                dropped += 1

        await session.commit()
        print(f"\nĐã vá {fixed} nghĩa, xoá {dropped} mnemonic nhiễm.")


if __name__ == "__main__":
    asyncio.run(main())
