"""PyMuPDF parser producing the only source of page text, spans, and boxes.

Born-digital text spans carry PDF coordinates. Tables are detected with
``page.find_tables()`` when the installed PyMuPDF exposes it, and their
extracted text is appended to the model-facing page text. Images are counted
from image blocks and represented by explicit placeholders. No raster OCR is
performed or claimed: image pixels are never converted to text.
"""

from typing import Any

import pymupdf
from pydantic import Field

from document_intelligence.domain.analysis import BBox
from document_intelligence.domain.base import StrictModel

CLIP_NOTICE = "\n[... additional page text clipped ...]"


def image_placeholder(page_number: int, image_index: int) -> str:
    """Model-facing line representing one raster image region (never OCRed)."""
    return (
        f"[image {image_index} on page {page_number}: "
        "no extractable text; image content is not OCRed]"
    )


class TextSpan(StrictModel):
    page: int
    text: str
    bbox: BBox


class ParsedImage(StrictModel):
    index: int = Field(ge=1)
    bbox: BBox | None = None


class ParsedTable(StrictModel):
    index: int = Field(ge=1)
    bbox: BBox | None = None
    markdown: str


class ParsedPage(StrictModel):
    """One parser page: model-facing text plus parser-owned structure."""

    page: int = Field(ge=1)
    text: str
    spans: list[TextSpan]
    text_chars: int = Field(ge=0)
    image_count: int = Field(ge=0)
    images: list[ParsedImage] = Field(default_factory=list)
    table_count: int = Field(ge=0)
    tables: list[ParsedTable] = Field(default_factory=list)

    @property
    def has_content(self) -> bool:
        """True when the page carries text, tables, or images to analyze."""
        return self.text_chars > 0 or self.image_count > 0


class ParsedDocument(StrictModel):
    page_count: int
    pages: list[ParsedPage]

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages)

    def page(self, number: int) -> ParsedPage | None:
        if 1 <= number <= len(self.pages):
            return self.pages[number - 1]
        return None


def _to_bbox(raw: Any) -> BBox | None:
    try:
        values = tuple(float(value) for value in raw)
    except (TypeError, ValueError):
        return None
    return (values[0], values[1], values[2], values[3]) if len(values) == 4 else None


def _clip(text: str, max_chars: int | None) -> str:
    if max_chars is None or len(text) <= max_chars:
        return text
    clipped = text[:max_chars].rstrip()
    last_break = max(clipped.rfind("\n"), clipped.rfind(" "))
    if last_break > max_chars // 2:
        clipped = clipped[:last_break]
    return clipped + CLIP_NOTICE


def _extract_tables(page: Any, page_number: int) -> list[ParsedTable]:
    """Detect tables with the version-gated PyMuPDF API; failures yield none."""
    finder = getattr(page, "find_tables", None)
    if finder is None:
        return []
    try:
        found = finder()
        tables = found.tables if hasattr(found, "tables") else list(found)
    except Exception:
        return []
    extracted: list[ParsedTable] = []
    for index, table in enumerate(tables):
        parsed = _parsed_table(table, index + 1)
        if parsed is not None:
            extracted.append(parsed)
    return extracted


def _parsed_table(table: Any, index: int) -> ParsedTable | None:
    """Convert one detected table; unusable tables are skipped."""
    try:
        markdown = str(table.to_markdown())
        bbox = _to_bbox(getattr(table, "bbox", None))
    except Exception:
        return None
    return ParsedTable(index=index, bbox=bbox, markdown=markdown) if markdown.strip() else None


def _extract_spans(page_dict: dict[str, Any], page_number: int) -> list[TextSpan]:
    spans: list[TextSpan] = []
    for block in page_dict.get("blocks", []):
        if not isinstance(block, dict) or block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for raw_span in line.get("spans", []):
                text = str(raw_span.get("text", "")).strip()
                if not text:
                    continue
                bbox = _to_bbox(raw_span.get("bbox"))
                if bbox is None:
                    raise ValueError("PyMuPDF returned an invalid bounding box")
                spans.append(TextSpan(page=page_number, text=text, bbox=bbox))
    return spans


def _extract_images(page_dict: dict[str, Any], page_number: int) -> list[ParsedImage]:
    images: list[ParsedImage] = []
    for block in page_dict.get("blocks", []):
        if not isinstance(block, dict) or block.get("type") != 1:
            continue
        images.append(ParsedImage(index=len(images) + 1, bbox=_to_bbox(block.get("bbox"))))
    return images


def parse_pdf(content: bytes, page_text_max_chars: int | None = None) -> ParsedDocument:
    """Extract per-page text spans, tables, and image placeholders.

    ``page_text_max_chars`` clips only the model-facing page text; parser spans
    stay complete so evidence resolution keeps working for the full page.
    """
    try:
        with pymupdf.open(stream=content, filetype="pdf") as document:  # type: ignore[no-untyped-call]
            if document.page_count == 0:
                raise ValueError("PDF has no pages")
            pages: list[ParsedPage] = []
            for page_index, page in enumerate(document):
                page_number = page_index + 1
                page_dict: dict[str, Any] = page.get_text("dict")
                spans = _extract_spans(page_dict, page_number)
                images = _extract_images(page_dict, page_number)
                tables = _extract_tables(page, page_number)

                lines = [span.text for span in spans]
                body_chars = sum(len(line) for line in lines)
                for table_index, table in enumerate(tables):
                    lines.append(f"[table {table_index + 1} on page {page_number}]")
                    lines.append(table.markdown.rstrip("\n"))
                    body_chars += len(table.markdown)
                for image in images:
                    lines.append(image_placeholder(page_number, image.index))
                model_text = _clip("\n".join(lines), page_text_max_chars)
                pages.append(
                    ParsedPage(
                        page=page_number,
                        text=model_text,
                        spans=spans,
                        text_chars=body_chars,
                        image_count=len(images),
                        images=images,
                        table_count=len(tables),
                        tables=tables,
                    )
                )
            return ParsedDocument(page_count=document.page_count, pages=pages)
    except (RuntimeError, ValueError) as exc:
        raise ValueError("Invalid or unreadable PDF") from exc
