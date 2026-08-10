"""Tiện ích thời gian.

Toàn hệ thống dùng UTC, lưu dạng chuỗi ISO-8601 (khớp kiểu TEXT trong schema file 01,
giữ nguyên khi chuyển sang PostgreSQL). `due_at` giữ độ chính xác tới micro-giây —
bắt buộc theo file 01 mục 3 để không mất thứ tự ôn trong cùng một ngày.

QUAN TRỌNG: `to_iso` LUÔN xuất đủ 6 chữ số micro-giây. Truy vấn hàng đợi so sánh
`due_at <= now` trực tiếp trên cột TEXT, nên mọi giá trị phải cùng độ rộng thì thứ tự
từ điển mới trùng với thứ tự thời gian. `datetime.isoformat()` mặc định BỎ phần
micro-giây khi bằng 0, tạo ra chuỗi ngắn hơn — chính là cái bẫy cần chặn ở đây.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def from_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    # SQLite default `datetime('now')` trả "YYYY-MM-DD HH:MM:SS" (không có tzinfo).
    normalized = value.replace(" ", "T")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
