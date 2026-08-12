"""Sinh audio phát âm bằng Kokoro-82M chạy local — KHÔNG bao giờ gọi ở vòng review.

VÌ SAO NẰM Ở VÒNG AGENT
-----------------------
Ràng buộc kiến trúc quan trọng nhất của app (file 00 mục 4): vòng review là fast path,
không I/O ngoài. TTS tuy không phải LLM nhưng vẫn là lời gọi mạng + tính toán nặng —
gọi lúc người học lật thẻ là phá đúng nguyên tắc đó. Nên audio được sinh SẴN trong
enrichment (chạy nền), lưu ra file, và vòng review chỉ trả về một đường dẫn tĩnh.

CACHE
-----
Tên file = sha256(text + voice + model). Cùng một từ ôn hàng chục lần chỉ tổng hợp một
lần duy nhất; ingestion trùng từ giữa các user cũng dùng lại luôn. Cache nằm trên volume
Docker nên sống qua các lần rebuild container.

SUY BIẾN AN TOÀN
----------------
Kokoro không chạy / không với tới được thì `synthesize()` trả None và ghi log cảnh báo.
Enrichment vẫn hoàn tất, thẻ vẫn tạo, chỉ là không có nút phát âm. Tuyệt đối không để
TTS làm hỏng cả pipeline vì nó là tính năng phụ trợ.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Giới hạn số lời gọi TTS đồng thời: Kokoro trên CPU chạy xấp xỉ realtime, bắn 20 câu
# cùng lúc chỉ làm tất cả cùng chậm và ăn hết RAM container.
#
# Mức 4 từng làm sập trải nghiệm: lô backfill giọng nam (~1200 lượt) đẩy container TTS
# lên ~490% CPU và 4.4/7.4GB RAM, process backend hầu như không được lên lịch chạy nữa —
# cả những endpoint tĩnh không chạm DB cũng timeout hàng chục giây. Vòng REVIEW phải là
# fast path, nên vòng agent chạy nền KHÔNG được phép giành hết máy: sinh audio chậm gấp
# đôi thì không ai nhận ra, app đứng hình thì nhận ra ngay.
_semaphore = asyncio.Semaphore(settings.tts_max_concurrency)


def audio_dir() -> Path:
    path = Path(settings.audio_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_key(text: str, voice: str) -> str:
    raw = f"{settings.tts_model}|{voice}|{text.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def audio_url_for(relative_path: str | None) -> str | None:
    """Đường dẫn lưu trong DB → URL trình duyệt gọi được."""
    if not relative_path:
        return None
    return f"/audio/{relative_path}"


async def synthesize(text: str, voice: str | None = None) -> str | None:
    """Tổng hợp `text` thành file audio, trả về đường dẫn tương đối (vd `a1b2c3.mp3`).

    Trả None nếu TTS tắt hoặc lỗi — người gọi cứ tiếp tục bình thường.
    """
    text = (text or "").strip()
    if not text or not settings.tts_enabled:
        return None

    voice = voice or settings.tts_voice
    name = f"{_cache_key(text, voice)}.mp3"
    target = audio_dir() / name

    # Cache hit: khỏi gọi lại. File rỗng coi như hỏng, tổng hợp lại.
    if target.exists() and target.stat().st_size > 0:
        return name

    payload = {
        "model": settings.tts_model,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
        "speed": settings.tts_speed,
    }

    async with _semaphore:
        try:
            async with httpx.AsyncClient(timeout=settings.tts_timeout_seconds) as client:
                resp = await client.post(
                    f"{settings.tts_base_url.rstrip('/')}/audio/speech",
                    json=payload,
                )
        except httpx.HTTPError as exc:
            logger.warning("TTS không với tới được (%s): %s", settings.tts_base_url, exc)
            return None

        if resp.status_code >= 400:
            logger.warning("TTS HTTP %d: %s", resp.status_code, resp.text[:300])
            return None

        data = resp.content
        if not data:
            logger.warning("TTS trả về audio rỗng cho '%s'", text[:60])
            return None

        # Ghi ra file tạm rồi đổi tên: tránh để lại file nửa vời nếu process chết giữa
        # chừng, vì lần sau cache sẽ tưởng file đó hợp lệ.
        tmp = target.with_suffix(".mp3.part")
        try:
            tmp.write_bytes(data)
            tmp.replace(target)
        except OSError as exc:
            logger.warning("Không ghi được file audio %s: %s", target, exc)
            return None

    logger.info("TTS đã sinh %s (%d bytes) cho '%s'", name, len(data), text[:60])
    return name


async def synthesize_many(
    texts: list[str], voice: str | None = None
) -> list[str | None]:
    """Tổng hợp nhiều chuỗi song song (đã bị semaphore ghìm lại ở mức an toàn)."""
    if not texts:
        return []
    results = await asyncio.gather(
        *(synthesize(t, voice) for t in texts), return_exceptions=True
    )
    out: list[str | None] = []
    for item in results:
        if isinstance(item, Exception):
            logger.warning("TTS lỗi: %s", item)
            out.append(None)
        else:
            out.append(item)
    return out


async def tts_health() -> str:
    """Trạng thái Kokoro cho /health: off | up | down."""
    if not settings.tts_enabled:
        return "off"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.tts_base_url.rstrip('/')}/models")
        return "up" if resp.status_code < 400 else "down"
    except httpx.HTTPError:
        return "down"
