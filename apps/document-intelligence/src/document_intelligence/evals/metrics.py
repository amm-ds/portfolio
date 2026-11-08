"""Deterministic, transparent metrics for the mixed document-analysis harness."""

import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
SIMILARITY_THRESHOLD = 0.55


def normalize(value: str) -> str:
    """Case-fold and collapse non-alphanumeric separators for exact comparisons."""
    return " ".join(TOKEN_PATTERN.findall(value.casefold()))


def token_f1(reference: str, predicted: str) -> float:
    """Symmetric bag-of-words F1; reported separately from citation support."""
    expected = Counter(TOKEN_PATTERN.findall(reference.casefold()))
    actual = Counter(TOKEN_PATTERN.findall(predicted.casefold()))
    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0
    true_positive = sum((expected & actual).values())
    precision = true_positive / sum(actual.values())
    recall = true_positive / sum(expected.values())
    return 2 * precision * recall / (precision + recall) if true_positive else 0.0


def best_match_scores(references: Sequence[str], predictions: Sequence[str]) -> list[float]:
    """Return each reference's best lexical score without reusing prediction constraints."""
    return [
        max((token_f1(reference, predicted) for predicted in predictions), default=0.0)
        for reference in references
    ]


def mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


def prf[T](references: Iterable[T], predictions: Iterable[T]) -> dict[str, float | int]:
    """Set-based precision/recall/F1 with duplicate outputs removed."""
    expected = set(references)
    actual = set(predictions)
    true_positive = len(expected & actual)
    precision = true_positive / len(actual) if actual else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    return {
        "true_positive": true_positive,
        "predicted": len(actual),
        "reference": len(expected),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
    }


def percentile(values: Sequence[float], quantile: float) -> float:
    """Nearest-rank percentile with an explicit empty-run value."""
    if not values:
        return 0.0
    if not 0 < quantile <= 1:
        raise ValueError("quantile must be in (0, 1]")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1)]
