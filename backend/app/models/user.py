"""Bảng users & decks — file 01 mục 1, phần USERS & DECKS."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, id_column


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = id_column()
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    # Cột mở rộng ngoài spec: spec không mô tả cách lưu mật khẩu nhưng file 04 yêu cầu #7
    # có đăng nhập email/password, nên bắt buộc phải có chỗ chứa hash.
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = created_at_column()
    # Mục tiêu từ mới HIỆN TẠI — ramp-up tự tăng/giảm nó theo retention (file 02 mục 7).
    daily_new_word_goal: Mapped[int] = mapped_column(Integer, default=10)
    # Khoảng người học tự đặt, vd 20–30 từ/ngày. Ramp-up chỉ được điều chỉnh mục tiêu
    # TRONG khoảng này; trước đây hai ngưỡng bị hard-code 5–30 trong srs/rampup.py nên
    # người học không có tiếng nói nào về nhịp độ của mình.
    daily_new_min: Mapped[int] = mapped_column(Integer, default=5)
    daily_new_max: Mapped[int] = mapped_column(Integer, default=30)
    timezone: Mapped[str] = mapped_column(String, default="Asia/Ho_Chi_Minh")


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[str] = id_column()
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = created_at_column()
