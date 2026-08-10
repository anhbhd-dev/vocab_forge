"""Thông báo — việc chạy nền đã xong.

    GET    /api/notifications
    POST   /api/notifications/{id}/read
    POST   /api/notifications/read-all
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, SessionDep
from app.core.time import to_iso, utcnow
from app.models.notification import Notification
from app.schemas.api import NotificationListOut, NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# Chuông thông báo chỉ là lối tắt tới việc cần làm, không phải nhật ký. Giữ danh sách
# ngắn để nó luôn liếc một cái là hiểu.
LIMIT = 20


@router.get("", response_model=NotificationListOut)
async def list_notifications(user: CurrentUser, session: SessionDep) -> dict:
    rows = (
        (
            await session.execute(
                select(Notification)
                .where(Notification.user_id == user.id)
                .order_by(Notification.created_at.desc())
                .limit(LIMIT)
            )
        )
        .scalars()
        .all()
    )
    unread = (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        )
    ).scalar_one()
    return {"notifications": list(rows), "unread_count": unread}


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: str, user: CurrentUser, session: SessionDep
) -> Notification:
    row = await session.get(Notification, notification_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo")
    # Đã đọc rồi thì giữ nguyên mốc thời gian cũ — đọc lại không phải là sự kiện mới.
    if row.read_at is None:
        row.read_at = to_iso(utcnow())
        await session.commit()
    return row


@router.post("/read-all", status_code=204)
async def mark_all_read(user: CurrentUser, session: SessionDep) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=to_iso(utcnow()))
    )
    await session.commit()
