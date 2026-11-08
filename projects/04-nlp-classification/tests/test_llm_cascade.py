"""Selective review: validation-only fitting and bounded final routing."""

import json
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
