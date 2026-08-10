"""Test SRS engine — ưu tiên cao nhất theo file 04 yêu cầu #6.

Các case bắt buộc theo spec:
  - New → Learning → Review
  - Review → Relearning khi Again
  - ngưỡng leech detection
  - error_type adjustment KHÔNG phá vỡ FSRS core
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.time import utcnow
from app.srs.engine import (
    RATING_AGAIN,
    RATING_EASY,
    RATING_GOOD,
    RATING_HARD,
    CardState,
    SRSEngine,
    next_interval_preview,
)
from app.srs.leech import LEECH_LAPSE_THRESHOLD, is_leech, recent_again_ratio


@pytest.fixture
def engine() -> SRSEngine:
    # Tắt fuzzing để interval xác định, test không flaky.
    return SRSEngine(enable_fuzzing=False)


def advance(card: CardState, outcome) -> CardState:
    """Chuyển ReviewOutcome thành CardState cho lần review kế tiếp."""
    return CardState(
        state=outcome.state,
        stability=outcome.stability,
        difficulty=outcome.difficulty,
        due_at=outcome.due_at,
        last_reviewed_at=outcome.last_reviewed_at,
        reps=outcome.reps,
        lapses=outcome.lapses,
        is_leech=outcome.is_leech,
        learning_step=outcome.learning_step,
    )


# --------------------------------------------------------- state machine
class TestStateMachine:
    def test_new_card_goes_to_learning(self, engine):
        outcome = engine.process_review(CardState(), RATING_GOOD)
        assert outcome.state == "learning"
        assert outcome.reps == 1
        assert outcome.stability > 0
        assert outcome.difficulty > 0
        # learning step đầu là phút, không phải ngày
        assert outcome.interval_days < 1

    def test_learning_graduates_to_review(self, engine):
        card = CardState()
        outcome = engine.process_review(card, RATING_GOOD)
        # Đi hết chuỗi learning steps (1 phút → 10 phút) thì tốt nghiệp
        for _ in range(5):
            if outcome.state == "review":
                break
            outcome = engine.process_review(advance(card, outcome), RATING_GOOD)
            card = advance(card, outcome)
        assert outcome.state == "review"
        assert outcome.interval_days >= 1

    def test_easy_on_new_card_skips_to_review(self, engine):
        outcome = engine.process_review(CardState(), RATING_EASY)
        assert outcome.state == "review"
        assert outcome.interval_days >= 1

    def test_review_to_relearning_on_again(self, engine):
        card = CardState(
            state="review",
            stability=20.0,
            difficulty=5.0,
            due_at=utcnow(),
            last_reviewed_at=utcnow() - timedelta(days=20),
            reps=5,
        )
        outcome = engine.process_review(card, RATING_AGAIN)
        assert outcome.state == "relearning"
        assert outcome.lapses == 1
        assert outcome.stability < card.stability
        assert outcome.interval_days < 1  # quay lại chuỗi bước ngắn

    def test_relearning_returns_to_review(self, engine):
        card = CardState(
            state="relearning",
            stability=5.0,
            difficulty=6.0,
            due_at=utcnow(),
            last_reviewed_at=utcnow() - timedelta(minutes=10),
            reps=6,
            lapses=1,
            learning_step=0,
        )
        outcome = engine.process_review(card, RATING_GOOD)
        assert outcome.state == "review"

    def test_again_on_learning_does_not_count_as_lapse(self, engine):
        """Lapse chỉ đếm khi quên từ state Review (file 02 mục 6)."""
        card = CardState(
            state="learning",
            stability=2.0,
            difficulty=5.0,
            due_at=utcnow(),
            last_reviewed_at=utcnow(),
            reps=1,
            learning_step=1,
        )
        outcome = engine.process_review(card, RATING_AGAIN)
        assert outcome.lapses == 0

    def test_invalid_rating_raises(self, engine):
        with pytest.raises(ValueError):
            engine.process_review(CardState(), 5)

    def test_hard_gives_shorter_interval_than_good(self, engine):
        card = CardState(
            state="review",
            stability=30.0,
            difficulty=5.0,
            due_at=utcnow(),
            last_reviewed_at=utcnow() - timedelta(days=30),
            reps=6,
        )
        hard = engine.process_review(card, RATING_HARD)
        good = engine.process_review(card, RATING_GOOD)
        easy = engine.process_review(card, RATING_EASY)
        assert hard.interval_days < good.interval_days < easy.interval_days


# ---------------------------------------------------------------- leech
class TestLeechDetection:
    def test_lapse_threshold(self):
        assert is_leech(LEECH_LAPSE_THRESHOLD, [])
        assert not is_leech(LEECH_LAPSE_THRESHOLD - 1, [])

    def test_three_agains_in_last_five(self):
        assert is_leech(2, [1, 3, 1, 3, 1])
        assert not is_leech(2, [1, 3, 1, 3, 3])

    def test_partial_window_is_not_leech(self):
        """Một lần Again duy nhất trên tổng 1 review chưa phải leech."""
        assert not is_leech(1, [1])
        assert not is_leech(1, [1, 1])

    def test_recent_again_ratio(self):
        assert recent_again_ratio([1, 1, 3, 3, 3]) == pytest.approx(0.4)
        assert recent_again_ratio([]) == 0.0

    def test_engine_flags_leech_and_requests_new_mnemonic(self, engine):
        card = CardState(
            state="review",
            stability=10.0,
            difficulty=8.0,
            due_at=utcnow(),
            last_reviewed_at=utcnow() - timedelta(days=10),
            reps=10,
            lapses=LEECH_LAPSE_THRESHOLD - 1,
        )
        outcome = engine.process_review(card, RATING_AGAIN)
        assert outcome.is_leech is True
        assert outcome.became_leech is True
        # Khác Anki: không suspend im lặng mà sinh mnemonic mới (file 02 mục 4).
        assert "regenerate_mnemonic" in outcome.followups

    def test_already_leech_does_not_retrigger(self, engine):
        card = CardState(
            state="review",
            stability=10.0,
            difficulty=8.0,
            due_at=utcnow(),
            last_reviewed_at=utcnow() - timedelta(days=10),
            reps=12,
            lapses=LEECH_LAPSE_THRESHOLD + 2,
            is_leech=True,
        )
        outcome = engine.process_review(card, RATING_AGAIN)
        assert outcome.is_leech is True
        assert outcome.became_leech is False
        assert "regenerate_mnemonic" not in outcome.followups


# ------------------------------------------------ error_type adjustment
class TestErrorTypeAdjustment:
    """File 02 mục 5 — phần MỞ RỘNG ngoài FSRS chuẩn."""

    @pytest.fixture
    def mature_card(self) -> CardState:
        return CardState(
            state="review",
            stability=20.0,
            difficulty=5.0,
            due_at=utcnow(),
            last_reviewed_at=utcnow() - timedelta(days=20),
            reps=8,
        )

    def test_spelling_barely_reduces_interval(self, engine, mature_card):
        baseline = engine.process_review(mature_card, RATING_AGAIN)
        spelling = engine.process_review(
            mature_card, RATING_AGAIN, error_type="spelling"
        )
        # Pseudocode file 02 mục 6: giữ ít nhất 0.9× stability cũ.
        assert spelling.stability == pytest.approx(mature_card.stability * 0.9)
        assert spelling.interval_days > baseline.interval_days
        # Sai chính tả không phải quên nghĩa → không tính lapse, không hạ state.
        assert spelling.lapses == 0
        assert spelling.state == "review"

    def test_register_keeps_academic_interval(self, engine, mature_card):
        outcome = engine.process_review(
            mature_card, RATING_AGAIN, error_type="register"
        )
        assert outcome.stability == pytest.approx(mature_card.stability)
        assert outcome.lapses == 0
        assert outcome.state == "review"
        assert "register_discrimination_exercise" in outcome.followups

    def test_collocation_reduces_moderately(self, engine, mature_card):
        baseline = engine.process_review(mature_card, RATING_AGAIN)
        collocation = engine.process_review(
            mature_card, RATING_AGAIN, error_type="collocation"
        )
        register = engine.process_review(
            mature_card, RATING_AGAIN, error_type="register"
        )
        # Nặng hơn register, nhẹ hơn Again trần trụi.
        assert baseline.stability < collocation.stability < register.stability
        # Hiểu sai kết hợp từ vẫn là lỗi liên quan trí nhớ → có tính lapse.
        assert collocation.lapses == 1
        assert "show_more_examples" in collocation.followups

    def test_meaning_is_full_again_penalty(self, engine, mature_card):
        baseline = engine.process_review(mature_card, RATING_AGAIN)
        meaning = engine.process_review(
            mature_card, RATING_AGAIN, error_type="meaning"
        )
        # KHÔNG được nhẹ tay: nhầm nghĩa phải phạt đúng như Again chuẩn.
        assert meaning.stability == pytest.approx(baseline.stability)
        assert meaning.state == baseline.state == "relearning"
        assert meaning.lapses == 1
        assert "prioritize_basic_direction" in meaning.followups

    def test_error_type_does_not_touch_successful_reviews(self, engine, mature_card):
        """Được Good/Easy thì không có gì để 'cứu' — FSRS core phải nguyên vẹn."""
        for rating in (RATING_HARD, RATING_GOOD, RATING_EASY):
            baseline = engine.process_review(mature_card, rating)
            for error_type in ("spelling", "register", "collocation", "meaning"):
                adjusted = engine.process_review(
                    mature_card, rating, error_type=error_type
                )
                assert adjusted.stability == pytest.approx(baseline.stability)
                assert adjusted.difficulty == pytest.approx(baseline.difficulty)
                assert adjusted.state == baseline.state

    def test_difficulty_never_altered_by_error_type(self, engine, mature_card):
        """Điều chỉnh của ta chỉ chạm stability/interval, KHÔNG chạm D của FSRS."""
        baseline = engine.process_review(mature_card, RATING_AGAIN)
        for error_type in ("spelling", "register", "collocation", "meaning"):
            adjusted = engine.process_review(
                mature_card, RATING_AGAIN, error_type=error_type
            )
            assert adjusted.difficulty == pytest.approx(baseline.difficulty)

    def test_adjustment_is_reported(self, engine, mature_card):
        outcome = engine.process_review(
            mature_card, RATING_AGAIN, error_type="spelling"
        )
        assert outcome.adjustments, "phải giải thích vì sao interval được giữ"
        assert "spelling" in outcome.adjustments[0]

    def test_new_card_with_error_type_does_not_crash(self, engine):
        outcome = engine.process_review(CardState(), RATING_AGAIN, error_type="spelling")
        assert outcome.state in ("learning", "relearning")


# -------------------------------------------------------------- misc
class TestEngineExtras:
    def test_retrievability_decreases_over_time(self, engine):
        card = CardState(
            state="review",
            stability=10.0,
            difficulty=5.0,
            due_at=utcnow() + timedelta(days=10),
            last_reviewed_at=utcnow(),
        )
        now = engine.retrievability(card, utcnow())
        later = engine.retrievability(card, utcnow() + timedelta(days=30))
        assert 0 <= later < now <= 1

    def test_interval_preview_is_monotonic(self, engine):
        preview = next_interval_preview(CardState(), engine)
        assert set(preview) == {"again", "hard", "good", "easy"}
        assert preview["again"] <= preview["hard"] <= preview["good"] <= preview["easy"]

    def test_due_at_keeps_sub_day_precision(self, engine):
        """file 01 mục 3: due_at phải giữ giờ/phút để phân biệt thứ tự trong ngày."""
        outcome = engine.process_review(CardState(), RATING_GOOD)
        assert outcome.due_at.hour or outcome.due_at.minute or outcome.due_at.second
        assert outcome.due_at > outcome.last_reviewed_at

    def test_elapsed_and_scheduled_days_logged(self, engine):
        last = utcnow() - timedelta(days=6)
        card = CardState(
            state="review",
            stability=10.0,
            difficulty=5.0,
            due_at=last + timedelta(days=10),
            last_reviewed_at=last,
            reps=3,
        )
        outcome = engine.process_review(card, RATING_GOOD)
        assert outcome.elapsed_days == pytest.approx(6, abs=0.01)
        assert outcome.scheduled_days == pytest.approx(10, abs=0.01)
