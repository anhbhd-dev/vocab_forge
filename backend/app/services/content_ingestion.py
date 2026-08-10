"""Content Ingestion — thành phần 1 trong file 00 mục 5.

Nhận input (text dán vào, URL, PDF) → trả về text thuần cho Extraction Agent.
"""

from __future__ import annotations

import base64
import binascii
import io
import re

import httpx

_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_BLANKS = re.compile(r"\n{3,}")


class IngestionError(RuntimeError):
    """Không lấy được text từ nguồn đầu vào."""


def html_to_text(html: str) -> str:
    text = _SCRIPT_STYLE.sub(" ", html)
    text = re.sub(r"<br\s*/?>|</p>|</div>|</h[1-6]>", "\n", text, flags=re.I)
    text = _TAG.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    text = _WS.sub(" ", text)
    return _BLANKS.sub("\n\n", text).strip()


def pdf_to_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise IngestionError(
            "Cần thư viện `pypdf` để đọc PDF: pip install pypdf"
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pragma: no cover - lỗi file hỏng
        raise IngestionError(f"Không đọc được PDF: {exc}") from exc

    text = "\n\n".join(p.strip() for p in pages if p.strip())
    if not text:
        raise IngestionError(
            "PDF không có text trích xuất được (có thể là bản scan — cần OCR, "
            "chưa hỗ trợ ở giai đoạn này)."
        )
    return text


async def fetch_url(url: str, timeout: float = 30.0) -> tuple[bytes, str]:
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers={"User-Agent": "VocabForge/0.1"}
        ) as client:
            resp = await client.get(url)
    except httpx.HTTPError as exc:
        raise IngestionError(f"Không tải được URL: {exc}") from exc
    if resp.status_code >= 400:
        raise IngestionError(f"URL trả HTTP {resp.status_code}")
    return resp.content, resp.headers.get("content-type", "")


async def resolve_text(
    source_type: str, raw_text: str | None, url: str | None
) -> str:
    """Trả về text sạch từ một trong 3 nguồn `source_type`."""
    if source_type == "pasted_text":
        if not raw_text or not raw_text.strip():
            raise IngestionError("`raw_text` trống.")
        return raw_text.strip()

    if source_type == "url":
        if not url:
            raise IngestionError("`url` là bắt buộc với source_type='url'.")
        content, content_type = await fetch_url(url)
        if "pdf" in content_type.lower() or url.lower().endswith(".pdf"):
            return pdf_to_text(content)
        return html_to_text(content.decode("utf-8", errors="replace"))

    if source_type == "pdf":
        # API spec (file 01 mục 2) không có multipart upload, nên PDF đi qua `url`
        # hoặc `raw_text` dạng base64.
        if url:
            content, _ = await fetch_url(url)
            return pdf_to_text(content)
        if raw_text:
            try:
                return pdf_to_text(base64.b64decode(raw_text, validate=True))
            except (binascii.Error, ValueError) as exc:
                raise IngestionError(
                    "source_type='pdf' cần `url` trỏ tới file PDF hoặc `raw_text` là "
                    "nội dung PDF mã hoá base64."
                ) from exc
        raise IngestionError("source_type='pdf' cần `url` hoặc `raw_text` (base64).")

    raise IngestionError(f"source_type không hỗ trợ: {source_type}")
