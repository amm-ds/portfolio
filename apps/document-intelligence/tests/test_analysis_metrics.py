import pytest

from document_intelligence.evals.metrics import (
    normalize,
    percentile,
    prf,
    token_f1,
)


def test_normalize_and_token_f1_handle_paraphrase_order_and_duplicates() -> None:
    assert normalize("  FastAPI, SQL & Python ") == "fastapi sql python"
    assert token_f1("Python SQL FastAPI", "FastAPI and Python plus SQL") == pytest.approx(0.75)
    assert token_f1("", "") == 1.0
    assert token_f1("source", "") == 0.0


def test_prf_deduplicates_and_handles_empty_sets() -> None:
    result = prf(("a", "b"), ("a", "a", "c"))
    assert result["true_positive"] == 1
    assert result["predicted"] == 2
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5
    assert prf((), ())["f1"] == 0.0


def test_percentile_uses_nearest_rank_and_validates_quantile() -> None:
    assert percentile([], 0.95) == 0.0
    assert percentile([4.0, 1.0, 3.0, 2.0], 0.5) == 2.0
    assert percentile([4.0, 1.0, 3.0, 2.0], 0.95) == 4.0
    with pytest.raises(ValueError, match="quantile"):
        percentile([1.0], 0.0)
