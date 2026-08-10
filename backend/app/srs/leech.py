"""Leech detection — file 02 mục 4.

Thẻ bị đánh dấu leech khi:
  - `lapses >= 8` (số lần quên từ trạng thái Review), HOẶC
  - trong 5 lần review gần nhất có >= 3 lần rating = Again.

Khác Anki ở phần XỬ LÝ (không suspend im lặng): caller phải trigger Mnemonic Agent
sinh mnemonic MỚI khi thẻ vừa chuyển thành leech — xem `app/services/leech_service.py`.
"""

from __future__ import annotations

from collections.abc import Sequence

LEECH_LAPSE_THRESHOLD = 8
LEECH_RECENT_WINDOW = 5
LEECH_RECENT_AGAIN_THRESHOLD = 3

RATING_AGAIN = 1


def recent_again_ratio(recent_ratings: Sequence[int]) -> float:
    """Tỉ lệ Again trong cửa sổ 5 lần review gần nhất (mới nhất đứng đầu)."""
    window = list(recent_ratings)[:LEECH_RECENT_WINDOW]
    if not window:
        return 0.0
    return sum(1 for r in window if r == RATING_AGAIN) / len(window)


def is_leech(lapses: int, recent_ratings: Sequence[int]) -> bool:
    if lapses >= LEECH_LAPSE_THRESHOLD:
        return True
    window = list(recent_ratings)[:LEECH_RECENT_WINDOW]
    # Chỉ xét khi đã đủ dữ liệu cửa sổ, tránh đánh dấu leech oan cho thẻ mới
    # (vd 1 lần Again duy nhất trên tổng 1 review = ratio 1.0 nhưng chưa phải leech).
    if len(window) < LEECH_RECENT_WINDOW:
        return False
    return sum(1 for r in window if r == RATING_AGAIN) >= LEECH_RECENT_AGAIN_THRESHOLD
