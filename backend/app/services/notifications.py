"""Tạo và đọc thông báo.

Nguyên tắc: gọi `notify()` KHÔNG bao giờ được làm hỏng việc đang chạy. Job đã enrich
xong 15 mục từ mà lỗi ghi thông báo lại kéo cả job sang 'failed' thì thà không có thông
báo. Vì vậy mọi lỗi ở đây đều bị nuốt và chỉ ghi log.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)


async def notify(
    session: AsyncSession,
    *,
    user_id: str,
    type: str,
    title: str,
    body: str | None = None,
    job_id: str | None = None,
    count: int | None = None,
) -> None:
    """Xếp một thông báo vào session hiện tại (người gọi tự commit)."""
    try:
        session.add(
            Notification(
                user_id=user_id,
                type=type,
                title=title,
                body=body,
                job_id=job_id,
                count=count,
            )
        )
    except Exception:  # pragma: no cover - thông báo là tính năng phụ trợ
        logger.exception("Không tạo được thông báo %s cho user %s", type, user_id)
