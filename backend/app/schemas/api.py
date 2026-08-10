"""Pydantic schema cho request/response của REST API — file 01 mục 2."""

from __future__ import annotations

import warnings
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

warnings.filterwarnings(
    "ignore", message='Field name "register".*', category=UserWarning
)

ORM = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------- Auth
class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    daily_new_word_goal: int = 10
    timezone: str = "Asia/Ho_Chi_Minh"


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ORM
    id: str
    email: str
    daily_new_word_goal: int
    timezone: str
    created_at: str


class UserSettingsUpdate(BaseModel):
    daily_new_word_goal: int | None = Field(default=None, ge=1, le=100)
    timezone: str | None = None


# -------------------------------------------------------------------- Decks
class DeckCreate(BaseModel):
    name: str
    description: str | None = None


class DeckOut(BaseModel):
    model_config = ORM
    id: str
    name: str
    description: str | None
    created_at: str


class SenseOut(BaseModel):
    model_config = ORM
    id: str
    definition_en: str
    definition_vi: str | None = None
    part_of_speech: str | None = None
    register: str | None = None


class ExampleOut(BaseModel):
    model_config = ORM
    id: str
    sentence: str
    essay_type: str | None = None
    source: str | None = None


class MnemonicOut(BaseModel):
    model_config = ORM
    id: str
    mnemonic_text: str
    mnemonic_type: str | None = None


class SenseDetail(SenseOut):
    examples: list[ExampleOut] = Field(default_factory=list)
    mnemonics: list[MnemonicOut] = Field(default_factory=list)


class LexicalItemOut(BaseModel):
    model_config = ORM
    id: str
    surface_form: str
    item_type: str
    ipa: str | None = None
    cefr_level: str | None = None
    academic_word_list_sublist: int | None = None
    created_at: str


class LexicalItemDetail(LexicalItemOut):
    senses: list[SenseDetail] = Field(default_factory=list)


class LexicalItemCreate(BaseModel):
    """POST /api/lexical-items — thêm thủ công, trigger enrichment agent."""

    surface_form: str
    item_type: Literal["single_word", "collocation", "phrasal_verb", "idiom"] = (
        "single_word"
    )
    deck_id: str | None = None
    sentence_context: str | None = None
    target_ielts_band: float = 7.0


# ---------------------------------------------------------------- Ingestion
class IngestionJobCreate(BaseModel):
    source_type: Literal["pasted_text", "url", "pdf"] = "pasted_text"
    raw_text: str | None = None
    url: str | None = None
    deck_id: str | None = None
    target_ielts_band: float = 7.0


class IngestionJobOut(BaseModel):
    model_config = ORM
    id: str
    deck_id: str | None
    source_type: str | None
    status: str
    error_message: str | None
    created_at: str
    completed_at: str | None


class CandidateOut(BaseModel):
    model_config = ORM
    id: str
    lexical_item_id: str
    surface_form: str
    item_type: str
    cefr_level: str | None = None
    reason: str | None = None
    sentence_context: str | None = None
    is_approved: bool


class ApproveRequest(BaseModel):
    selected_lexical_item_ids: list[str]
    target_ielts_band: float = 7.0


# ------------------------------------------------------------------- Review
class ReviewCardOut(BaseModel):
    """Payload một thẻ trong hàng đợi review.

    Toàn bộ dữ liệu (nghĩa, ví dụ, mnemonic, cluster) đã được agent sinh sẵn và lưu DB
    TRƯỚC khi thẻ vào hàng đợi (file 00 mục 4.1) — endpoint này không gọi LLM.
    """

    id: str
    sense_id: str
    card_direction: str
    state: str
    due_at: str | None
    last_reviewed_at: str | None = None
    is_leech: bool
    reps: int
    lapses: int
    stability: float = 0.0
    difficulty: float = 0.0
    retrievability: float = 1.0

    surface_form: str
    item_type: str
    ipa: str | None = None
    cefr_level: str | None = None
    definition_en: str
    definition_vi: str | None = None
    part_of_speech: str | None = None
    register: str | None = None

    examples: list[ExampleOut] = Field(default_factory=list)
    mnemonics: list[MnemonicOut] = Field(default_factory=list)
    cluster_id: str | None = None
    interval_preview_days: dict[str, float] = Field(default_factory=dict)


class ReviewQueueOut(BaseModel):
    cards: list[ReviewCardOut]
    due_count: int
    new_count: int
    daily_new_word_goal: int


class AnswerRequest(BaseModel):
    rating: int = Field(ge=1, le=4)
    error_type: Literal["meaning", "collocation", "spelling", "register", "none"] | None = None


class AnswerResponse(BaseModel):
    card_id: str
    state: str
    due_at: str
    interval_days: float
    stability: float
    difficulty: float
    reps: int
    lapses: int
    is_leech: bool
    became_leech: bool
    adjustments: list[str] = Field(default_factory=list)
    followups: list[str] = Field(default_factory=list)


class ReviewStatsOut(BaseModel):
    due_today: int
    new_available: int
    reviewed_today: int
    streak_days: int
    retention_rate_7d: float | None
    retention_rate_30d: float | None
    total_cards: int
    leech_count: int


# --------------------------------------------------------------- Production
class ProductionAttemptCreate(BaseModel):
    card_id: str
    user_sentence: str
    essay_context: str | None = None


class ProductionAttemptOut(BaseModel):
    model_config = ORM
    id: str
    card_id: str
    user_sentence: str
    submitted_at: str
    is_correct: bool | None
    error_type: str | None
    feedback_text: str | None
    corrected_sentence: str | None
    graded_by_model: str | None
    graded_at: str | None

    @property
    def status(self) -> str:  # pragma: no cover - tiện ích hiển thị
        return "graded" if self.graded_at else "pending"


# ----------------------------------------------------------------- Clusters
class ClusterMemberOut(BaseModel):
    sense_id: str
    surface_form: str
    definition_en: str
    distinguishing_note: str | None = None


class ClusterOut(BaseModel):
    id: str
    cluster_label: str | None
    created_at: str
    members: list[ClusterMemberOut] = Field(default_factory=list)


class ClusterExerciseOption(BaseModel):
    sense_id: str
    surface_form: str


class ClusterExerciseOut(BaseModel):
    cluster_id: str
    cluster_label: str | None
    question_sentence: str
    correct_sense_id: str
    options: list[ClusterExerciseOption]
    explanation: str | None = None


# ---------------------------------------------------------------- Analytics
class AnalyticsOverviewOut(BaseModel):
    total_lexical_items: int
    total_cards: int
    cards_by_state: dict[str, int]
    reviews_last_7d: int
    retention_rate_7d: float | None
    retention_rate_30d: float | None
    streak_days: int
    daily_new_word_goal: int
    ramp_up: dict[str, Any]
    agent_cache: list[dict[str, Any]]


class ErrorBreakdownItem(BaseModel):
    error_type: str
    count: int
    share: float


class ErrorBreakdownOut(BaseModel):
    review_errors: list[ErrorBreakdownItem]
    production_errors: list[ErrorBreakdownItem]
    total_reviews_with_error_type: int
    total_production_attempts: int


class LeechOut(BaseModel):
    card_id: str
    sense_id: str
    surface_form: str
    definition_en: str
    card_direction: str
    lapses: int
    reps: int
    latest_mnemonic: str | None = None
    mnemonic_regenerated: bool = False
