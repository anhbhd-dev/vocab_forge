"""Bảng notifications — thông báo việc chạy nền đã xong.

VÌ SAO CẦN
----------
Trích xuất và enrichment đều là việc của vòng agent: mất từ vài chục giây tới vài phút.
Bắt người học ngồi nhìn màn hình chờ là lãng phí đúng khoảng thời gian họ có thể dùng để
ôn bài. Nên luồng đúng là: nhận bài → báo "đã nhận" ngay → chạy nền → khi xong thì để
lại một thông báo, người học bấm vào là tới đúng chỗ cần hành động.

Bảng riêng thay vì suy ra từ `ingestion_jobs`: một job sinh ra HAI sự kiện đáng báo
(trích xuất xong → mời duyệt; tạo thẻ xong → mời ôn), và mỗi sự kiện có trạng thái
đã-đọc riêng. Nhồi hai cờ đó vào bảng job sẽ hỏng ngay khi có loại thông báo thứ ba.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, id_column

NOTIFICATION_TYPES = (
    "extraction_done",
    "extraction_failed",
    "enrichment_done",
    "enrichment_failed",
)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "type IN ('extraction_done','extraction_failed','enrichment_done',"
            "'enrichment_failed')",
            name="ck_notification_type",
        ),
    )

    id: Mapped[str] = id_column()
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str | None] = mapped_column(String)
    # Job liên quan — FE dùng để dựng đường dẫn tới đúng màn hình duyệt.
    job_id: Mapped[str | None] = mapped_column(String, ForeignKey("ingestion_jobs.id"))
    # Con số đáng khoe ngay trên tiêu đề (số từ chờ duyệt / số thẻ vừa tạo).
    count: Mapped[int | None] = mapped_column(Integer)
    read_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = created_at_column()
