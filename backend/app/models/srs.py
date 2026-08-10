"""Bảng cards & review_logs — file 01 mục 1, phần SRS CORE."""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, id_column

CARD_DIRECTIONS = ("en_to_vi", "vi_to_en", "production", "cluster_discrimination")
CARD_STATES = ("new", "learning", "review", "relearning")
ERROR_TYPES_REVIEW = ("meaning", "collocation", "spelling", "register", "none")


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint(
            "card_direction IN ('en_to_vi','vi_to_en','production','cluster_discrimination')",
            name="ck_card_direction",
        ),
        CheckConstraint(
            "state IN ('new','learning','review','relearning')", name="ck_card_state"
        ),
    )

    id: Mapped[str] = id_column()
    sense_id: Mapped[str] = mapped_column(
        String, ForeignKey("senses.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    card_direction: Mapped[str] = mapped_column(String, nullable=False)

    state: Mapped[str] = mapped_column(String, nullable=False, default="new")
    stability: Mapped[float | None] = mapped_column(Float, default=0.0)
    difficulty: Mapped[float | None] = mapped_column(Float, default=0.0)
    # due_at lưu datetime ISO đầy đủ (tới micro-giây), KHÔNG chỉ ngày — file 01 mục 3.
    due_at: Mapped[str | None] = mapped_column(String)
    last_reviewed_at: Mapped[str | None] = mapped_column(String)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    is_leech: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Cột mở rộng ngoài spec file 01 (bắt buộc về mặt kỹ thuật) ---
    # py-fsrs mô hình hoá chuỗi learning/relearning steps bằng `Card.step`. Nếu không
    # persist, mỗi lần load lại card từ DB sẽ reset về step 0 và card không bao giờ
    # "tốt nghiệp" khỏi learning đúng cách. Cột này thuần nội bộ engine, không lộ ra API.
    learning_step: Mapped[int | None] = mapped_column(Integer, default=0)

    created_at: Mapped[str] = created_at_column()


class ReviewLog(Base):
    __tablename__ = "review_logs"
    __table_args__ = (
        CheckConstraint("rating IN (1,2,3,4)", name="ck_review_rating"),
        CheckConstraint(
            "error_type IS NULL OR error_type IN "
            "('meaning','collocation','spelling','register','none')",
            name="ck_review_error_type",
        ),
    )

    id: Mapped[str] = id_column()
    card_id: Mapped[str] = mapped_column(String, ForeignKey("cards.id"), nullable=False)
    reviewed_at: Mapped[str] = created_at_column()
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    elapsed_days: Mapped[float | None] = mapped_column(Float)
    scheduled_days: Mapped[float | None] = mapped_column(Float)
    error_type: Mapped[str | None] = mapped_column(String)
