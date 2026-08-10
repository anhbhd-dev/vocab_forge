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

import re  # noqa: E402

from pydantic import BaseModel, ConfigDict, Field, field_validator  # noqa: E402

# DeepSeek là model Trung Quốc và thỉnh thoảng trôi về tiếng Trung ở những trường đáng
# lẽ phải là tiếng Việt — người học mở thẻ ra thấy "全球范围内的下降或减少" thay vì nghĩa
# tiếng Việt. Prompt đã nói rõ ngôn ngữ nhưng nói không đủ, nên chặn thêm ở tầng schema:
# ValidationError khiến runner gọi lại LLM kèm lý do (xem agents/runner.py), và cũng
# khiến các entry cache đã nhiễm bị bỏ qua thay vì trả về mãi.
#
# Dải ký tự: Kana, CJK ext-A, CJK thống nhất, dạng tương thích, Hangul. Tiếng Việt viết
# bằng chữ Latin có dấu nên không bao giờ chạm vào các dải này.
_CJK_RE = re.compile(
    r"[぀-ヿ㐀-䶿一-鿿豈-﫿가-힯]"
)


def _reject_cjk(value: str | None) -> str | None:
    """Từ chối chuỗi chứa chữ Hán/Kana/Hangul — dùng cho các trường tiếng Việt."""
    if value and _CJK_RE.search(value):
        raise ValueError(
            "phải viết bằng TIẾNG VIỆT (chữ Latin có dấu), không được dùng chữ Hán, "
            "Kana hay Hangul"
        )
    return value


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
    # Khoảng band thay cho một band duy nhất: một bài đọc thường chứa từ ở nhiều mức, và
    # người học muốn quét hết từ mức mình đang có tới mức mình nhắm tới (vd 5.0 → 8.0)
    # thay vì chỉ lấy đúng một lát cắt. Prompt quy đổi khoảng này sang CEFR (nguyên tắc #7).
    band_min: float = Field(default=5.0, ge=4.0, le=9.0)
    band_max: float = Field(default=8.0, ge=4.0, le=9.0)
    existing_items: list[str] = Field(default_factory=list)

    @field_validator("band_max")
    @classmethod
    def _max_not_below_min(cls, value: float, info):
        band_min = info.data.get("band_min")
        if band_min is not None and value < band_min:
            raise ValueError("band_max không được nhỏ hơn band_min")
        return value


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
    # Câu có thật trong bài đọc của user, nếu có. Gửi kèm để agent dịch và đánh dấu nó
    # luôn trong cùng một lượt gọi — nếu không thì trên thẻ sẽ có đúng một câu trơ ra
    # không bản dịch, giữa những câu khác đều có.
    source_sentence: str | None = None


HighlightRole = Literal["target", "collocation", "academic", "linker"]


class ContextHighlight(StrictModel):
    """Một mảnh đáng tô màu trong câu ví dụ.

    `text` là CHUỖI CON nguyên văn của câu chứ không phải chỉ số ký tự: LLM đếm vị trí
    rất tệ, còn chép lại đúng đoạn chữ thì làm được. FE tự dò vị trí bằng so khớp chuỗi
    và bỏ qua mảnh nào không tìm thấy.
    """

    text: str = Field(min_length=1)
    role: HighlightRole = "academic"


class ContextExample(StrictModel):
    sentence: str
    # Bản dịch có thể vắng: dữ liệu cũ sinh trước khi có trường này, và câu lấy thẳng từ
    # bài đọc của user thì không đi qua agent nên không bao giờ có bản dịch.
    sentence_vi: str | None = None
    essay_type: EssayType = "general"
    highlights: list[ContextHighlight] = Field(default_factory=list)

    _no_cjk_vi = field_validator("sentence_vi")(_reject_cjk)


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

    _no_cjk_note = field_validator("distinguishing_note")(_reject_cjk)


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

    _no_cjk_text = field_validator("mnemonic_text")(_reject_cjk)


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

    _no_cjk_feedback = field_validator("feedback_text")(_reject_cjk)


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

    _no_cjk_vi = field_validator("definition_vi")(_reject_cjk)


class SenseOutput(StrictModel):
    # senses rỗng nghĩa là không định nghĩa được từ → phải retry, không im lặng bỏ qua.
    senses: list[SenseDefinition] = Field(min_length=1)
