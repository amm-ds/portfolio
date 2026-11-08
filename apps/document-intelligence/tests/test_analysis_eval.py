import asyncio
from pathlib import Path

from document_intelligence.analysis.page_analyzer import DeterministicPageAnalyzer
from document_intelligence.analysis.page_chat import DeterministicPageChat
from document_intelligence.documents.parser import ParsedPage
from document_intelligence.domain.analysis import (
    PageAnalysisOutput,
    PageChatMessage,
    PageChatResponse,
)
from document_intelligence.evals.analysis_runner import run_eval
from document_intelligence.evals.contracts import DEFAULT_FIXTURE_ROOT, load_references


def test_offline_page_eval_executes_all_references() -> None:
    report = asyncio.run(run_eval(DeterministicPageAnalyzer(), DeterministicPageChat()))
    references = load_references()
    assert report["schema_version"] == "page-analysis-eval-report-v1"
    assert report["analysis_schema"] == "page-analysis-v1"
    assert report["dataset"]["revision"] == references.dataset_revision
    assert report["dataset"]["count"] == len(references.cases) == 7
    assert report["mode"] == "offline_deterministic"
    assert report["live_results"] == "pending"
    metrics = report["metrics"]
    assert metrics["provider_errors"] == 0
    assert metrics["page_failure_rate"] == 0.0
    assert metrics["evidence_resolvability"] == 1.0
    assert metrics["reference_pages"] == sum(len(case.pages) for case in references.cases)
    assert "classification_accuracy" not in metrics
    assert "correction_rate" not in metrics
    assert "analysis_miss_rate" in metrics
    assert len(report["cases"]) == len(references.cases)
    for case in report["cases"]:
        result = case["predicted_analysis"]
        assert result["schema_version"] == "page-analysis-v1"
        assert "misses" in case


class FailingAnalyzer:
    name = "failing-test-analyzer"

    async def analyze_page(self, page: ParsedPage) -> PageAnalysisOutput:
        raise RuntimeError("intentional analysis failure")


class FailingChat:
    async def chat(self, page: ParsedPage, messages: list[PageChatMessage]) -> PageChatResponse:
        raise RuntimeError("intentional chat failure")


def test_eval_retains_provider_failures_as_measured_cases(tmp_path: Path) -> None:
    references = load_references()
    single_reference = references.model_copy(update={"cases": [references.cases[0]]})
    reference_path = tmp_path / "references.json"
    reference_path.write_text(single_reference.model_dump_json(), encoding="utf-8")
    report = asyncio.run(
        run_eval(
            FailingAnalyzer(),
            FailingChat(),
            fixture_root=DEFAULT_FIXTURE_ROOT,
            reference_path=reference_path,
        )
    )
    assert report["dataset"]["count"] == 1
    assert report["metrics"]["provider_errors"] == 4
    assert report["metrics"]["cases_with_errors"] == 1
    assert report["metrics"]["page_failure_rate"] == 1.0
    assert report["metrics"]["analysis_miss_rate"] == 1.0
    assert report["cases"][0]["errors"] == [
        "analysis:RuntimeError",
        "analysis:RuntimeError",
        "chat:RuntimeError",
        "chat:RuntimeError",
    ]
    assert report["cases"][0]["misses"]


def test_shared_fixtures_remain_text_identical() -> None:
    public = DEFAULT_FIXTURE_ROOT.parent / "web" / "public" / "fixtures"
    backend = {path.name for path in DEFAULT_FIXTURE_ROOT.glob("*.pdf")}
    # The web copy is owned by the UI; every fixture present in both must match.
    for name in backend & {path.name for path in public.glob("*.pdf")}:
        from document_intelligence.documents.parser import parse_pdf

        assert (
            parse_pdf((public / name).read_bytes()).text
            == parse_pdf((DEFAULT_FIXTURE_ROOT / name).read_bytes()).text
        )
