"""Bảng lexical_items / senses / example_sentences / mnemonics / confusion_clusters.

File 01 mục 1, phần CARD CORE và MNEMONIC & CLUSTER.
"""

from __future__ import annotations

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, id_column

ITEM_TYPES = ("single_word", "collocation", "phrasal_verb", "idiom")
REGISTERS = ("academic", "neutral", "informal")
ESSAY_TYPES = (
    "opinion",
    "discussion",
    "problem_solution",
    "advantage_disadvantage",
    "general",
)
MNEMONIC_TYPES = ("keyword_dual_coding", "etymology", "story_link")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ",".join(f"'{v}'" for v in values)
    return f"{column} IN ({joined})"


class LexicalItem(Base):
    __tablename__ = "lexical_items"
    __table_args__ = (
        CheckConstraint(_in_list("item_type", ITEM_TYPES), name="ck_item_type"),
    )

    id: Mapped[str] = id_column()
    surface_form: Mapped[str] = mapped_column(String, nullable=False)
    item_type: Mapped[str] = mapped_column(String, nullable=False)
    ipa: Mapped[str | None] = mapped_column(String)
    # Tên file audio phát âm do Kokoro sinh sẵn ở vòng agent (xem services/tts.py).
    # Lưu tên file chứ không lưu URL đầy đủ: đổi domain/prefix không phải migrate dữ liệu.
    audio_path: Mapped[str | None] = mapped_column(String)
    audio_path_male: Mapped[str | None] = mapped_column(String)
    cefr_level: Mapped[str | None] = mapped_column(String)
    academic_word_list_sublist: Mapped[int | None] = mapped_column(Integer)
    source_deck_id: Mapped[str | None] = mapped_column(String, ForeignKey("decks.id"))
    created_at: Mapped[str] = created_at_column()


class Sense(Base):
    """Một nghĩa của lexical item = một đơn vị sinh ra card.

    Tách `lexical_item` khỏi `sense` là chủ ý (file 01 mục 3): "address" (địa chỉ) và
    "address" (giải quyết) phải là 2 card riêng để tránh interference khi ôn tập.
    """

    __tablename__ = "senses"
    __table_args__ = (
        CheckConstraint(_in_list("register", REGISTERS), name="ck_sense_register"),
    )

    id: Mapped[str] = id_column()
    lexical_item_id: Mapped[str] = mapped_column(
        String, ForeignKey("lexical_items.id"), nullable=False
    )
    definition_en: Mapped[str] = mapped_column(String, nullable=False)
    definition_vi: Mapped[str | None] = mapped_column(String)
    part_of_speech: Mapped[str | None] = mapped_column(String)
    register: Mapped[str | None] = mapped_column(String)
    frequency_rank: Mapped[int | None] = mapped_column(Integer)


class ExampleSentence(Base):
    __tablename__ = "example_sentences"
    __table_args__ = (
        CheckConstraint(_in_list("essay_type", ESSAY_TYPES), name="ck_essay_type"),
        CheckConstraint(
            _in_list("source", ("user_reading", "agent_generated")),
            name="ck_example_source",
        ),
    )

    id: Mapped[str] = id_column()
    sense_id: Mapped[str] = mapped_column(
        String, ForeignKey("senses.id"), nullable=False
    )
    sentence: Mapped[str] = mapped_column(String, nullable=False)
    # Bản dịch tiếng Việt do Context Agent sinh cùng lúc với câu. NULL với câu lấy thẳng
    # từ bài đọc của user (không đi qua agent) và với dữ liệu sinh trước tính năng này.
    sentence_vi: Mapped[str | None] = mapped_column(String)
    # [{"text": "...", "role": "target|collocation|academic|linker"}] — các đoạn cần tô
    # màu. Lưu chuỗi con chứ không lưu offset: câu là bất biến nên chuỗi con luôn dò
    # lại được, còn offset thì hỏng ngay khi có ai đó sửa một dấu cách.
    highlights: Mapped[list | None] = mapped_column(JSON)
    essay_type: Mapped[str | None] = mapped_column(String)
    source: Mapped[str | None] = mapped_column(String)
    generated_by_model: Mapped[str | None] = mapped_column(String)
    audio_path: Mapped[str | None] = mapped_column(String)
    # Giọng nam, sinh song song với giọng nữ ở vòng agent. Hai cột riêng thay vì một
    # bảng audio: chỉ có hai giọng và cả hai đều sinh sẵn, thêm bảng chỉ tổ phải join.
    audio_path_male: Mapped[str | None] = mapped_column(String)


class Mnemonic(Base):
    __tablename__ = "mnemonics"
    __table_args__ = (
        CheckConstraint(
            _in_list("mnemonic_type", MNEMONIC_TYPES), name="ck_mnemonic_type"
        ),
    )

    id: Mapped[str] = id_column()
    sense_id: Mapped[str] = mapped_column(
        String, ForeignKey("senses.id"), nullable=False
    )
    mnemonic_text: Mapped[str] = mapped_column(String, nullable=False)
    mnemonic_type: Mapped[str | None] = mapped_column(String)
    generated_by_model: Mapped[str | None] = mapped_column(String)


class ConfusionCluster(Base):
    __tablename__ = "confusion_clusters"

    id: Mapped[str] = id_column()
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    cluster_label: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = created_at_column()


class ConfusionClusterMember(Base):
    __tablename__ = "confusion_cluster_members"

    cluster_id: Mapped[str] = mapped_column(
        String, ForeignKey("confusion_clusters.id"), primary_key=True
    )
    sense_id: Mapped[str] = mapped_column(
        String, ForeignKey("senses.id"), primary_key=True
    )
    distinguishing_note: Mapped[str | None] = mapped_column(String)
