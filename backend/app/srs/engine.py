"""SRS Engine — wrapper quanh FSRS + phần mở rộng error_type-aware scheduling.

Triển khai theo `docs/02_SRS_ENGINE_SPEC.md`:
  - mục 3: state machine New → Learning → Review → Relearning
  - mục 4: leech detection (tách sang `app/srs/leech.py`)
  - mục 5: điều chỉnh lịch ôn theo `error_type` — ĐÂY KHÔNG PHẢI FSRS CHUẨN
  - mục 6: pseudocode luồng xử lý một lần review

PHIÊN BẢN FSRS
--------------
Spec (file 02 mục 1, file 04 mục STACK) yêu cầu FSRS-7 và yêu cầu kiểm tra thư viện
trước khi code. Tại thời điểm implement, bản `fsrs` (py-fsrs) mới nhất trên PyPI là
6.3.2 và **chưa có FSRS-7**: `Scheduler._next_interval` vẫn `round()` về số ngày
nguyên (xem `FSRS_SUPPORTS_FRACTIONAL_INTERVAL` bên dưới), tức chưa có fractional
interval — chính là điểm khác biệt cốt lõi của FSRS-7 theo spec.

=> Dùng FSRS-6 (pin `fsrs==6.3.2`) làm engine lõi, đúng phương án fallback tạm thời
   spec cho phép.

TODO(FSRS-7): khi py-fsrs phát hành bản hỗ trợ FSRS-7, chỉ cần:
   1. nâng pin trong pyproject.toml,
   2. bỏ `_fractional_interval_days()` bên dưới và dùng interval fractional native,
   3. chạy lại `tests/test_srs_engine.py` (đã viết để bám hành vi, không bám version).
Toàn bộ phần còn lại của hệ thống không cần đổi vì `due_at` đã lưu datetime đầy đủ tới
micro-giây (file 01 mục 3), sẵn sàng cho same-day review.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from fsrs import Card as FSRSCard
from fsrs import Rating as FSRSRating
from fsrs import Scheduler
from fsrs import State as FSRSState

from app.core.config import settings
from app.core.time import utcnow
from app.srs.leech import is_leech

# FSRS-6 trả interval số nguyên ngày. Cờ này để test và code phía trên biết
# đang chạy engine bản nào mà không cần đọc version string.
FSRS_SUPPORTS_FRACTIONAL_INTERVAL = False
FSRS_VARIANT = "FSRS-6"

# Map state nội bộ (file 01: 'new'|'learning'|'review'|'relearning') ↔ state của py-fsrs.
# py-fsrs KHÔNG có 'new': thẻ chưa review được biểu diễn bằng state=Learning, step=0,
# stability=None, difficulty=None. Ta giữ 'new' ở tầng DB vì API/queue cần phân biệt
# thẻ mới với thẻ đang học (ramp-up đếm theo số thẻ 'new' đưa vào mỗi ngày).
_FSRS_TO_DB_STATE = {
    FSRSState.Learning: "learning",
    FSRSState.Review: "review",
    FSRSState.Relearning: "relearning",
}
_DB_TO_FSRS_STATE = {
    "learning": FSRSState.Learning,
    "review": FSRSState.Review,
    "relearning": FSRSState.Relearning,
}

RATING_AGAIN = 1
RATING_HARD = 2
RATING_GOOD = 3
RATING_EASY = 4

# --- Hệ số điều chỉnh theo error_type (file 02 mục 5) ---
# Ý nghĩa: sàn stability được giữ lại so với stability CŨ của thẻ, tính theo mức độ
# "lỗi này có thực sự là quên nghĩa hay không".
#   spelling: gần như không phạt — đúng con số 0.9 trong pseudocode file 02 mục 6.
#   register: dùng đúng nghĩa + đúng collocation, chỉ sai văn phong → không phạt
#             interval học thuật (giữ nguyên stability cũ), thay vào đó trigger bài tập
#             phân biệt register.
#   collocation: hiểu nghĩa nhưng sai giới từ/kết hợp → phạt VỪA PHẢI, không nhẹ như
#             spelling cũng không nặng như meaning.
#   meaning: nhầm hẳn nghĩa → KHÔNG có sàn, để FSRS phạt đầy đủ như Again chuẩn.
_STABILITY_FLOOR_RATIO = {
    "spelling": 0.9,
    "register": 1.0,
    "collocation": 0.6,
}


@dataclass
class CardState:
    """Ảnh chụp trạng thái thẻ mà engine cần — tách khỏi SQLAlchemy model để
    `engine.py` là logic thuần, test được không cần DB (file 04 yêu cầu #6)."""

    state: str = "new"
    stability: float | None = None
    difficulty: float | None = None
    due_at: datetime | None = None
    last_reviewed_at: datetime | None = None
    reps: int = 0
    lapses: int = 0
    is_leech: bool = False
    learning_step: int | None = 0


@dataclass
class ReviewOutcome:
    """Kết quả một lần review: giá trị mới của card + dữ liệu để ghi review_log."""

    state: str
    stability: float
    difficulty: float
    due_at: datetime
    last_reviewed_at: datetime
    reps: int
    lapses: int
    is_leech: bool
    learning_step: int | None
    elapsed_days: float | None
    scheduled_days: float | None
    interval_days: float
    became_leech: bool = False
    # Giải thích vì sao interval bị/không bị điều chỉnh — trả ra API để UI hiển thị
    # và để debug phần mở rộng ngoài FSRS.
    adjustments: list[str] = field(default_factory=list)
    # Hành động hệ quả cho tầng service (không thực thi trong engine để engine
    # không phụ thuộc DB / job queue).
    followups: list[str] = field(default_factory=list)


class SRSEngine:
    """Bọc `fsrs.Scheduler`. Toàn bộ can thiệp ngoài FSRS chuẩn nằm trong lớp này."""

    def __init__(
        self,
        desired_retention: float | None = None,
        maximum_interval: int | None = None,
        enable_fuzzing: bool | None = None,
    ) -> None:
        self.desired_retention = (
            desired_retention
            if desired_retention is not None
            else settings.fsrs_desired_retention
        )
        self.scheduler = Scheduler(
            desired_retention=self.desired_retention,
            maximum_interval=(
                maximum_interval
                if maximum_interval is not None
                else settings.fsrs_maximum_interval
            ),
            enable_fuzzing=(
                enable_fuzzing
                if enable_fuzzing is not None
                else settings.fsrs_enable_fuzzing
            ),
        )

    # ------------------------------------------------------------------ helpers

    def _to_fsrs_card(self, card: CardState) -> FSRSCard:
        if card.state == "new":
            # Thẻ chưa từng review: để stability/difficulty = None cho FSRS tự khởi tạo
            # bằng `_initial_stability` thay vì nhận số 0 vô nghĩa từ DB default.
            return FSRSCard(
                state=FSRSState.Learning,
                step=0,
                stability=None,
                difficulty=None,
                due=card.due_at or utcnow(),
                last_review=None,
            )
        return FSRSCard(
            state=_DB_TO_FSRS_STATE[card.state],
            step=card.learning_step,
            stability=card.stability or None,
            difficulty=card.difficulty or None,
            due=card.due_at or utcnow(),
            last_review=card.last_reviewed_at,
        )

    def _fractional_interval_days(self, stability: float) -> float:
        """Interval (ngày, dạng phân số) suy từ stability theo đường cong quên FSRS.

        Bản sao công thức `Scheduler._next_interval` NHƯNG bỏ `round()`. Dùng cho nhánh
        điều chỉnh theo error_type: khi ta tự tính lại due từ stability đã chỉnh, việc
        làm tròn về ngày nguyên sẽ xoá mất chênh lệch nhỏ (vd giữ 0.9× stability của
        một thẻ interval 2 ngày). Cũng chính là hành vi fractional mà FSRS-7 hứa hẹn.
        """
        decay = -self.scheduler.parameters[20]
        factor = 0.9 ** (1 / decay) - 1
        interval = (stability / factor) * (
            (self.desired_retention ** (1 / decay)) - 1
        )
        return min(max(interval, 0.0), float(self.scheduler.maximum_interval))

    def retrievability(self, card: CardState, at: datetime | None = None) -> float:
        """R hiện tại — dùng cho analytics và sắp xếp hàng đợi."""
        return self.scheduler.get_card_retrievability(
            self._to_fsrs_card(card), at or utcnow()
        )

    # -------------------------------------------------------------- main entry

    def process_review(
        self,
        card: CardState,
        rating: int,
        error_type: str | None = None,
        now: datetime | None = None,
        recent_ratings: Sequence[int] = (),
    ) -> ReviewOutcome:
        """Xử lý một lần review — theo pseudocode file 02 mục 6.

        `recent_ratings`: rating của các lần review TRƯỚC (mới nhất đứng đầu), do tầng
        service nạp từ `review_logs`; engine không truy cập DB.
        """
        if rating not in (RATING_AGAIN, RATING_HARD, RATING_GOOD, RATING_EASY):
            raise ValueError(f"rating phải thuộc 1..4, nhận: {rating}")

        now = now or utcnow()
        old_state = card.state
        old_stability = card.stability or 0.0

        # 1. Tính D, S mới theo công thức FSRS (thư viện lo phần này).
        fsrs_card = self._to_fsrs_card(card)
        elapsed_days = (
            (now - card.last_reviewed_at).total_seconds() / 86400.0
            if card.last_reviewed_at
            else None
        )
        scheduled_days = (
            (card.due_at - card.last_reviewed_at).total_seconds() / 86400.0
            if card.due_at and card.last_reviewed_at
            else None
        )

        updated, _log = self.scheduler.review_card(
            fsrs_card, FSRSRating(rating), review_datetime=now
        )

        new_state = _FSRS_TO_DB_STATE[updated.state]
        new_stability = float(updated.stability or 0.0)
        new_difficulty = float(updated.difficulty or 0.0)
        due_at = updated.due
        interval_days = (due_at - now).total_seconds() / 86400.0
        adjustments: list[str] = []
        followups: list[str] = []
        # None = thẻ không nằm trong chuỗi learning/relearning steps nữa.
        learning_step_override: int | None | str = "unset"

        # 2. ĐIỀU CHỈNH THEO error_type — phần MỞ RỘNG NGOÀI FSRS CHUẨN (file 02 mục 5).
        #
        # Nguyên tắc: không phải mọi lỗi đều là "quên" theo nghĩa SRS. Tách lỗi trí nhớ
        # (memory failure) khỏi lỗi sử dụng (usage failure) để không đốt review budget
        # vào việc lặp lại nghĩa mà user đã nhớ rõ.
        #
        # Chỉ can thiệp khi FSRS thực sự đã phạt (stability giảm so với trước). Nếu
        # user vẫn được Good/Easy thì không có gì để "cứu", giữ nguyên kết quả FSRS.
        floor_ratio = _STABILITY_FLOOR_RATIO.get(error_type or "")
        penalised = new_stability < old_stability and old_stability > 0

        if floor_ratio is not None and penalised:
            floored = max(new_stability, old_stability * floor_ratio)
            if floored > new_stability:
                new_stability = floored
                interval_days = self._fractional_interval_days(new_stability)
                due_at = now + timedelta(days=interval_days)
                adjustments.append(
                    f"error_type={error_type}: giữ sàn stability {floor_ratio:g}× "
                    f"stability cũ ({old_stability:.2f} → {new_stability:.2f})"
                )

            # Nếu sau khi giữ sàn mà interval vẫn dài hơn một ngày thì thẻ KHÔNG còn
            # thuộc về chuỗi relearning steps ngắn (10 phút) nữa — để state
            # 'relearning' đi kèm due 12 ngày là mâu thuẫn: lần review kế tiếp sẽ bị
            # ép chạy lại learning steps dù ta vừa kết luận trí nhớ vẫn còn tốt.
            # Khôi phục về 'review' cho nhất quán giữa state và interval.
            if (
                old_state == "review"
                and new_state == "relearning"
                and interval_days >= 1.0
            ):
                new_state = "review"
                learning_step_override = None
                adjustments.append(
                    f"error_type={error_type}: giữ state 'review', không hạ xuống "
                    "'relearning' (lỗi sử dụng, không phải lỗi trí nhớ)"
                )

        # Hệ quả kèm theo cho từng loại lỗi (file 02 mục 5, cột "Điều chỉnh").
        if error_type == "meaning":
            # Nhầm hẳn nghĩa → phải củng cố nhận diện cơ bản trước khi cho sản xuất.
            followups.append("prioritize_basic_direction")
            adjustments.append(
                "error_type=meaning: phạt đầy đủ như Again chuẩn, ưu tiên card "
                "en_to_vi trước khi cho làm production"
            )
        elif error_type == "collocation":
            # Hiểu nghĩa nhưng sai kết hợp từ → cần thêm ví dụ câu, không phải lặp
            # định nghĩa.
            followups.append("show_more_examples")
        elif error_type == "register":
            followups.append("register_discrimination_exercise")

        # 3. Lapses — chỉ đếm khi quên từ trạng thái Review (đúng file 02 mục 6).
        #    Ngoại lệ mở rộng: lỗi chính tả/văn phong không tính là "quên".
        is_memory_failure = rating == RATING_AGAIN and error_type not in (
            "spelling",
            "register",
        )
        lapses = card.lapses + (
            1 if is_memory_failure and old_state == "review" else 0
        )

        # 4. Leech check (file 02 mục 4).
        ratings_window = [rating, *list(recent_ratings)]
        leech = is_leech(lapses, ratings_window)
        became_leech = leech and not card.is_leech
        if became_leech:
            # Khác Anki: không suspend im lặng mà sinh lại mnemonic bằng cách tiếp cận
            # KHÁC (file 02 mục 4) — service sẽ enqueue job này.
            followups.append("regenerate_mnemonic")

        return ReviewOutcome(
            state=new_state,
            stability=new_stability,
            difficulty=new_difficulty,
            due_at=due_at,
            last_reviewed_at=now,
            reps=card.reps + 1,
            lapses=lapses,
            is_leech=leech,
            learning_step=(
                updated.step
                if learning_step_override == "unset"
                else learning_step_override  # type: ignore[arg-type]
            ),
            elapsed_days=elapsed_days,
            scheduled_days=scheduled_days,
            interval_days=interval_days,
            became_leech=became_leech,
            adjustments=adjustments,
            followups=followups,
        )


_default_engine: SRSEngine | None = None


def get_engine() -> SRSEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = SRSEngine()
    return _default_engine


def next_interval_preview(card: CardState, engine: SRSEngine | None = None) -> dict[str, float]:
    """Interval dự kiến cho từng rating — để UI hiển thị '1m / 10m / 4d / 9d' trên nút.

    Không ghi gì xuống DB, chỉ mô phỏng.
    """
    engine = engine or get_engine()
    preview: dict[str, float] = {}
    now = utcnow()
    for name, rating in (
        ("again", RATING_AGAIN),
        ("hard", RATING_HARD),
        ("good", RATING_GOOD),
        ("easy", RATING_EASY),
    ):
        outcome = engine.process_review(card, rating, now=now)
        preview[name] = round(outcome.interval_days, 6)
    return preview


__all__ = [
    "CardState",
    "FSRS_VARIANT",
    "FSRS_SUPPORTS_FRACTIONAL_INTERVAL",
    "ReviewOutcome",
    "SRSEngine",
    "get_engine",
    "next_interval_preview",
]
