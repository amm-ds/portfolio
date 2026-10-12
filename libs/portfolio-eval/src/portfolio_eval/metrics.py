"""Metric protocol + run comparison. New metrics plug in here (platform.md)."""

from dataclasses import dataclass, field
from typing import Any, Protocol


class Metric(Protocol):
    """Callable metric contract: ``name`` attribute + ``__call__(y_true, y_pred)``."""

    name: str

    def __call__(self, y_true: list[int], y_pred: list[int]) -> float: ...


@dataclass(frozen=True)
class MetricResult:
    """One metric reading within a run."""

    name: str
    value: float
    higher_is_better: bool = True
    split: str = "test"


@dataclass
class RunResult:
    """Named run with its metric readings."""

    name: str
    metrics: list[MetricResult] = field(default_factory=list)

    def get(self, metric_name: str) -> MetricResult | None:
        return next((m for m in self.metrics if m.name == metric_name), None)


def compare_runs(runs: list[RunResult], metric_name: str) -> dict[str, Any]:
    """Value and rank of one metric across runs (best first)."""
    vals: dict[str, float] = {}
    higher = True
    for r in runs:
        m = r.get(metric_name)
        if m is None:
            vals[r.name] = float("nan")
        else:
            vals[r.name] = m.value
            higher = m.higher_is_better
    ranked = sorted(vals, key=lambda k: vals[k], reverse=higher)
    return {"ranking": ranked, **{k: round(v, 6) for k, v in vals.items()}}
