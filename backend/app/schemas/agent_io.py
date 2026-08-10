"""Pydantic schema cho input/output của từng agent — file 03.

Output schema ở đây dùng cho 2 việc:
  1. nhắc lại schema trong prompt gửi LLM,
  2. validate response (file 04 yêu cầu #4) — sai schema thì retry, hết retry thì raise.
"""

from __future__ import annotations

import warnings
from typing import Literal

# `register` là tên cột trong schema file 01 nên phải giữ nguyên, nhưng nó trùng tên
# với `ABCMeta.register` thừa kế qua metaclass của Pydantic → chỉ là cảnh báo, field
# vẫn hoạt động đúng. Tắt riêng cảnh báo này để log khởi động sạch.
warnings.filterwarnings(
    "ignore", message='Field name "register".*', category=UserWarning
)

from pydantic import BaseModel, ConfigDict, Field

ItemType = Literal["single_word", "collocation", "phrasal_verb", "idiom"]
EssayType = Literal[
    "opinion", "discussion", "problem_solution", "advantage_disadvantage", "general"
]
MnemonicType = Literal["keyword_dual_coding", "etymology", "story_link"]
Register = Literal["academic", "neutral", "informal"]
ProductionErrorType = Literal["none", "meaning", "collocation", "grammar", "register"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ----------------------------------------------------------------- Agent 1
class ExtractionInput(StrictModel):
    text: str
    target_ielts_band: float = 7.0
    existing_items: list[str] = Field(default_factory=list)


class ExtractionCandidate(StrictModel):
    surface_form: str
    item_type: ItemType
    cefr_level: str | None = None
    reason: str | None = None
    sentence_context: str | None = None


class ExtractionOutput(StrictModel):
    # Bắt buộc có key `candidates` (dù có thể rỗng nếu bài đọc không có gì đáng học).
    # KHÔNG dùng default: nếu để mặc định, một response rác thiếu hẳn key vẫn validate
    # thành công và cho ra kết quả rỗng thay vì kích hoạt retry (file 04 yêu cầu #4).
    candidates: list[ExtractionCandidate]


# ----------------------------------------------------------------- Agent 2
class ContextInput(StrictModel):
    surface_form: str
    definition_en: str
    essay_types: list[EssayType]


class ContextExample(StrictModel):
    sentence: str
    essay_type: EssayType = "general"


class ContextOutput(StrictModel):
    # Ít nhất 1 câu ví dụ, nếu không thì coi như agent trả sai và phải retry.
    examples: list[ContextExample] = Field(min_length=1)


# ----------------------------------------------------------------- Agent 3
class ClusterCandidateSense(StrictModel):
    sense_id: str
    surface_form: str
    definition_en: str


class ClusterInput(StrictModel):
    candidate_senses: list[ClusterCandidateSense]


class ClusterMember(StrictModel):
    sense_id: str
    distinguishing_note: str | None = None


class ClusterItem(StrictModel):
    cluster_label: str
    members: list[ClusterMember] = Field(default_factory=list)
    discrimination_exercise_hint: str | None = None


class ClusterOutput(StrictModel):
    # Rỗng là kết quả hợp lệ: nhóm ứng viên có thể không thực sự dễ nhầm.
    clusters: list[ClusterItem]


# ----------------------------------------------------------------- Agent 4
class MnemonicInput(StrictModel):
    surface_form: str
    definition_en: str
    is_regeneration: bool = False
    previous_mnemonic: str | None = None


class MnemonicOutput(StrictModel):
    mnemonic_text: str
    mnemonic_type: MnemonicType = "keyword_dual_coding"


# ----------------------------------------------------------------- Agent 5
class ProductionGradingInput(StrictModel):
    target_surface_form: str
    target_definition: str
    user_sentence: str
    essay_context: str | None = None


class ProductionGradingOutput(StrictModel):
    is_correct: bool
    error_type: ProductionErrorType = "none"
    feedback_text: str
    corrected_sentence: str | None = None


# ------------------------------------------------- Agent mở rộng: Sense Agent
class SenseInput(StrictModel):
    surface_form: str
    item_type: ItemType
    sentence_context: str | None = None
    target_ielts_band: float = 7.0


class SenseDefinition(StrictModel):
    definition_en: str
    definition_vi: str | None = None
    part_of_speech: str | None = None
    register: Register | None = None
    needs_mnemonic: bool = False


class SenseOutput(StrictModel):
    # senses rỗng nghĩa là không định nghĩa được từ → phải retry, không im lặng bỏ qua.
    senses: list[SenseDefinition] = Field(min_length=1)
