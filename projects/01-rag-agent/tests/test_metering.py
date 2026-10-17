"""Wave-15 metering tests: per-phase spend table, budget-cap propagation, telemetry.

All tests are offline: every LLM call is backed by a scripted FunctionModel or
by raw duck-typed usage objects — no network, no provider required. Metering
is forced active/inactive via ``start_metering(active=...)`` so the tests are
independent of whether this machine has hosted credentials configured.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from portfolio_core.llm_budget import BudgetExceededError
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from rag_agent.config import RAGConfig
from rag_agent.evaluate import run_rag_eval
from rag_agent.index import Retriever
from rag_agent.judge import LLMRubricJudge
from rag_agent.metering import PhaseMeter, start_metering
from rag_agent.reporting import RAGRun, cost_telemetry, write_cost_telemetry
from rag_agent.schemas import EvalQuestion
from rag_agent.verify import LLMEntailmentJudge

CANNED_ANALYSIS_JSON = json.dumps(
    {
        "summary": "Test-only canned answer.",
        "citations": [
            {"chunk_id": "c", "article_id": "a", "title": "t", "excerpt": "e", "score": 1.0}
        ],
        "confidence": 0.5,
    }
)
RUBRIC_JSON = json.dumps({"score": 0.9, "reason": "supported by the context"})
CLAIM_VERDICTS_JSON = json.dumps(
    {"verdicts": [{"claim": "Test-only canned answer.", "supported": True, "reason": "checked"}]}
)


def _constant_model(response: str) -> FunctionModel:
    def respond(messages: list, info: Any) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=response)])

    return FunctionModel(respond)


def _usage(input_tokens: int, output_tokens: int, cached: int = 0) -> Any:
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
    )


def _synthetic_rag_run() -> RAGRun:
    from portfolio_eval.rag import RAGEvalResult

    return RAGRun(
        eval_result=RAGEvalResult(n=2, faithfulness=0.8, answer_relevance=0.7, context_recall=0.5),
        latencies_s=[0.1, 0.2],
        input_tokens=[100, 120],
        output_tokens=[50, 60],
    )


def test_phase_meter_pricing_and_cached_share() -> None:
    meter = start_metering(active=True)
    # 1000 fresh input + 500 output at the kimi-k2.8 reference card.
    meter.record("agent", _usage(1000, 500))
    # 800 of 1000 input tokens are cache reads (priced at 30% of input).
    meter.record("ragas", _usage(1000, 0, cached=800))
    snap = meter.snapshot()
    assert snap["phases"]["agent"]["calls"] == 1
    assert snap["phases"]["agent"]["spend_usd"] == pytest.approx(0.001 + 0.002)
    assert snap["phases"]["ragas"]["spend_usd"] == pytest.approx(0.0002 + 0.00024)
    assert snap["phases"]["ragas"]["cached_input_tokens"] == 800
    assert snap["total"]["calls"] == 2
    assert snap["total"]["spend_usd"] == pytest.approx(0.00344)
    assert snap["ledger_spend_usd"] == pytest.approx(0.00344)
    assert "never a billed amount" in snap["cost_basis"]


def test_phase_meter_extracts_property_style_usage() -> None:
    """pydantic-ai 2.55 exposes ``result.usage`` as a PROPERTY; meter it truly.

    Regression guard for the platform duck-typing gap (``meter_result`` only
    recognizes a ``.usage()`` method): a result-like object whose ``usage``
    attribute is a plain usage object must record its tokens, not zeros.
    """

    class FakeResult:
        @property
        def usage(self) -> Any:
            return _usage(2000, 1000)

    meter = start_metering(active=True)
    meter.record("agent", FakeResult())
    snap = meter.snapshot()
    assert snap["phases"]["agent"]["input_tokens"] == 2000
    assert snap["phases"]["agent"]["spend_usd"] == pytest.approx(0.002 + 0.004)


def test_phase_meter_inactive_is_noop() -> None:
    meter = start_metering(active=False)
    meter.record("agent", _usage(1_000_000, 1_000_000))
    snap = meter.snapshot()
    assert not snap["active"]
    assert snap["total"]["spend_usd"] == 0.0
    assert "phases" in snap and set(snap["phases"]) == {"agent", "judge", "verify", "ragas"}


def test_phase_meter_rejects_unknown_phase() -> None:
    meter = PhaseMeter(active=True)
    with pytest.raises(KeyError):
        meter.record("nope", _usage(1, 1))


def test_run_rag_eval_meters_all_llm_phases(config: RAGConfig, retriever: Retriever) -> None:
    from rag_agent.agent import build_agent

    meter = start_metering(active=True)
    agent = build_agent(config, model=_constant_model(CANNED_ANALYSIS_JSON))
    questions = [EvalQuestion(question="why are plants green", relevant_article_ids=["photo-000"])]
    rag_run = run_rag_eval(
        config,
        agent,
        retriever,
        questions,
        judge=LLMRubricJudge(model=_constant_model(RUBRIC_JSON)),
        verifier=LLMEntailmentJudge(model=_constant_model(CLAIM_VERDICTS_JSON)),
    )
    assert rag_run.eval_result.n == 1
    snap = meter.snapshot()
    assert snap["phases"]["agent"]["calls"] == 1
    assert snap["phases"]["judge"]["calls"] == 2  # faithfulness + relevance verdicts
    assert snap["phases"]["verify"]["calls"] == 1  # one batched claim-verdict call


def test_ragas_llm_result_metering() -> None:
    from rag_agent.ragas_eval import _meter_llm_result

    meter = start_metering(active=True)
    result = SimpleNamespace(
        llm_output={
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "prompt_tokens_details": {"cached_tokens": 40},
            }
        }
    )
    _meter_llm_result(result)
    snap = meter.snapshot()
    ragas = snap["phases"]["ragas"]
    assert ragas["calls"] == 1
    assert ragas["input_tokens"] == 100
    assert ragas["output_tokens"] == 20
    assert ragas["cached_input_tokens"] == 40
    assert ragas["spend_usd"] == pytest.approx(60e-6 + 40 * 0.3e-6 + 20 * 4e-6)


def test_ragas_llm_result_without_usage_is_skipped() -> None:
    from rag_agent.ragas_eval import _meter_llm_result

    meter = start_metering(active=True)
    _meter_llm_result(SimpleNamespace(llm_output={}))
    _meter_llm_result(SimpleNamespace(llm_output=None))
    assert meter.snapshot()["phases"]["ragas"]["calls"] == 0


def test_judge_reraises_budget_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    from rag_agent import judge as judge_mod

    meter = PhaseMeter(active=True)

    def boom(phase: str, result: Any, model_name: str | None = None) -> None:
        raise BudgetExceededError("cap reached")

    monkeypatch.setattr(meter, "record", boom)
    monkeypatch.setattr(judge_mod, "get_meter", lambda: meter)
    llm_judge = LLMRubricJudge(model=_constant_model(RUBRIC_JSON))
    with pytest.raises(BudgetExceededError):
        llm_judge.judge("q", "ctx", "answer")


def test_verify_repair_reraises_budget_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    from rag_agent import verify as verify_mod

    meter = PhaseMeter(active=True)

    def boom(phase: str, result: Any, model_name: str | None = None) -> None:
        raise BudgetExceededError("cap reached")

    monkeypatch.setattr(meter, "record", boom)
    monkeypatch.setattr(verify_mod, "get_meter", lambda: meter)
    judge = LLMEntailmentJudge(model=_constant_model(CLAIM_VERDICTS_JSON))
    with pytest.raises(BudgetExceededError):
        judge.verify_claims("q", ["a claim"], "evidence")
    with pytest.raises(BudgetExceededError):
        judge.repair("q", "a claim", "evidence")


def test_cost_telemetry_phases_breakdown(config: RAGConfig) -> None:
    meter = start_metering(active=True)
    meter.record("agent", _usage(1000, 500))
    meter.record("ragas", _usage(1000, 0, cached=800))
    snapshot = meter.snapshot()
    rag_run = _synthetic_rag_run()
    payload = cost_telemetry(config, rag_run, wall_time_s=60.0, phases=snapshot)
    assert payload["api_cost_usd"] == pytest.approx(snapshot["total"]["spend_usd"])
    assert payload["phases"]["agent"]["calls"] == 1
    assert payload["total"]["calls"] == 2
    assert payload["meter"]["active"] is True
    assert payload["meter"]["ledger_spend_usd"] == pytest.approx(snapshot["total"]["spend_usd"])
    # Legacy schema fields are unchanged for existing readers.
    assert payload["n_queries"] == 2
    assert payload["total_input_tokens"] == 220

    path = write_cost_telemetry(config, rag_run, wall_time_s=60.0, phases=snapshot)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["phases"]["ragas"]["cached_input_tokens"] == 800
    assert written["meter"]["cost_basis"] == snapshot["cost_basis"]


def test_cli_evaluate_surfaces_budget_exceeded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rag_agent import cli as cli_mod
    from typer.testing import CliRunner

    monkeypatch.chdir(tmp_path)

    def boom(*args: Any, **kwargs: Any) -> None:
        raise BudgetExceededError("LLM budget cap reached: estimated $3.00 >= $3.00")

    monkeypatch.setattr(cli_mod, "run_evaluation", boom)
    result = CliRunner().invoke(cli_mod.app, ["evaluate"])
    assert result.exit_code == 2
    assert "LLM budget cap" in result.output


def test_provider_settings_preset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hosted merges neutralize temperature; ollama keeps the no-think body."""
    from rag_agent import provider as provider_mod

    monkeypatch.setattr("portfolio_core.llm.is_hosted_provider", lambda *a, **k: True)
    hosted = provider_mod.model_settings_for_provider({"temperature": 0})
    assert "temperature" not in hosted
    assert hosted["extra_body"]["thinking"] == {"type": "disabled"}
    # existing extra_body entries survive the merge
    hosted_merged = provider_mod.model_settings_for_provider(
        {"temperature": 0, "extra_body": {"custom": 1}}
    )
    assert hosted_merged["extra_body"]["custom"] == 1
    assert hosted_merged["extra_body"]["thinking"] == {"type": "disabled"}

    monkeypatch.setattr("portfolio_core.llm.is_hosted_provider", lambda *a, **k: False)
    local = provider_mod.model_settings_for_provider()
    assert local is not None and local["extra_body"] == {"think": False}
