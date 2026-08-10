"""Bảng ingestion_jobs, ingestion_candidates, agent_cache.

File 01 mục 1, phần INGESTION & AGENT JOBS.
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, id_column

JOB_STATUSES = ("pending", "extracting", "enriching", "done", "failed")
SOURCE_TYPES = ("pasted_text", "url", "pdf")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('pasted_text','url','pdf')", name="ck_job_source_type"
        ),
        CheckConstraint(
            "status IN ('pending','extracting','enriching','done','failed')",
            name="ck_job_status",
        ),
    )

    id: Mapped[str] = id_column()
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    deck_id: Mapped[str | None] = mapped_column(String, ForeignKey("decks.id"))
    source_type: Mapped[str | None] = mapped_column(String)
    raw_text: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = created_at_column()
    completed_at: Mapped[str | None] = mapped_column(String)


class IngestionCandidate(Base):
    """Ứng viên từ/cụm do Extraction Agent đề xuất, CHỜ user duyệt.

    Bảng mở rộng ngoài file 01. Lý do bắt buộc phải có: API spec
    (file 01 mục 2) có `GET /jobs/{id}/candidates` trả về danh sách chờ duyệt và
    `POST /jobs/{id}/approve` nhận `selected_lexical_item_ids`. Nghĩa là candidate phải
    tồn tại dưới dạng `lexical_items` có id trước khi được duyệt, nhưng `lexical_items`
    không có chỗ chứa `reason` / `sentence_context` mà Extraction Agent sinh ra
    (file 03, Agent 1 output schema), cũng như trạng thái đã-duyệt-hay-chưa.
    """

    __tablename__ = "ingestion_candidates"

    id: Mapped[str] = id_column()
    job_id: Mapped[str] = mapped_column(
        String, ForeignKey("ingestion_jobs.id"), nullable=False
    )
    lexical_item_id: Mapped[str] = mapped_column(
        String, ForeignKey("lexical_items.id"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String)
    sentence_context: Mapped[str | None] = mapped_column(String)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = created_at_column()


class AgentCache(Base):
    """Cache response của agent.

    File 01 mục 3: bắt buộc có NGAY từ đầu, không phải optimization sau — từ vựng
    academic IELTS trùng lặp rất cao giữa người dùng.
    """

    __tablename__ = "agent_cache"

    cache_key: Mapped[str] = mapped_column(String, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String, nullable=False)
    response_json: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = created_at_column()
    # Mở rộng nhỏ: đếm số lần cache hit để đo hiệu quả tiết kiệm chi phí LLM.
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
