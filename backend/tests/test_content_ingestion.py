"""Test Content Ingestion — file 00 mục 5, thành phần 1."""

from __future__ import annotations

import base64

import pytest

from app.services.content_ingestion import IngestionError, html_to_text, resolve_text


class TestHtmlToText:
    def test_strips_tags_scripts_and_styles(self):
        html = (
            "<html><head><style>p{color:red}</style><script>alert(1)</script></head>"
            "<body><h1>Tiêu đề</h1><p>Đoạn một.</p><p>Đoạn hai.</p></body></html>"
        )
        text = html_to_text(html)
        assert "alert(1)" not in text
        assert "color:red" not in text
        assert "Tiêu đề" in text
        assert "Đoạn một." in text and "Đoạn hai." in text

    def test_decodes_entities(self):
        assert "&" in html_to_text("<p>A &amp; B</p>")
        assert "&nbsp;" not in html_to_text("<p>A&nbsp;B</p>")


class TestResolveText:
    async def test_pasted_text_passthrough(self):
        assert await resolve_text("pasted_text", "  bài đọc  ", None) == "bài đọc"

    async def test_empty_pasted_text_raises(self):
        with pytest.raises(IngestionError):
            await resolve_text("pasted_text", "   ", None)

    async def test_url_without_url_raises(self):
        with pytest.raises(IngestionError):
            await resolve_text("url", None, None)

    async def test_unsupported_source_type_raises(self):
        with pytest.raises(IngestionError):
            await resolve_text("audio", "x", None)

    async def test_invalid_base64_pdf_raises_clear_message(self):
        with pytest.raises(IngestionError) as exc:
            await resolve_text("pdf", "không-phải-base64!!!", None)
        assert "base64" in str(exc.value)

    async def test_pdf_roundtrip(self):
        pypdf = pytest.importorskip("pypdf")
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        import io

        buffer = io.BytesIO()
        writer.write(buffer)
        encoded = base64.b64encode(buffer.getvalue()).decode()

        # Trang trắng không có text — phải báo lỗi rõ ràng thay vì trả chuỗi rỗng.
        with pytest.raises(IngestionError) as exc:
            await resolve_text("pdf", encoded, None)
        assert "OCR" in str(exc.value)
