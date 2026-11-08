"""Per-page parsing: multipage spans, tables, image placeholders, clipping."""

from document_intelligence.documents.parser import parse_pdf
from tests.conftest import FIXTURES


def test_multipage_document_parses_one_model_facing_page_per_pdf_page() -> None:
    parsed = parse_pdf((FIXTURES / "analysis-multipage.pdf").read_bytes())
    assert parsed.page_count == 2
    assert len(parsed.pages) == 2
    first, second = parsed.pages
    assert first.page == 1
    assert second.page == 2
    assert first.text.startswith("QUARTERLY RESEARCH REPORT")
    assert "FINDINGS" not in first.text
    assert second.text.startswith("FINDINGS")
    assert parsed.page(1) is first
    assert parsed.page(2) is second
    assert parsed.page(3) is None
    assert all(span.page == 1 for span in first.spans)
    assert all(span.page == 2 for span in second.spans)


def test_tables_are_detected_counted_and_appended_to_page_text() -> None:
    parsed = parse_pdf((FIXTURES / "tables-images.pdf").read_bytes())
    page = parsed.pages[0]
    assert page.table_count == 1
    assert len(page.tables) == 1
    table = page.tables[0]
    assert table.index == 1
    assert table.bbox is not None
    assert "|ITEM|PRICE|" in table.markdown
    assert "|Widget|$40|" in table.markdown
    assert "[table 1 on page 1]" in page.text
    assert "|Widget|$40|" in page.text


def test_images_are_counted_with_clear_placeholders() -> None:
    parsed = parse_pdf((FIXTURES / "tables-images.pdf").read_bytes())
    page = parsed.pages[0]
    assert page.image_count == 1
    assert len(page.images) == 1
    assert page.images[0].bbox is not None
    assert "[image 1 on page 1" in page.text
    assert "not OCRed" in page.text


def test_model_text_clipping_keeps_spans_intact() -> None:
    content = (FIXTURES / "analysis-multipage.pdf").read_bytes()
    clipped = parse_pdf(content, page_text_max_chars=80)
    full = parse_pdf(content)
    assert "AUTHORS: Example Research Group" in full.pages[0].text
    assert "AUTHORS: Example Research Group" not in clipped.pages[0].text
    assert "clipped" in clipped.pages[0].text
    assert clipped.pages[0].text.startswith("QUARTERLY RESEARCH REPORT")
    # Spans stay complete so evidence resolution works beyond the clipped window.
    assert len(clipped.pages[0].spans) == len(full.pages[0].spans)
    assert clipped.pages[0].text_chars == full.pages[0].text_chars


def test_text_pages_report_zero_images_and_tables() -> None:
    parsed = parse_pdf((FIXTURES / "cv.pdf").read_bytes())
    page = parsed.pages[0]
    assert page.image_count == 0
    assert page.table_count == 0
    assert page.has_content
    assert page.text_chars == sum(len(span.text) for span in page.spans)
