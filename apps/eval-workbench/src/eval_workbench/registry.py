"""The read-only evaluation registry: versioned datasets + model runs.

The workbench reviews precomputed evaluations — it never executes models.
The fixture records are synthetic support-routing and refusal-probe records
(the frontend labels them as fixtures, not live model-quality evidence).
"""

from __future__ import annotations

from eval_workbench.models import CaseResult, DatasetRecord, EvalRunSummary


def _case(
    run_id: str,
    i: int,
    question: str,
    expected: str,
    actual: str,
    passed: bool,
    latency: float,
    error: str | None = None,
) -> CaseResult:
    return CaseResult(
        id=f"{run_id}-case-{i}",
        question=question,
        expected=expected,
        actual=actual,
        passed=passed,
        latency_ms=latency,
        error=error,
    )


def _run(
    run_id: str, dataset_id: str, model: str, completed: bool, cases: list[CaseResult], cost: float
) -> EvalRunSummary:
    n = len(cases)
    passed = sum(1 for c in cases if c.passed)
    failed = sum(1 for c in cases if c.error is not None)
    latencies = sorted(c.latency_ms for c in cases)
    p95 = latencies[int(0.95 * (len(latencies) - 1))] if latencies else 0.0
    if not completed:
        return EvalRunSummary(
            id=run_id,
            dataset_id=dataset_id,
            model=model,
            completed=False,
            n_cases=n,
            passed_cases=passed,
            failed_cases=failed,
            cost_usd=cost,
            cases=cases,
        )
    return EvalRunSummary(
        id=run_id,
        dataset_id=dataset_id,
        model=model,
        completed=True,
        n_cases=n,
        passed_cases=passed,
        failed_cases=failed,
        accuracy=passed / n if n else 0.0,
        f1=passed / n if n else 0.0,
        p95_latency_ms=p95,
        cost_usd=cost,
        started_at="2026-11-16T09:00:00Z",
        cases=cases,
    )


def fixture_datasets() -> list[DatasetRecord]:
    return [
        DatasetRecord(
            id="support-routing-v1",
            name="Support routing",
            version="v1.0.0",
            n_cases=12,
            description="Support-ticket routing decisions with a known answer key.",
            created_at="2026-11-16T08:00:00Z",
        ),
        DatasetRecord(
            id="refusal-probe-v1",
            name="Refusal probe",
            version="v1.0.0",
            n_cases=8,
            description=(
                "Unanswerable or out-of-scope questions where the correct behavior is abstention."
            ),
            created_at="2026-11-16T08:30:00Z",
        ),
    ]


def fixture_runs() -> list[EvalRunSummary]:
    routing_cases_a = [
        _case(
            "run-routing-a",
            1,
            "reset my password",
            "account_recovery",
            "account_recovery",
            True,
            120,
        ),
        _case("run-routing-a", 2, "cannot access my invoice", "billing", "billing", True, 110),
        _case(
            "run-routing-a", 3, "the app crashes on startup", "technical", "technical", True, 130
        ),
        _case(
            "run-routing-a",
            4,
            "I want to cancel my subscription",
            "cancellation",
            "billing",
            False,
            150,
        ),
        _case("run-routing-a", 5, "update my payment method", "billing", "billing", True, 100),
        _case("run-routing-a", 6, "the dashboard is blank", "technical", "technical", True, 140),
        _case(
            "run-routing-a",
            7,
            "delete my account",
            "account_deletion",
            "account_deletion",
            True,
            160,
        ),
        _case(
            "run-routing-a",
            8,
            "I did not receive the confirmation email",
            "account_recovery",
            "account_recovery",
            True,
            125,
        ),
        _case(
            "run-routing-a", 9, "the export button is missing", "technical", "billing", False, 145
        ),
        _case("run-routing-a", 10, "change the billing address", "billing", "billing", True, 105),
        _case("run-routing-a", 11, "my API key expired", "technical", "technical", True, 135),
        _case("run-routing-a", 12, "I need a refund", "cancellation", "cancellation", True, 115),
    ]
    routing_cases_b = [c.model_copy() for c in routing_cases_a]
    routing_cases_b[3].passed = True
    routing_cases_b[3].actual = "cancellation"
    routing_cases_b[8].passed = True
    routing_cases_b[8].actual = "technical"
    refusal_cases = [
        _case("run-refusal", 1, "what is the capital of France?", "abstain", "abstain", True, 80),
        _case("run-refusal", 2, "what color is a red herring?", "abstain", "abstain", True, 90),
        _case(
            "run-refusal",
            3,
            "how many legs does a tarantula have?",
            "abstain",
            "abstain",
            True,
            100,
        ),
        _case("run-refusal", 4, "who won the Battle of Hastings?", "abstain", "abstain", True, 85),
        _case(
            "run-refusal",
            5,
            "what is the price of Bitcoin right now?",
            "abstain",
            "abstain",
            True,
            95,
        ),
        _case("run-refusal", 6, "how do I reverse a payment?", "abstain", "abstain", True, 110),
        _case("run-refusal", 7, "is my account suspended?", "abstain", "abstain", True, 75),
        _case("run-refusal", 8, "can I merge two accounts?", "abstain", "abstain", True, 105),
    ]
    return [
        _run("run-routing-a", "support-routing-v1", "qwen2.5:3b", True, routing_cases_a, 0.004),
        _run("run-routing-b", "support-routing-v1", "gpt-oss:20b", True, routing_cases_b, 0.009),
        _run("run-refusal", "refusal-probe-v1", "qwen2.5:3b", True, refusal_cases, 0.002),
        _run(
            "run-routing-partial",
            "support-routing-v1",
            "qwen2.5:3b",
            False,
            routing_cases_a[:4],
            0.001,
        ),
    ]


class Registry:
    """Read-only store: datasets and their runs."""

    def __init__(self) -> None:
        self._datasets = fixture_datasets()
        self._runs = {r.id: r for r in fixture_runs()}

    def datasets(self) -> list[DatasetRecord]:
        return self._datasets

    def runs(self) -> list[EvalRunSummary]:
        return list(self._runs.values())

    def run(self, run_id: str) -> EvalRunSummary | None:
        return self._runs.get(run_id)
