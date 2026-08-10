"""Sinh phiên âm IPA cho lexical item — thuần offline, KHÔNG gọi LLM.

Vì sao không để agent sinh IPA: LLM bịa phiên âm rất tự tin (đúng định dạng, sai nội
dung) và không có cách nào kiểm chứng tự động. Phiên âm là dữ liệu tra cứu, phải lấy từ
từ điển phát âm.

Hai tầng, tra theo thứ tự:

1. **CMUdict** (`eng_to_ipa`) — từ điển phát âm CMU, chuẩn General American, do người
   biên soạn. Chính xác nhất nhưng chỉ phủ từ đơn có sẵn trong từ điển.
2. **espeak-ng** — bộ luật grapheme→phoneme, nhận MỌI chuỗi kể cả cụm nhiều từ và từ
   không có trong từ điển. Máy móc hơn nhưng không bao giờ miss.

Đơn vị học của app là collocation nên tầng 2 gánh phần lớn: "a detrimental effect on"
không bao giờ nằm trong CMUdict. Với cụm từ, ta tra CMUdict từng từ một rồi ghép — giữ
được độ chính xác của từ điển ở những từ nó biết, chỉ rơi xuống espeak ở từ nó không biết.

Cả hai thư viện đều không có mặt cũng không sao: `to_ipa()` trả về None, cột `ipa` vẫn
NULL đúng như trước, pipeline không gãy.
"""

from __future__ import annotations

import logging
import re
import subprocess
from functools import lru_cache

logger = logging.getLogger(__name__)

# Ký tự nhấn trong CMUdict/espeak; giữ nguyên vì người học cần biết trọng âm.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")

# eng_to_ipa đánh dấu từ không tra được bằng dấu * ở cuối.
_UNKNOWN_MARK = "*"


@lru_cache(maxsize=1)
def _cmudict_available() -> bool:
    try:
        import eng_to_ipa  # noqa: F401
    except Exception as exc:  # pragma: no cover - phụ thuộc môi trường
        logger.info("eng_to_ipa không dùng được (%s) — chỉ dùng espeak-ng", exc)
        return False
    return True


@lru_cache(maxsize=1)
def _espeak_available() -> bool:
    try:
        subprocess.run(
            ["espeak-ng", "--version"],
            capture_output=True,
            timeout=5,
            check=True,
        )
    except Exception as exc:  # pragma: no cover - phụ thuộc môi trường
        logger.info("espeak-ng không dùng được (%s)", exc)
        return False
    return True


@lru_cache(maxsize=4096)
def _cmudict_word(word: str) -> str | None:
    """Phiên âm MỘT từ bằng CMUdict. None nếu từ điển không có từ đó."""
    if not _cmudict_available():
        return None
    import eng_to_ipa

    try:
        result = eng_to_ipa.convert(word)
    except Exception as exc:  # pragma: no cover - lỗi nội bộ thư viện
        logger.debug("eng_to_ipa lỗi với '%s': %s", word, exc)
        return None

    result = (result or "").strip()
    # Không tra được → trả lại chính chữ cái kèm dấu *, không phải IPA.
    if not result or result.endswith(_UNKNOWN_MARK):
        return None
    return result


@lru_cache(maxsize=4096)
def _espeak_text(text: str) -> str | None:
    """Phiên âm cả chuỗi bằng espeak-ng (-q: không phát tiếng, --ipa: ra IPA)."""
    if not _espeak_available():
        return None
    try:
        proc = subprocess.run(
            ["espeak-ng", "-q", "--ipa", "-v", "en-us", text],
            capture_output=True,
            timeout=10,
            check=True,
        )
    except Exception as exc:  # pragma: no cover - phụ thuộc môi trường
        logger.debug("espeak-ng lỗi với '%s': %s", text, exc)
        return None

    out = proc.stdout.decode("utf-8", errors="replace").strip()
    # espeak xuống dòng với chuỗi dài; gộp lại thành một dòng.
    out = " ".join(out.split())
    return out or None


def to_ipa(surface_form: str) -> str | None:
    """Trả phiên âm IPA của `surface_form`, hoặc None nếu không sinh được.

    Cụm nhiều từ: tra CMUdict từng từ, từ nào từ điển không có thì rơi xuống espeak-ng
    cho riêng từ đó. Nhờ vậy một từ lạ không kéo cả cụm xuống chất lượng espeak.
    """
    text = (surface_form or "").strip()
    if not text:
        return None

    words = _WORD_RE.findall(text)
    if not words:
        return None

    parts: list[str] = []
    for word in words:
        ipa = _cmudict_word(word.lower()) or _espeak_text(word)
        if ipa is None:
            # Không tầng nào phiên âm được từ này → bỏ cả cụm, thà NULL còn hơn
            # trả về phiên âm thiếu từ khiến người học đọc sai.
            logger.debug("Không phiên âm được '%s' trong '%s'", word, text)
            return None
        parts.append(ipa)

    return " ".join(parts)


def phonetics_backend() -> str:
    """Mô tả tầng nào đang dùng được — trả ra ở /health để soi nhanh khi deploy."""
    tiers = []
    if _cmudict_available():
        tiers.append("cmudict")
    if _espeak_available():
        tiers.append("espeak-ng")
    return "+".join(tiers) if tiers else "none"
