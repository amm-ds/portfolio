"""Canonical JSON and Markdown downloads for documents and single pages."""

import json
from typing import Literal

from document_intelligence.domain.analysis import (
    AnalysisRecord,
    DocumentRecord,
    Evidence,
    PageAnalysis,
)

ExportFormat = Literal["json", "md"]

NO_OCR_NOTE = (
    "Note: this report covers born-digital text and extracted tables only. "
    "Raster images are counted and quoted as placeholders; their pixel content "
    "is not OCRed."
)


def export_json(payload: dict[str, object]) -> str:
    """Canonical sorted pretty JSON with a trailing newline."""
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def document_payload(record: DocumentRecord, analysis: AnalysisRecord | None) -> dict[str, object]:
    return {
        "document": record.model_dump(mode="json"),
        "analysis": (
            analysis.analysis.model_dump(mode="json") if analysis and analysis.analysis else None
        ),
        "progress": (
            analysis.progress.model_dump(mode="json")
            if analysis
            else {"page_count": 0, "processed_pages": 0, "failed_pages": 0}
        ),
        "analyzer": analysis.analyzer if analysis else None,
        "created_at": (
            analysis.created_at.isoformat() if analysis else record.created_at.isoformat()
        ),
        "updated_at": (
            analysis.updated_at.isoformat() if analysis else record.updated_at.isoformat()
        ),
    }


def page_payload(
    record: DocumentRecord, analysis: AnalysisRecord | None, page_number: int
) -> dict[str, object] | None:
    page = find_page(analysis, page_number)
    if page is None:
        return None
    return {
        "document": record.model_dump(mode="json"),
        "page": page.model_dump(mode="json"),
    }


def find_page(analysis: AnalysisRecord | None, page_number: int) -> PageAnalysis | None:
    if analysis is None or analysis.analysis is None:
        return None
    return next((page for page in analysis.analysis.pages if page.page == page_number), None)


def _evidence_marker(evidence: Evidence) -> str:
    if not evidence.resolved:
        return "UNRESOLVED"
    return f"page {evidence.page}, resolved" if evidence.page else "resolved"


def _cited_quote_lines(evidence: Evidence) -> str:
    return f'    > "{evidence.quote}" ({_evidence_marker(evidence)})'


def _render_page_section(page: PageAnalysis, heading: str) -> list[str]:
    status = f"- status: {page.status}" + (f" (error: {page.error})" if page.error else "")
    lines = [
        heading,
        "",
        status,
        f"- text chars: {page.text_chars}; images: {page.image_count}; tables: {page.table_count}",
        "",
        f"Summary: {page.summary.summary}",
        "",
        "Key points:",
    ]
    if page.summary.key_points:
        for point in page.summary.key_points:
            lines.append(f"- {point.text}")
            lines.extend(_cited_quote_lines(evidence) for evidence in point.evidence)
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("Entities:")
    if page.entities:
        for entity in page.entities:
            lines.append(
                f"- {entity.text} (name: {entity.name}, type: {entity.type}) — "
                f'"{entity.evidence.quote}" ({_evidence_marker(entity.evidence)})'
            )
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("Topics:")
    if page.topics:
        for topic in page.topics:
            lines.append(f"- {topic.label}: {topic.rationale}")
            lines.extend(_cited_quote_lines(evidence) for evidence in topic.evidence)
    else:
        lines.append("- (none)")
    if page.issues:
        lines.append("")
        lines.append("Issues:")
        for issue in page.issues:
            lines.append(f"- [{issue.severity}] {issue.code} at {issue.path}: {issue.message}")
    lines.append("")
    return lines


def export_document_markdown(record: DocumentRecord, analysis: AnalysisRecord | None) -> str:
    progress = analysis.progress if analysis else None
    lines = [
        f"# Document analysis: {record.filename}",
        "",
        f"- document id: {record.id}",
        f"- tenant: {record.tenant_id}",
        f"- sha256: {record.sha256}",
        f"- status: {record.status}",
        f"- pages: {record.page_count if record.page_count is not None else '-'}",
        f"- uploaded: {record.created_at.isoformat()}",
        f"- updated: {record.updated_at.isoformat()}",
        f"- analyzer: {analysis.analyzer if analysis else '-'}",
        (
            "- progress: "
            f"{progress.processed_pages}/{progress.page_count} processed, "
            f"{progress.failed_pages} failed"
            if progress
            else "- progress: not started"
        ),
        "",
    ]
    pages = analysis.analysis.pages if analysis and analysis.analysis else []
    if not pages:
        lines.extend(["No page analysis is available yet.", ""])
    for page in pages:
        note = "" if page.status == "completed" else f" — {page.status}"
        lines.extend(_render_page_section(page, f"## Page {page.page}{note}"))
    lines.append(NO_OCR_NOTE)
    lines.append("")
    return "\n".join(lines)


def export_page_markdown(
    record: DocumentRecord, analysis: AnalysisRecord | None, page_number: int
) -> str | None:
    page = find_page(analysis, page_number)
    if page is None:
        return None
    lines = [
        f"# Page {page_number} analysis: {record.filename}",
        "",
        f"- document id: {record.id}",
        f"- sha256: {record.sha256}",
        f"- document status: {record.status}",
        "",
    ]
    lines.extend(_render_page_section(page, f"## Page {page.page}"))
    lines.append(NO_OCR_NOTE)
    lines.append("")
    return "\n".join(lines)
