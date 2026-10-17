"""Probe-row schema tests on tiny fabricated models (offline, no transformers)."""

import numpy as np
import pytest
import torch
from nlp_classification.latency_probe import (
    cost_per_1k,
    quantize_int8,
    sample_texts,
    sklearn_row,
    time_single_predictions,
    torch_row,
)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from torch import nn

TEXTS = [
    "sports team wins the final match",
    "markets rally as stocks climb",
    "new telescope reveals distant worlds",
    "startup ships a new software release",
]
LABELS = ["World", "Sports", "Business", "Sci/Tech"]


class TinyTokenizer:
    """Whitespace tokenizer standing in for the HF tokenizer (returns ids)."""

    def __call__(self, text: str, **kwargs: object) -> dict[str, list[int]]:
        ids = [hash(w) % 1000 + 1 for w in text.split()]
        return {"input_ids": ids}


class TinyClassifier(nn.Module):
    """Tiny embedding-bag classifier producing one logit per class."""

    def __init__(self, n_labels: int) -> None:
        super().__init__()
        self.emb = nn.EmbeddingBag(1001, 8, mode="mean")
        self.head = nn.Linear(8, n_labels)

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        return self.head(self.emb(input_ids))


@pytest.fixture()
def tiny_logreg() -> Pipeline:
    y = np.tile([0, 1, 2, 3], 3)
    return Pipeline([("tfidf", TfidfVectorizer()), ("clf", LogisticRegression(max_iter=200))]).fit(
        TEXTS * 3, y
    )


def test_sample_texts_seeded_and_wraps() -> None:
    a = sample_texts(TEXTS, 6, seed=42)
    b = sample_texts(TEXTS, 6, seed=42)
    assert a == b
    assert len(a) == 6
    assert all(t in TEXTS for t in a)


def test_time_single_predictions_counts() -> None:
    calls = {"n": 0}

    def predict(text: str) -> int:
        calls["n"] += 1
        return 0

    stats = time_single_predictions(predict, TEXTS, warmup=2)
    assert stats["n"] == len(TEXTS)
    assert calls["n"] == len(TEXTS) + 2  # warmup runs through the same closure
    assert stats["p50_latency_ms"] >= 0.0
    assert stats["throughput_pred_s"] > 0.0


def test_sklearn_row_schema(tmp_path, tiny_logreg: Pipeline) -> None:
    artifact = tmp_path / "baseline.joblib"
    artifact.write_bytes(b"placeholder")
    row = sklearn_row(
        tiny_logreg,
        artifact,
        TEXTS,
        n=4,
        seed=42,
        metrics={"accuracy": 0.872, "f1_macro": 0.8714},
    )
    for key in (
        "variant",
        "size_mb",
        "p50_latency_ms",
        "throughput_pred_s",
        "cost_per_1k_usd",
        "accuracy",
        "f1_macro",
    ):
        assert key in row, f"missing key {key}"
    assert row["n"] == 4
    assert row["cost_per_1k_usd"] == 0.0  # sklearn: no per-token meter
    assert row["mean_input_tokens"] is None
    assert row["accuracy"] == pytest.approx(0.872)
    assert row["size_mb"] > 0.0


def test_torch_row_schema_and_measured_tokens() -> None:
    torch.manual_seed(0)
    model = TinyClassifier(len(LABELS)).eval()
    tokenizer = TinyTokenizer()
    row = torch_row(
        "tiny_fp32",
        "tiny.pt",
        model,
        tokenizer,
        LABELS,
        TEXTS,
        n=4,
        max_length=16,
        seed=42,
        metrics={"accuracy": 0.902, "f1_macro": 0.9021},
    )
    assert row["variant"] == "tiny_fp32"
    assert row["n"] == 4
    assert row["size_mb"] > 0.0
    assert row["mean_input_tokens"] > 0.0  # measured, not estimated
    assert 1 <= row["mean_output_tokens"] <= 5  # class name tokenizes short
    assert row["cost_per_1k_usd"] > 0.0
    assert row["accuracy"] == pytest.approx(0.902)
    assert row["f1_macro"] == pytest.approx(0.9021)


def test_quantize_int8_shrinks_and_keeps_output_shape() -> None:
    torch.manual_seed(0)
    model = TinyClassifier(len(LABELS)).eval()
    ids = torch.randint(0, 1001, (2, 5))
    mask = torch.ones_like(ids)
    before = model(ids, mask)
    int8 = quantize_int8(model)
    after = int8(ids, mask)
    assert after.shape == before.shape
    assert isinstance(int8.head, nn.quantized.dynamic.Linear)  # dynamic int8 applied


def test_cost_per_1k_rate_card() -> None:
    # 100 in + 5 out tokens/pred -> (100*1 + 5*4)/1e6 $/pred -> *1000 per 1k
    assert cost_per_1k(100.0, 5.0) == pytest.approx(0.12)
