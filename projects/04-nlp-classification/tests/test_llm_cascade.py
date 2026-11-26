"""Selective review: validation-only fitting and bounded final routing."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from nlp_classification.llm_cascade import (
    KimiReviewer,
    ReviewBatch,
    ReviewDecision,
    apply_threshold,
    fit_threshold,
)


class StubReviewer:
    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.latency_s = 0.0
        self.calls: list[list[int]] = []

    def review(self, texts: list[str], indices: list[int]) -> dict[int, ReviewDecision]:
        self.calls.append(indices)
        return {
            index: ReviewDecision(label_index=1, rationale="business headline") for index in indices
        }


def _probas() -> np.ndarray:
    return np.asarray(
        [
            [0.55, 0.45],
            [0.90, 0.10],
            [0.55, 0.45],
            [0.95, 0.05],
        ]
    )


def test_threshold_uses_validation_score_and_fewer_reviews() -> None:
    reviewer = StubReviewer()
    threshold = fit_threshold(
        _probas(),
        [1, 0, 1, 0],
        ["stocks rally", "team wins", "markets fall", "player scores"],
        [0.5, 0.6, 0.8],
        reviewer,
    )

    assert threshold == 0.6
    assert reviewer.calls == [[0, 2]]


def test_final_routing_only_reviews_below_frozen_threshold() -> None:
    reviewer = StubReviewer()
    routed = apply_threshold(
        _probas(),
        ["stocks rally", "team wins", "markets fall", "player scores"],
        0.6,
        reviewer,
    )

    assert routed.tolist() == [1, 0, 1, 0]
    assert reviewer.calls == [[0, 2]]


def test_routing_sends_exactly_the_sub_threshold_rows_once() -> None:
    # Boundary discipline: a row at confidence exactly τ stays on the
    # transformer path; only strictly-below rows are reviewed, each exactly
    # once. A broken `<=` comparison would also send index 1, so this input
    # fails against that regression.
    probas = np.asarray(
        [
            [0.59, 0.41],  # below τ → reviewed
            [0.60, 0.40],  # exactly τ → NOT reviewed
            [0.61, 0.39],  # above τ → NOT reviewed
        ]
    )
    reviewer = StubReviewer()
    routed = apply_threshold(probas, ["markets", "stocks", "scores"], 0.6, reviewer)

    assert reviewer.calls == [[0]]  # one round-trip, exactly row 0
    assert routed.tolist() == [1, 0, 0]  # only the reviewed row is replaced


def test_kimi_reviewer_batches_eight_rows_and_preserves_order() -> None:
    class FakeAgent:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def run_sync(self, prompt: str) -> SimpleNamespace:
            self.calls.append(prompt)
            items = json.loads(prompt.split("Items: ", 1)[1])
            return SimpleNamespace(
                output=ReviewBatch(
                    decisions=[
                        ReviewDecision(label_index=index % 2, rationale="headline evidence")
                        for index in range(len(items))
                    ]
                ),
                usage=SimpleNamespace(input_tokens=10, output_tokens=5),
            )

    reviewer = KimiReviewer(["world", "sports"])
    fake = FakeAgent()
    reviewer._agent = fake  # type: ignore[assignment]
    texts = [f"headline {index}" for index in range(9)]
    decisions = reviewer.review(texts, list(range(9)))

    assert len(fake.calls) == 2
    assert [decisions[index].label_index for index in range(9)] == [0, 1] * 4 + [0]
    assert reviewer.input_tokens == 20
    assert reviewer.output_tokens == 10


def test_kimi_reviewer_rejects_wrong_batch_size() -> None:
    class BadAgent:
        def run_sync(self, prompt: str) -> SimpleNamespace:
            return SimpleNamespace(
                output=ReviewBatch(
                    decisions=[ReviewDecision(label_index=0, rationale="wrong count")]
                ),
                usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            )

    reviewer = KimiReviewer(["world", "sports"])
    reviewer._agent = BadAgent()  # type: ignore[assignment]
    with pytest.raises(ValueError, match="wrong number"):
        reviewer.review(["one", "two"], [0, 1])


def test_route_rows_returns_verdicts_and_matches_apply_threshold() -> None:
    from nlp_classification.llm_cascade import route_rows

    reviewer = StubReviewer()
    routed, decisions = route_rows(
        _probas(), ["stocks rally", "team wins", "markets fall", "player scores"], 0.6, reviewer
    )

    assert reviewer.calls == [[0, 2]]
    assert set(decisions) == {0, 2}
    assert all(decision.label_index == 1 for decision in decisions.values())
    assert (
        routed.tolist()
        == apply_threshold(
            _probas(),
            ["stocks rally", "team wins", "markets fall", "player scores"],
            0.6,
            StubReviewer(),
        ).tolist()
    )


def test_comparison_figure_adds_fresh_paired_error_bar() -> None:
    from nlp_classification.llm_cascade import _comparison_figure

    result = {
        split: {
            "baseline_f1_macro": base,
            "cascade_f1_macro": base + 0.001,
            "n_reviews": 3,
        }
        for split, base in (("validation", 0.9), ("bounded test", 0.8), ("fresh holdout", 0.7))
    }
    paired_ci = {"f1_macro": {"ci_95": [-0.004, 0.006]}}
    fig = _comparison_figure(result, paired_ci=paired_ci)

    assert len(fig.data) == 3
    assert list(fig.data[0].y) == [0.9, 0.8, 0.7]
    assert [round(v, 6) for v in fig.data[1].y] == [0.901, 0.801, 0.701]
    error_trace = fig.data[2]
    assert list(error_trace.x) == ["fresh holdout"]
    # The bar spans [baseline + lo, baseline + hi] = [0.696, 0.706] around 0.701.
    assert error_trace.error_y.arrayminus[0] == pytest.approx(0.701 - 0.696)
    assert error_trace.error_y.array[0] == pytest.approx(0.706 - 0.701)

    plain = _comparison_figure(result)
    assert len(plain.data) == 2  # no interval, no error-bar trace


def _committed_rows_and_ci() -> tuple[list[dict], dict]:
    reports = Path(__file__).parents[1] / "reports"
    rows_files = sorted(reports.glob("llm_cascade_rows_*.jsonl"))
    assert rows_files, "per-row cascade decisions are not committed"
    rows = [json.loads(line) for line in rows_files[-1].read_text().splitlines() if line.strip()]
    ci_path = reports / "llm_cascade_paired_ci.json"
    assert ci_path.exists(), "paired cascade CI report is not committed"
    return rows, json.loads(ci_path.read_text())


def test_committed_rows_reconcile_to_replication_summary() -> None:
    """The persisted per-row decisions must reproduce the reported counts and
    metrics exactly, and the paired interval must recompute from the rows."""
    from nlp_classification.llm_cascade import paired_fresh_report
    from sklearn import metrics as skm

    rows, ci_doc = _committed_rows_and_ci()
    replication = ci_doc["replication"]
    for split in ("validation", "bounded test", "fresh holdout"):
        split_rows = [row for row in rows if row["split"] == split]
        summary = replication[split]
        assert len(split_rows) > 0
        assert {row["id"] for row in split_rows} == {
            f"{split}:{index}" for index in range(len(split_rows))
        }
        assert sum(1 for row in split_rows if row["routed"]) == summary["n_reviews"]
        assert all((row["llm_verdict"] is not None) == row["routed"] for row in split_rows)
        assert all(
            row["final_pred"] == (row["llm_verdict"] if row["routed"] else row["baseline_pred"])
            for row in split_rows
        )
        y_true = [row["gold"] for row in split_rows]
        for key, pred_key in (("baseline", "baseline_pred"), ("cascade", "final_pred")):
            preds = [row[pred_key] for row in split_rows]
            assert (
                float(skm.f1_score(y_true, preds, average="macro", zero_division=0))
                == (summary[f"{key}_f1_macro"])
            )
            assert (
                float(np.mean([p == t for p, t in zip(preds, y_true, strict=True)]))
                == (summary[f"{key}_accuracy"])
            )

    recomputed = paired_fresh_report(rows)
    committed = ci_doc["fresh_holdout_paired"]
    assert recomputed["n_rows"] == committed["n_rows"]
    assert recomputed["n_reviews"] == committed["n_reviews"]
    assert recomputed["f1_macro"]["ci_95"] == committed["f1_macro"]["ci_95"]
    assert recomputed["accuracy"]["ci_95"] == committed["accuracy"]["ci_95"]
    assert recomputed["mcnemar"] == committed["mcnemar"]
