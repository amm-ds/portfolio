"""Page-level evaluation for summaries, entities, topics, and cited page chat."""

import argparse
import asyncio
import hashlib
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from document_intelligence.analysis.evidence import (
    build_page_analysis,
    failed_page_analysis,
    resolve_quote,
)
from document_intelligence.analysis.page_analyzer import (
    INSTRUCTIONS,
    DeterministicPageAnalyzer,
    PageAnalyzer,
    build_page_analyzer,
)
from document_intelligence.analysis.page_chat import (
    CHAT_INSTRUCTIONS,
    DeterministicPageChat,
    PageChat,
    build_page_chat,
)
from document_intelligence.documents.parser import parse_pdf
from document_intelligence.domain.analysis import (
    PageAnalysis,
    PageAnalysisResult,
    PageChatMessage,
    PageChatResponse,
)
from document_intelligence.evals.contracts import (
    DEFAULT_FIXTURE_ROOT,
    DEFAULT_REFERENCE_PATH,
    ReferenceCase,
    ReferencePage,
    ReferenceQuestion,
    load_references,
)
from document_intelligence.evals.metrics import (
    SIMILARITY_THRESHOLD,
    best_match_scores,
    mean,
    normalize,
    percentile,
    prf,
    token_f1,
)


def _quote_match(predicted: str, references: list[str]) -> bool:
    normalized = normalize(predicted)
    return any(
        normalized == normalize(reference)
        or normalize(reference) in normalized
        or normalized in normalize(reference)
        for reference in references
    )


def _validate_reference_sources(case: ReferenceCase, parsed_pages: dict[int, Any]) -> None:
    for reference in case.pages:
        page = parsed_pages.get(reference.page)
        if page is None:
            raise ValueError(f"Reference page {reference.page} missing for {case.case_id}")
        quotes = [quote for point in reference.key_points for quote in point.evidence]
        quotes.extend(entity.evidence for entity in reference.entities)
        quotes.extend(quote for question in reference.questions for quote in question.citations)
        unresolved = [quote for quote in quotes if not resolve_quote(quote, page).resolved]
        if unresolved:
            raise ValueError(
                f"Reference evidence does not resolve for {case.case_id}: {unresolved}"
            )


def _citations(pages: list[PageAnalysis]) -> list[Any]:
    evidence: list[Any] = []
    for page in pages:
        evidence.extend(item for point in page.summary.key_points for item in point.evidence)
        evidence.extend(entity.evidence for entity in page.entities)
        evidence.extend(item for topic in page.topics for item in topic.evidence)
    return evidence


def _summary_scores(reference: ReferencePage, raw_pages: dict[int, PageAnalysis]) -> dict[str, Any]:
    page_analysis = raw_pages.get(reference.page)
    predicted_texts = (
        [point.text for point in page_analysis.summary.key_points] if page_analysis else []
    )
    reference_texts = [point.text for point in reference.key_points]
    scores = best_match_scores(reference_texts, predicted_texts)
    supported = 0
    for index, point in enumerate(reference.key_points):
        if not predicted_texts or scores[index] < SIMILARITY_THRESHOLD or not page_analysis:
            continue
        best_index = max(
            range(len(predicted_texts)),
            key=lambda predicted_index: token_f1(
                point.text, page_analysis.summary.key_points[predicted_index].text
            ),
        )
        citations = page_analysis.summary.key_points[best_index].evidence
        if any(
            citation.resolved and _quote_match(citation.quote, point.evidence)
            for citation in citations
        ):
            supported += 1
    count = len(reference.key_points)
    return {
        "summary_covered": sum(score >= SIMILARITY_THRESHOLD for score in scores),
        "summary_reference_count": count,
        "summary_token_f1": mean(scores),
        "summary_reference_citations": supported,
    }


def _entity_scores(reference: ReferencePage, page_analysis: PageAnalysis | None) -> dict[str, Any]:
    predicted = page_analysis.entities if page_analysis else []
    reference_keys = [
        (normalize(entity.text), normalize(entity.name), normalize(entity.type))
        for entity in reference.entities
    ]
    predicted_keys = [
        (normalize(entity.text), normalize(entity.name), normalize(entity.type))
        for entity in predicted
    ]
    scores = prf(reference_keys, predicted_keys)
    reference_names = {
        (normalize(entity.text), normalize(entity.name)): normalize(entity.type)
        for entity in reference.entities
    }
    name_matches = [
        entity_type for text, name, entity_type in predicted_keys if (text, name) in reference_names
    ]
    type_correct = sum(
        reference_names[(text, name)] == entity_type
        for text, name, entity_type in predicted_keys
        if (text, name) in reference_names
    )
    return {
        "entity_true_positive": scores["true_positive"],
        "entity_predicted": scores["predicted"],
        "entity_reference": scores["reference"],
        "entity_precision": scores["precision"],
        "entity_recall": scores["recall"],
        "entity_f1": scores["f1"],
        "entity_type_correct": type_correct,
        "entity_name_matches": len(name_matches),
        "entity_type_accuracy": type_correct / len(name_matches) if name_matches else 0.0,
    }


def _topic_scores(reference: ReferencePage, page_analysis: PageAnalysis | None) -> dict[str, Any]:
    predicted = page_analysis.topics if page_analysis else []
    aliases = {
        normalize(alias): normalize(topic.label)
        for topic in reference.topics
        for alias in [topic.label, *topic.aliases]
    }
    reference_labels = [normalize(topic.label) for topic in reference.topics]
    actual = [aliases.get(normalize(topic.label), normalize(topic.label)) for topic in predicted]
    scores = prf(reference_labels, actual)
    return {
        "topic_true_positive": scores["true_positive"],
        "topic_predicted": scores["predicted"],
        "topic_reference": scores["reference"],
        "topic_precision": scores["precision"],
        "topic_recall": scores["recall"],
        "topic_f1": scores["f1"],
    }


def _answer_scores(
    question: ReferenceQuestion, answer: PageChatResponse | None
) -> tuple[dict[str, Any], int, int]:
    citations = answer.citations if answer else []
    supported = any(
        citation.resolved and _quote_match(citation.quote, question.citations)
        for citation in citations
    )
    similarity = token_f1(question.answer, answer.answer) if answer else 0.0
    return (
        {
            "answer_correct": int(similarity >= SIMILARITY_THRESHOLD),
            "answer_token_f1": similarity,
            "answer_reference_citation": int(supported),
        },
        len(citations),
        sum(citation.resolved for citation in citations),
    )


def _page_misses(
    reference: ReferencePage,
    raw_pages: dict[int, PageAnalysis],
    answers: list[dict[str, Any]],
    parser_pages: dict[int, Any],
) -> list[str]:
    page_analysis = raw_pages.get(reference.page)
    misses: list[str] = []
    if page_analysis is None:
        return [f"page {reference.page}: not analyzed"]
    if page_analysis.status == "failed":
        misses.append(f"page {reference.page}: analysis failed ({page_analysis.error})")
    error_issues = [issue.code for issue in page_analysis.issues if issue.severity == "error"]
    if error_issues:
        misses.append(f"page {reference.page}: validation issues {sorted(set(error_issues))}")
    summary = _summary_scores(reference, raw_pages)
    if summary["summary_covered"] != summary["summary_reference_count"]:
        misses.append(f"page {reference.page}: uncovered key points")
    if summary["summary_reference_citations"] != summary["summary_reference_count"]:
        misses.append(f"page {reference.page}: unsupported key-point citations")
    entities = _entity_scores(reference, page_analysis)
    if reference.entities and entities["entity_f1"] < 1.0:
        misses.append(f"page {reference.page}: entity misses (f1={entities['entity_f1']:.2f})")
    topics = _topic_scores(reference, page_analysis)
    if reference.topics and topics["topic_f1"] < 1.0:
        misses.append(f"page {reference.page}: topic misses (f1={topics['topic_f1']:.2f})")
    for answer in answers:
        failed_answer = answer["error"] or not answer["answer_correct"]
        if failed_answer or not answer["answer_reference_citation"]:
            misses.append(f"page {reference.page}: question missed: {answer['question']}")
    parsed = parser_pages.get(reference.page)
    if parsed is not None:
        if parsed.table_count != reference.expect_tables:
            misses.append(
                f"page {reference.page}: table count {parsed.table_count} "
                f"!= expected {reference.expect_tables}"
            )
        if parsed.image_count != reference.expect_images:
            misses.append(
                f"page {reference.page}: image count {parsed.image_count} "
                f"!= expected {reference.expect_images}"
            )
    return misses


async def score_case(
    case: ReferenceCase,
    pdf: bytes,
    analyzer: PageAnalyzer,
    chat: PageChat,
) -> dict[str, Any]:
    """Score one case serially so provider failures remain attributable."""
    parsed = parse_pdf(pdf)
    parser_pages = {page.page: page for page in parsed.pages}
    _validate_reference_sources(case, parser_pages)
    errors: list[str] = []
    started = time.perf_counter()
    raw_pages: dict[int, PageAnalysis] = {}
    for page in parsed.pages:
        try:
            output = await analyzer.analyze_page(page)
            raw_pages[page.page] = build_page_analysis(output, page)
        except Exception as exc:
            errors.append(f"analysis:{type(exc).__name__}")
            raw_pages[page.page] = failed_page_analysis(page, f"{type(exc).__name__}: {exc}")
    analysis_latency = (time.perf_counter() - started) * 1000
    pages = [raw_pages[number] for number in sorted(raw_pages)]

    answers: list[dict[str, Any]] = []
    answer_count = 0
    answer_correct = 0
    answer_reference_citations = 0
    answer_citation_count = 0
    answer_citation_resolved = 0
    output_characters = len(PageAnalysisResult(pages=pages).model_dump_json())
    qa_started = time.perf_counter()
    for reference in case.pages:
        reference_page = parser_pages.get(reference.page)
        if reference_page is None:
            raise ValueError(f"Reference page {reference.page} missing for {case.case_id}")
        for question in reference.questions:
            try:
                answer: PageChatResponse | None = await chat.chat(
                    reference_page,
                    [PageChatMessage(role="user", content=question.question)],
                )
            except Exception as exc:
                errors.append(f"chat:{type(exc).__name__}")
                answer = None
            scores, citation_count, citation_resolved = _answer_scores(question, answer)
            answer_count += 1
            answer_correct += int(scores["answer_correct"])
            answer_reference_citations += int(scores["answer_reference_citation"])
            answer_citation_count += citation_count
            answer_citation_resolved += citation_resolved
            output_characters += len(answer.model_dump_json()) if answer else 0
            answers.append(
                {
                    "page": reference.page,
                    "question": question.question,
                    **scores,
                    "error": answer is None,
                    "predicted": answer.model_dump(mode="json") if answer else None,
                }
            )
    qa_latency = (time.perf_counter() - qa_started) * 1000

    all_citations = _citations(pages)
    evidence_count = len(all_citations) + answer_citation_count
    evidence_resolved = sum(citation.resolved for citation in all_citations)
    evidence_resolved += answer_citation_resolved
    reference_pages: list[dict[str, Any]] = []
    misses: list[str] = []
    for reference in case.pages:
        page_answers = [a for a in answers if a["page"] == reference.page]
        page_misses = _page_misses(reference, raw_pages, page_answers, parser_pages)
        misses.extend(page_misses)
        reference_pages.append(
            {
                "page": reference.page,
                "summary": _summary_scores(reference, raw_pages),
                "entities": _entity_scores(reference, raw_pages.get(reference.page)),
                "topics": _topic_scores(reference, raw_pages.get(reference.page)),
                "missed": bool(page_misses),
            }
        )
    row: dict[str, Any] = {
        "case_id": case.case_id,
        "errors": errors,
        "predicted_analysis": PageAnalysisResult(pages=pages).model_dump(mode="json"),
        "reference_pages": reference_pages,
        "answers": answers,
        "answer_count": answer_count,
        "answer_correct": answer_correct,
        "answer_reference_citations": answer_reference_citations,
        "evidence_count": evidence_count,
        "evidence_resolved": evidence_resolved,
        "unsupported_citations": evidence_count - evidence_resolved,
        "latency_ms": analysis_latency + qa_latency,
        "analysis_latency_ms": analysis_latency,
        "qa_latency_ms": qa_latency,
        "input_characters": sum(len(page.text) for page in parsed.pages) * (1 + answer_count),
        "output_characters": output_characters,
        "misses": misses,
    }
    return row


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _page_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-reference-page summary, entity, and topic metrics."""
    summary_covered = sum(row["summary"]["summary_covered"] for row in rows)
    summary_count = sum(row["summary"]["summary_reference_count"] for row in rows)
    summary_citations = sum(row["summary"]["summary_reference_citations"] for row in rows)
    entity_tp = sum(row["entities"]["entity_true_positive"] for row in rows)
    entity_predicted = sum(row["entities"]["entity_predicted"] for row in rows)
    entity_reference = sum(row["entities"]["entity_reference"] for row in rows)
    topic_tp = sum(row["topics"]["topic_true_positive"] for row in rows)
    topic_predicted = sum(row["topics"]["topic_predicted"] for row in rows)
    topic_reference = sum(row["topics"]["topic_reference"] for row in rows)
    entity_precision = _rate(entity_tp, entity_predicted)
    entity_recall = _rate(entity_tp, entity_reference)
    topic_precision = _rate(topic_tp, topic_predicted)
    topic_recall = _rate(topic_tp, topic_reference)
    return {
        "reference_pages": len(rows),
        "summary_key_point_coverage": _rate(summary_covered, summary_count),
        "summary_key_point_token_f1": mean(row["summary"]["summary_token_f1"] for row in rows),
        "summary_reference_citation_rate": _rate(summary_citations, summary_count),
        "entity_precision": entity_precision,
        "entity_recall": entity_recall,
        "entity_f1": 2 * entity_precision * entity_recall / (entity_precision + entity_recall)
        if entity_precision + entity_recall
        else 0.0,
        "entity_type_accuracy": _rate(
            sum(row["entities"]["entity_type_correct"] for row in rows),
            sum(row["entities"]["entity_name_matches"] for row in rows),
        ),
        "topic_precision": topic_precision,
        "topic_recall": topic_recall,
        "topic_f1": 2 * topic_precision * topic_recall / (topic_precision + topic_recall)
        if topic_precision + topic_recall
        else 0.0,
        "analysis_miss_rate": _rate(sum(bool(row["missed"]) for row in rows), len(rows)),
    }


def _case_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate case-level Q&A, evidence, and error metrics."""
    evidence_count = sum(row["evidence_count"] for row in rows)
    evidence_resolved = sum(row["evidence_resolved"] for row in rows)
    answer_count = sum(row["answer_count"] for row in rows)
    return {
        "qa_answer_accuracy": _rate(sum(row["answer_correct"] for row in rows), answer_count),
        "qa_answer_token_f1": mean(
            score["answer_token_f1"] for row in rows for score in row["answers"]
        ),
        "qa_reference_citation_rate": _rate(
            sum(row["answer_reference_citations"] for row in rows), answer_count
        ),
        "evidence_resolvability": _rate(evidence_resolved, evidence_count),
        "unsupported_citation_rate": _rate(evidence_count - evidence_resolved, evidence_count),
        "cases_with_errors": sum(bool(row["errors"]) for row in rows),
        "provider_errors": sum(len(row["errors"]) for row in rows),
    }


async def run_eval(
    analyzer: PageAnalyzer,
    chat: PageChat,
    *,
    fixture_root: Path = DEFAULT_FIXTURE_ROOT,
    reference_path: Path = DEFAULT_REFERENCE_PATH,
    input_cost_per_million: float = 0.0,
    output_cost_per_million: float = 0.0,
) -> dict[str, Any]:
    references = load_references(reference_path)
    rows = [
        await score_case(case, (fixture_root / case.file).read_bytes(), analyzer, chat)
        for case in references.cases
    ]
    reference_rows = [page for row in rows for page in row["reference_pages"]]
    page_rows = [
        {
            "page": page.page,
            "status": page.status,
            "error_issues": len([i for i in page.issues if i.severity == "error"]),
        }
        for row in rows
        for page in PageAnalysisResult.model_validate(row["predicted_analysis"]).pages
    ]
    analyzed_pages = len(page_rows)
    latencies = [float(row["latency_ms"]) for row in rows]
    analysis_latencies = [float(row["analysis_latency_ms"]) for row in rows]
    qa_latencies = [float(row["qa_latency_ms"]) for row in rows]
    input_tokens = math.ceil(sum(row["input_characters"] for row in rows) / 4)
    output_tokens = math.ceil(sum(row["output_characters"] for row in rows) / 4)
    offline = isinstance(analyzer, DeterministicPageAnalyzer) and isinstance(
        chat, DeterministicPageChat
    )
    prompt_digest = hashlib.sha256(f"{INSTRUCTIONS}\n{CHAT_INSTRUCTIONS}".encode()).hexdigest()[:16]
    return {
        "schema_version": "page-analysis-eval-report-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "revision": references.dataset_revision,
            "count": len(rows),
            "source": "committed synthetic born-digital mixed documents",
        },
        "analysis_schema": "page-analysis-v1",
        "prompt_sha256_16": prompt_digest,
        "mode": "offline_deterministic" if offline else "live_model",
        "live_results": "pending" if offline else "executed",
        "quality_note": "Deterministic functional verification; not AI accuracy."
        if offline
        else "Executed configured model run; inspect per-page misses.",
        "analyzer": analyzer.name,
        "chat_adapter": type(chat).__name__,
        "methods": {
            "summary": references.summary_method,
            "entities": references.entity_method,
            "topics": references.topic_method,
            "answers": references.answer_method,
            "misses": references.miss_method,
            "similarity_threshold": SIMILARITY_THRESHOLD,
        },
        "metrics": {
            **_page_metrics(reference_rows),
            **_case_metrics(rows),
            "page_failure_rate": _rate(
                sum(page["status"] == "failed" for page in page_rows), analyzed_pages
            ),
        },
        "latency_ms": {
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
            "analysis_p50": percentile(analysis_latencies, 0.50),
            "qa_p50": percentile(qa_latencies, 0.50),
        },
        "cost_estimate": {
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "input_cost_per_million_usd": input_cost_per_million,
            "output_cost_per_million_usd": output_cost_per_million,
            "usd": (input_tokens * input_cost_per_million + output_tokens * output_cost_per_million)
            / 1_000_000,
            "note": "Character/4 estimate, not provider metering; configure current prices.",
        },
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument("--references", type=Path, default=DEFAULT_REFERENCE_PATH)
    parser.add_argument("--output", type=Path, default=Path("reports/offline-metrics.json"))
    parser.add_argument("--live", action="store_true", help="Call the configured model provider")
    parser.add_argument("--input-cost-per-million", type=float, default=0.0)
    parser.add_argument("--output-cost-per-million", type=float, default=0.0)
    arguments = parser.parse_args()
    from document_intelligence.config import Settings

    settings = Settings(analyzer_backend="model" if arguments.live else "fixture")
    report = asyncio.run(
        run_eval(
            build_page_analyzer(settings),
            build_page_chat(settings),
            fixture_root=arguments.fixture_root,
            reference_path=arguments.references,
            input_cost_per_million=arguments.input_cost_per_million,
            output_cost_per_million=arguments.output_cost_per_million,
        )
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
