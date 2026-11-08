"""Deterministic per-page evidence resolution and analysis validation."""

import unicodedata
from collections.abc import Iterator

from document_intelligence.documents.parser import ParsedPage, image_placeholder
from document_intelligence.domain.analysis import (
    BBox,
    CitedText,
    Evidence,
    PageAnalysis,
    PageAnalysisOutput,
    PageTopic,
    ValidationIssue,
)

FAILED_PAGE_SUMMARY = "Analysis failed for this page."

# Quotes are matched after a compatibility fold so model-typed text (straight
# quotes, de-ligatured words) still matches PDF-extracted glyphs (fi/fl
# ligatures, curly quotes, non-breaking spaces). Displayed quotes stay verbatim;
# only matching is affected.
_FOLD_TRANSLATION = str.maketrans(
    {
        "\u00a0": " ",
        "\u2007": " ",
        "\u202f": " ",
        "\u200b": "",
        "\ufeff": "",
        "\u00ad": "",
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(_FOLD_TRANSLATION)


def _surface_entries(page: ParsedPage) -> list[tuple[str, BBox | None]]:
    """All quotable page passages: spans, table lines, and image placeholders.

    Synthetic entries carry their table/image box so quotes against them
    highlight the region the model actually read.
    """
    entries: list[tuple[str, BBox | None]] = [(span.text, span.bbox) for span in page.spans]
    for table in page.tables:
        for line in table.markdown.splitlines():
            if line.strip():
                entries.append((line, table.bbox))
    for image in page.images:
        entries.append((image_placeholder(page.page, image.index), image.bbox))
    return entries


def _resolve(quote: str, page: ParsedPage) -> tuple[Evidence, bool]:
    """Resolve one quote to page coordinates; report whether it is ambiguous.

    Ambiguity means the folded quote matches more than one distinct passage
    with no single whole-passage match to disambiguate it; the evidence then
    points at the first occurrence and validation surfaces a warning.
    """
    normalized_quote = " ".join(_fold(quote).split())
    if not normalized_quote:
        return Evidence(quote=quote), False
    entries = _surface_entries(page)
    parts: list[str] = []
    owner: list[int] = []
    for entry_index, (text, _bbox) in enumerate(entries):
        words = _fold(text).split()
        if parts and words:
            parts.append(" ")
            owner.append(entry_index)
        for word_index, word in enumerate(words):
            parts.append(word)
            owner.extend([entry_index] * len(word))
            if word_index < len(words) - 1:
                parts.append(" ")
                owner.append(entry_index)
    page_text = "".join(parts)
    matches: list[tuple[frozenset[int], int]] = []
    seen: set[frozenset[int]] = set()
    start = page_text.find(normalized_quote)
    while start >= 0:
        end = start + len(normalized_quote)
        entry_set = frozenset(index for index in owner[start:end] if index < len(entries))
        if entry_set and entry_set not in seen:
            seen.add(entry_set)
            matches.append((entry_set, start))
        start = page_text.find(normalized_quote, start + 1)
    if not matches:
        return Evidence(quote=quote), False

    def touches_entry_boundaries(entry_set: frozenset[int], start: int) -> bool:
        end = start + len(normalized_quote)
        last_owner = owner[start] if start < len(owner) else -1
        ends_at_boundary = end >= len(page_text) or owner[end] not in entry_set
        return last_owner in entry_set and ends_at_boundary

    whole = [match for match in matches if touches_entry_boundaries(*match)]
    if len(whole) == 1:
        chosen = whole[0]
        ambiguous = False
    elif len(whole) > 1:
        chosen = whole[0]
        ambiguous = True
    else:
        chosen = matches[0]
        ambiguous = len(matches) > 1
    entry_set, _start = chosen
    boxes = [entries[index][1] for index in entry_set]
    if any(box is None for box in boxes):
        return Evidence(quote=quote), False
    bbox = (
        min(box[0] for box in boxes if box is not None),
        min(box[1] for box in boxes if box is not None),
        max(box[2] for box in boxes if box is not None),
        max(box[3] for box in boxes if box is not None),
    )
    return Evidence(quote=quote, page=page.page, bbox=bbox, resolved=True), ambiguous


def resolve_quote(quote: str, page: ParsedPage) -> Evidence:
    """Resolve one verbatim quote to page coordinates (see :func:`_resolve`)."""
    return _resolve(quote, page)[0]


def resolve_output(output: PageAnalysisOutput, page: ParsedPage) -> PageAnalysisOutput:
    """Rebuild all evidence, discarding coordinates supplied by the model."""

    def cited(item: CitedText) -> CitedText:
        return CitedText(
            text=item.text, evidence=[resolve_quote(entry.quote, page) for entry in item.evidence]
        )

    def topic(item: PageTopic) -> PageTopic:
        return PageTopic(
            label=item.label,
            rationale=item.rationale,
            evidence=[resolve_quote(entry.quote, page) for entry in item.evidence],
        )

    return PageAnalysisOutput(
        summary=output.summary.model_copy(
            update={"key_points": [cited(item) for item in output.summary.key_points]}
        ),
        entities=[
            entity.model_copy(update={"evidence": resolve_quote(entity.evidence.quote, page)})
            for entity in output.entities
        ],
        topics=[topic(item) for item in output.topics],
    )


def failed_page_analysis(page: ParsedPage, error: str) -> PageAnalysis:
    """Persist a per-page failure without losing parser counts."""
    return PageAnalysis(
        page=page.page,
        status="failed",
        error=error[:2000],
        summary={"summary": FAILED_PAGE_SUMMARY, "key_points": []},
        text_chars=page.text_chars,
        image_count=page.image_count,
        table_count=page.table_count,
    )


def _evidence_items(output: PageAnalysisOutput) -> Iterator[tuple[str, list[Evidence]]]:
    for index, point in enumerate(output.summary.key_points):
        yield f"summary.key_points.{index}.evidence", point.evidence
    for index, entity in enumerate(output.entities):
        yield f"entities.{index}.evidence", [entity.evidence]
    for index, topic in enumerate(output.topics):
        yield f"topics.{index}.evidence", topic.evidence


def _normalized(value: str) -> str:
    return " ".join(value.split())


def validate_output(output: PageAnalysisOutput, page: ParsedPage) -> list[ValidationIssue]:
    """Return explicit errors for missing, ambiguous, or unsupported evidence."""
    issues: list[ValidationIssue] = []
    for path, evidence_items in _evidence_items(output):
        if not evidence_items:
            issues.append(
                ValidationIssue(
                    code="missing_evidence",
                    path=path,
                    message="At least one exact source quote is required",
                )
            )
            continue
        for index, evidence in enumerate(evidence_items):
            if not evidence.resolved or evidence.page is None or evidence.bbox is None:
                issues.append(
                    ValidationIssue(
                        code="unresolved_evidence",
                        path=f"{path}.{index}",
                        message="Quote must resolve to one passage on this page",
                    )
                )
                continue
            if _resolve(evidence.quote, page)[1]:
                issues.append(
                    ValidationIssue(
                        code="ambiguous_evidence",
                        path=f"{path}.{index}",
                        message=(
                            "Quote matches multiple passages on this page; "
                            "coordinates point to the first matching passage"
                        ),
                        severity="warning",
                    )
                )
    for index, entity in enumerate(output.entities):
        if _normalized(entity.text) not in _normalized(entity.evidence.quote):
            issues.append(
                ValidationIssue(
                    code="unsupported_entity_text",
                    path=f"entities.{index}.text",
                    message="Entity text must occur literally in its evidence quote",
                )
            )
    if page.has_content:
        if not output.summary.key_points:
            issues.append(
                ValidationIssue(
                    code="missing_key_points",
                    path="summary.key_points",
                    message="Pages with content require at least one cited key point",
                )
            )
        if not output.topics:
            issues.append(
                ValidationIssue(
                    code="missing_topics",
                    path="topics",
                    message="Pages with content require at least one cited topic",
                )
            )
    return issues


def build_page_analysis(
    output: PageAnalysisOutput, page: ParsedPage, error: str | None = None
) -> PageAnalysis:
    """Resolve, validate, and assemble the persisted per-page analysis."""
    resolved = resolve_output(output, page)
    return PageAnalysis(
        page=page.page,
        status="completed",
        error=error,
        issues=validate_output(resolved, page),
        summary=resolved.summary,
        entities=resolved.entities,
        topics=resolved.topics,
        text_chars=page.text_chars,
        image_count=page.image_count,
        table_count=page.table_count,
    )
