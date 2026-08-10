"""Ramp-up số từ mới mỗi ngày — file 02 mục 7."""

from __future__ import annotations

from app.srs.rampup import (
    MAX_DAILY_NEW,
    MIN_DAILY_NEW,
    evaluate_daily_goal,
)


def test_raises_when_retention_good_and_load_light():
    decision = evaluate_daily_goal(
        current_goal=10, retention_7d=0.90, due_count_today=12
    )
    assert decision.action == "raise"
    assert decision.recommended_goal == 15
    assert decision.changed


def test_holds_when_retention_below_threshold():
    decision = evaluate_daily_goal(
        current_goal=10, retention_7d=0.80, due_count_today=5
    )
    assert decision.action == "hold"
    assert not decision.changed


def test_holds_when_review_debt_too_high():
    """Điều kiện thứ 2: số thẻ due không vượt quá 1.5× số từ mới/ngày."""
    decision = evaluate_daily_goal(
        current_goal=10, retention_7d=0.95, due_count_today=16
    )
    assert decision.action == "hold"


def test_lowers_after_three_consecutive_bad_days():
    decision = evaluate_daily_goal(
        current_goal=20,
        retention_7d=0.70,
        due_count_today=40,
        daily_retention_desc=[0.70, 0.72, 0.68, 0.90],
    )
    assert decision.action == "lower"
    assert decision.recommended_goal == 15


def test_two_bad_days_is_not_enough_to_lower():
    decision = evaluate_daily_goal(
        current_goal=20,
        retention_7d=0.80,
        due_count_today=10,
        daily_retention_desc=[0.70, 0.72, 0.88],
    )
    assert decision.action == "hold"


def test_never_exceeds_thirty():
    decision = evaluate_daily_goal(
        current_goal=MAX_DAILY_NEW, retention_7d=0.99, due_count_today=1
    )
    assert decision.recommended_goal == MAX_DAILY_NEW
    assert decision.action == "hold"


def test_never_drops_below_floor():
    decision = evaluate_daily_goal(
        current_goal=MIN_DAILY_NEW,
        retention_7d=0.50,
        due_count_today=50,
        daily_retention_desc=[0.4, 0.4, 0.4],
    )
    assert decision.recommended_goal == MIN_DAILY_NEW


def test_holds_without_enough_data():
    decision = evaluate_daily_goal(
        current_goal=10, retention_7d=None, due_count_today=0
    )
    assert decision.action == "hold"
