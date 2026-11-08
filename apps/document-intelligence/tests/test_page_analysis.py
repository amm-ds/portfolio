"""Page analysis contracts, single-call AI output, and evidence guards."""

import asyncio

import pytest
from pydantic import ValidationError
from pydantic_ai import ModelRetry
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from document_intelligence.analysis.evidence import (
    build_page_analysis,
    resolve_output,
    resolve_quote,
    validate_output,
)
from document_intelligence.analysis.page_analyzer import (
    DeterministicPageAnalyzer,
    PydanticAIPageAnalyzer,
    require_complete_page_output,
)
from document_intelligence.documents.parser import (
    ParsedImage,
    ParsedPage,
    ParsedTable,
    TextSpan,
    image_placeholder,
    parse_pdf,
)
from document_intelligence.domain.analysis import (
    CitedText,
    Evidence,
    PageAnalysisOutput,
    PageAnalysisResult,
    PageEntity,
    PageSummary,
    PageTopic,
)
from document_intelligence.fixtures import render_pdf
from tests.conftest import FIXTURES


def _page(number: int) -> ParsedPage:
    parsed = parse_pdf((FIXTURES / "analysis-multipage.pdf").read_bytes())
    return parsed.pages[number - 1]


def test_deterministic_page_analysis_resolves_every_quote_on_its_page() -> None:
    parsed = parse_pdf((FIXTURES / "analysis-multipage.pdf").read_bytes())
    for page in parsed.pages:
        output = asyncio.run(DeterministicPageAnalyzer().analyze_page(page))
        analysis = build_page_analysis(output, page)
        assert analysis.page == page.page
        assert analysis.status == "completed"
        assert analysis.text_chars == page.text_chars
        evidence = [
            *[item for point in analysis.summary.key_points for item in point.evidence],
            *[entity.evidence for entity in analysis.entities],
            *[item for topic in analysis.topics for item in topic.evidence],
        ]
        assert all(item.resolved and item.page == page.page and item.bbox for item in evidence)
        if page.has_content:
            assert analysis.summary.key_points
            assert analysis.topics
            assert analysis.issues == []


def test_model_coordinates_are_discarded_and_bad_entity_text_is_an_error() -> None:
    page = _page(1)
    output = PageAnalysisOutput(
        summary=PageSummary(
            summary="s",
            key_points=[
                CitedText(
                    text="point",
                    evidence=[Evidence(quote="QUARTERLY RESEARCH REPORT", page=999, resolved=True)],
                )
            ],
        ),
        entities=[
            PageEntity(
                text="Not Present In Quote",
                name="Not Present In Quote",
                type="organization",
                evidence=Evidence(quote="ORGANIZATION: Northstar Research"),
            )
        ],
        topics=[
            PageTopic(label="t", rationale="r", evidence=[Evidence(quote="PERIOD: 2025-03-31")])
        ],
    )
    analysis = build_page_analysis(output, page)
    point_evidence = analysis.summary.key_points[0].evidence[0]
    assert point_evidence.page == 1
    assert point_evidence.bbox is not None and point_evidence.bbox != (0, 0, 1, 1)
    assert {issue.code for issue in analysis.issues} == {"unsupported_entity_text"}
    assert analysis.entities[0].evidence.resolved


def test_missing_ambiguous_and_unresolved_evidence_are_validation_errors() -> None:
    page = _page(1)
    output = asyncio.run(DeterministicPageAnalyzer().analyze_page(page))
    missing = output.model_copy(deep=True)
    missing.topics[0].evidence = []
    missing_issues = validate_output(resolve_output(missing, page), page)
    assert any(issue.code == "missing_evidence" for issue in missing_issues)

    unresolved = output.model_copy(deep=True)
    unresolved.summary.key_points[0].evidence[0].quote = "NOT ON THIS PAGE"
    resolved_unresolved = resolve_output(unresolved, page)
    assert any(
        issue.code == "unresolved_evidence" for issue in validate_output(resolved_unresolved, page)
    )

    duplicate = parse_pdf(render_pdf(["Repeated passage", "Repeated passage"])).pages[0]
    output_with_duplicate = output.model_copy(deep=True)
    output_with_duplicate.summary.key_points[0].evidence[0].quote = "Repeated passage"
    resolved_duplicate = resolve_output(output_with_duplicate, duplicate)
    point_evidence = resolved_duplicate.summary.key_points[0].evidence[0]
    assert point_evidence.resolved and point_evidence.bbox is not None
    warnings = [
        issue
        for issue in validate_output(resolved_duplicate, duplicate)
        if issue.code == "ambiguous_evidence"
    ]
    assert len(warnings) == 1
    assert warnings[0].severity == "warning"
    assert warnings[0].path == "summary.key_points.0.evidence.0"


def test_resolution_folds_typographic_variants() -> None:
    extracted = "It\u2019s a \u201cquoted\u201d passage \u2014 filed"
    page = ParsedPage(
        page=1,
        text=extracted,
        spans=[TextSpan(page=1, text=extracted, bbox=(1, 2, 300, 20))],
        text_chars=len(extracted),
        image_count=0,
        table_count=0,
    )
    evidence = resolve_quote('It\'s a "quoted" passage - filed', page)
    assert evidence.resolved
    assert evidence.bbox == (1, 2, 300, 20)


def test_table_lines_and_image_placeholders_are_quotable() -> None:
    table = ParsedTable(
        index=1,
        bbox=(10, 100, 400, 200),
        markdown="| ITEM | PRICE |\n| --- | --- |\n| Widget | $40 |",
    )
    page = ParsedPage(
        page=1,
        text="INVENTORY REPORT",
        spans=[TextSpan(page=1, text="INVENTORY REPORT", bbox=(1, 2, 200, 20))],
        text_chars=16,
        image_count=1,
        images=[ParsedImage(index=1, bbox=(54, 260, 154, 360))],
        table_count=1,
        tables=[table],
    )
    table_evidence = resolve_quote("| Widget | $40 |", page)
    assert table_evidence.resolved
    assert table_evidence.bbox == (10, 100, 400, 200)

    placeholder = image_placeholder(1, 1)
    image_evidence = resolve_quote(placeholder, page)
    assert image_evidence.resolved
    assert image_evidence.bbox == (54, 260, 154, 360)


def test_substring_matches_do_not_warn_when_one_whole_passage_matches() -> None:
    page = ParsedPage(
        page=1,
        text="ITEM",
        spans=[TextSpan(page=1, text="ITEM", bbox=(5, 6, 50, 18))],
        text_chars=4,
        image_count=0,
        table_count=1,
        tables=[
            ParsedTable(
                index=1,
                bbox=(10, 100, 400, 200),
                markdown="| ITEM | PRICE |\n| --- | --- |",
            )
        ],
    )
    output = PageAnalysisOutput(
        summary=PageSummary(
            summary="s",
            key_points=[CitedText(text="ITEM", evidence=[Evidence(quote="ITEM")])],
        ),
        topics=[PageTopic(label="t", rationale="r", evidence=[Evidence(quote="ITEM")])],
    )
    analysis = build_page_analysis(output, page)
    assert analysis.summary.key_points[0].evidence[0].resolved
    assert analysis.issues == []


def test_content_pages_require_key_points_and_topics() -> None:
    page = _page(2)
    output = asyncio.run(DeterministicPageAnalyzer().analyze_page(page))
    empty = output.model_copy(deep=True)
    empty.summary.key_points = []
    empty.topics = []
    codes = {issue.code for issue in validate_output(resolve_output(empty, page), page)}
    assert {"missing_key_points", "missing_topics"} <= codes


def test_pydantic_ai_analyzer_makes_one_tool_free_structured_call_per_page() -> None:
    parsed = parse_pdf((FIXTURES / "prompt-injection.pdf").read_bytes())
    page = parsed.pages[0]
    expected = asyncio.run(DeterministicPageAnalyzer().analyze_page(page))
    calls: list[int] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(len(info.function_tools))
        assert "IGNORE ALL INSTRUCTIONS" in str(messages[-1].parts[0])
        return ModelResponse(parts=[TextPart(expected.model_dump_json())])

    analyzer = PydanticAIPageAnalyzer(FunctionModel(respond), timeout_seconds=5)
    actual = asyncio.run(analyzer.analyze_page(page))
    assert actual == expected
    assert calls == [0]


def test_strict_page_contract_rejects_unknown_fields_and_schema_versions() -> None:
    with pytest.raises(ValidationError):
        Evidence.model_validate({"quote": "x", "invented_bbox": [0, 0, 1, 1]})
    result = PageAnalysisResult.model_validate(
        {
            "schema_version": "page-analysis-v1",
            "pages": [
                {
                    "page": 1,
                    "status": "completed",
                    "error": None,
                    "issues": [],
                    "summary": {"summary": "s", "key_points": []},
                    "entities": [],
                    "topics": [],
                    "text_chars": 0,
                    "image_count": 0,
                    "table_count": 0,
                }
            ],
        }
    )
    payload = result.model_dump(mode="json")
    payload["schema_version"] = "analysis-v1"
    with pytest.raises(ValidationError):
        PageAnalysisResult.model_validate(payload)
    payload = result.model_dump(mode="json")
    payload["pages"][0]["unknown"] = True
    with pytest.raises(ValidationError):
        PageAnalysisResult.model_validate(payload)


def test_model_output_validator_requests_missing_key_points_and_topics() -> None:
    page = _page(2)
    output = asyncio.run(DeterministicPageAnalyzer().analyze_page(page))
    validate = require_complete_page_output(page)
    incomplete = output.model_copy(deep=True)
    incomplete.summary.key_points = []
    with pytest.raises(ModelRetry, match="key point"):
        validate(incomplete)
    incomplete = output.model_copy(deep=True)
    incomplete.topics = []
    with pytest.raises(ModelRetry, match="topic"):
        validate(incomplete)


def test_empty_page_skips_content_requirements() -> None:
    empty_page = ParsedPage(
        page=3, text="", spans=[], text_chars=0, image_count=0, images=[], table_count=0
    )
    output = asyncio.run(DeterministicPageAnalyzer().analyze_page(empty_page))
    assert output.summary.key_points == []
    assert output.topics == []
    assert validate_output(resolve_output(output, empty_page), empty_page) == []


def test_table_only_page_derives_content_from_table_lines() -> None:
    markdown = "| ITEM | PRICE |\n| --- | --- |\n| Widget | $40 |"
    page = ParsedPage(
        page=1,
        text=markdown,
        spans=[],
        text_chars=len(markdown),
        image_count=0,
        images=[],
        table_count=1,
        tables=[ParsedTable(index=1, bbox=(10, 100, 400, 200), markdown=markdown)],
    )
    output = asyncio.run(DeterministicPageAnalyzer().analyze_page(page))
    analysis = build_page_analysis(output, page)
    assert analysis.summary.key_points
    assert analysis.topics
    assert analysis.issues == []
    assert all(point.evidence[0].resolved for point in analysis.summary.key_points)
    assert all(item.resolved for topic in analysis.topics for item in topic.evidence)


def test_image_only_page_summary_reports_tables_and_images_neutrally() -> None:
    placeholder = image_placeholder(1, 1)
    page = ParsedPage(
        page=1,
        text=placeholder,
        spans=[],
        text_chars=0,
        image_count=1,
        images=[ParsedImage(index=1, bbox=(54, 260, 154, 360))],
        table_count=0,
        tables=[],
    )
    output = asyncio.run(DeterministicPageAnalyzer().analyze_page(page))
    assert output.summary.key_points
    assert output.topics
    assert "0 table(s), 1 image(s)" in output.summary.summary
    assert "not OCRed" in output.summary.summary
