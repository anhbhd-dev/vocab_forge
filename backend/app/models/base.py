"""Base declarative + tiện ích chung cho model.

Ghi chú thiết kế: schema trong `docs/01_MO_HINH_DU_LIEU_VA_API.md` dùng kiểu TEXT cho
mọi mốc thời gian (ISO-8601). Ta giữ nguyên kiểu TEXT thay vì đổi sang DateTime để DDL
sinh ra khớp chính xác spec và để `due_at` giữ được độ chính xác tới micro-giây
(file 01 mục 3).
"""

from __future__ import annotations

import uuid

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.time import to_iso, utcnow


class Base(DeclarativeBase):
    pass


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return to_iso(utcnow())  # type: ignore[return-value]


def id_column() -> Mapped[str]:
    return mapped_column(String, primary_key=True, default=new_id)


def created_at_column() -> Mapped[str]:
    """Mốc thời gian ISO-8601 UTC, luôn do Python sinh.

    Schema gốc (file 01) dùng `DEFAULT (datetime('now'))` — cú pháp riêng của SQLite,
    không chạy được trên PostgreSQL. Bỏ server_default và luôn ghi từ Python thay vì
    viết default theo từng dialect: như vậy giá trị luôn cùng một định dạng
    (`YYYY-MM-DDTHH:MM:SS.ffffff+00:00`), điều kiện bắt buộc để so sánh/sắp xếp
    `due_at` theo thứ tự thời gian trên cột TEXT (xem app/core/time.py).
    """
    return mapped_column(String, nullable=False, default=now_iso)
