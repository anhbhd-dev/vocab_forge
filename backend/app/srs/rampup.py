"""Ramp-up số từ mới mỗi ngày — file 02 mục 7.

Logic thuần, không chạm DB: tầng service nạp số liệu rồi gọi `evaluate_daily_goal`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

MIN_DAILY_NEW = 5
MAX_DAILY_NEW = 30
STEP = 5

RAISE_RETENTION_THRESHOLD = 0.85  # retention 7 ngày gần nhất
DUE_LOAD_MULTIPLIER = 1.5  # số thẻ due không vượt quá 1.5× số từ mới/ngày
LOWER_RETENTION_THRESHOLD = 0.75
LOWER_CONSECUTIVE_DAYS = 3


@dataclass
class RampUpDecision:
    current_goal: int
    recommended_goal: int
    action: str  # 'raise' | 'lower' | 'hold'
    reason: str

    @property
    def changed(self) -> bool:
        return self.recommended_goal != self.current_goal


def evaluate_daily_goal(
    current_goal: int,
    retention_7d: float | None,
    due_count_today: int,
    daily_retention_desc: Sequence[float] = (),
) -> RampUpDecision:
    """Quyết định tăng/giảm/giữ nguyên `daily_new_word_goal`.

    `daily_retention_desc`: retention theo từng ngày, mới nhất đứng đầu — dùng để kiểm
    tra điều kiện "< 75% trong 3 ngày LIÊN TIẾP".
    """
    recent = list(daily_retention_desc)[:LOWER_CONSECUTIVE_DAYS]
    if len(recent) == LOWER_CONSECUTIVE_DAYS and all(
        r < LOWER_RETENTION_THRESHOLD for r in recent
    ):
        lowered = max(MIN_DAILY_NEW, current_goal - STEP)
        return RampUpDecision(
            current_goal=current_goal,
            recommended_goal=lowered,
            action="lower",
            reason=(
                f"Retention < {LOWER_RETENTION_THRESHOLD:.0%} trong "
                f"{LOWER_CONSECUTIVE_DAYS} ngày liên tiếp — giảm từ mới, ưu tiên trả "
                "nợ review trước."
            ),
        )

    if retention_7d is None:
        return RampUpDecision(
            current_goal, current_goal, "hold", "Chưa đủ dữ liệu review 7 ngày."
        )

    if current_goal >= MAX_DAILY_NEW:
        return RampUpDecision(
            current_goal, current_goal, "hold", "Đã đạt mục tiêu 30 từ/ngày."
        )

    due_ceiling = current_goal * DUE_LOAD_MULTIPLIER
    if retention_7d >= RAISE_RETENTION_THRESHOLD and due_count_today <= due_ceiling:
        raised = min(MAX_DAILY_NEW, current_goal + STEP)
        return RampUpDecision(
            current_goal=current_goal,
            recommended_goal=raised,
            action="raise",
            reason=(
                f"Retention 7 ngày {retention_7d:.0%} ≥ "
                f"{RAISE_RETENTION_THRESHOLD:.0%} và tải review "
                f"({due_count_today}) ≤ {due_ceiling:.0f} — có thể tăng."
            ),
        )

    if retention_7d < RAISE_RETENTION_THRESHOLD:
        reason = (
            f"Retention 7 ngày {retention_7d:.0%} chưa đạt "
            f"{RAISE_RETENTION_THRESHOLD:.0%} — giữ nguyên."
        )
    else:
        reason = (
            f"Tải review hôm nay ({due_count_today}) vượt "
            f"{DUE_LOAD_MULTIPLIER:g}× mục tiêu — giữ nguyên để tránh dồn nợ."
        )
    return RampUpDecision(current_goal, current_goal, "hold", reason)
