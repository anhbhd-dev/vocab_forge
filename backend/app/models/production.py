"""Bảng production_attempts — file 01 mục 1, phần PRODUCTION GRADING."""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, id_column

ERROR_TYPES_PRODUCTION = ("meaning", "collocation", "grammar", "register", "none")


class ProductionAttempt(Base):
    __tablename__ = "production_attempts"
    __table_args__ = (
        CheckConstraint(
            "error_type IS NULL OR error_type IN "
            "('meaning','collocation','grammar','register','none')",
            name="ck_production_error_type",
        ),
    )

    id: Mapped[str] = id_column()
    card_id: Mapped[str] = mapped_column(String, ForeignKey("cards.id"), nullable=False)
    user_sentence: Mapped[str] = mapped_column(String, nullable=False)
    submitted_at: Mapped[str] = created_at_column()

    # Các cột dưới đây NULL cho tới khi Production Grading Agent trả kết quả
    # (file 00 mục 4.2: không chặn vòng review, user poll lại sau).
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    error_type: Mapped[str | None] = mapped_column(String)
    feedback_text: Mapped[str | None] = mapped_column(String)
    graded_by_model: Mapped[str | None] = mapped_column(String)
    graded_at: Mapped[str | None] = mapped_column(String)

    # Mở rộng: output schema của Agent 5 (file 03) có `corrected_sentence` nhưng bảng
    # trong file 01 chưa có cột chứa — thêm để không mất dữ liệu agent đã sinh ra.
    corrected_sentence: Mapped[str | None] = mapped_column(String)
