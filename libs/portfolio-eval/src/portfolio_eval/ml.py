"""Standard ML metrics as typed callables, aggregating to plotly + JSON."""

from dataclasses import dataclass, field

import numpy as np
import plotly.graph_objects as go
from portfolio_core.plotting import apply_theme
from sklearn import metrics as skm

from portfolio_eval.metrics import MetricResult, RunResult


def classification_metrics(y_true: list[int], y_pred: list[int]) -> list[MetricResult]:
    """Accuracy / precision / recall / F1 (macro) in one call."""
    return [
        MetricResult("accuracy", float(skm.accuracy_score(y_true, y_pred))),
        MetricResult(
            "precision_macro",
            float(skm.precision_score(y_true, y_pred, average="macro", zero_division=0)),
        ),
        MetricResult(
            "recall_macro",
            float(skm.recall_score(y_true, y_pred, average="macro", zero_division=0)),
        ),
        MetricResult(
            "f1_macro", float(skm.f1_score(y_true, y_pred, average="macro", zero_division=0))
        ),
    ]


def regression_metrics(y_true: list[float], y_pred: list[float]) -> list[MetricResult]:
    """MAE / RMSE / MAPE in one call (MAPE as %, lower is better)."""
    yt, yp = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    mae = float(np.mean(np.abs(yt - yp)))
    rmse = float(np.sqrt(np.mean((yt - yp) ** 2)))
    mask = yt != 0
    mape = (
        float(np.mean(np.abs((yt[mask] - yp[mask]) / yt[mask])) * 100)
        if mask.any()
        else float("nan")
    )
    return [
        MetricResult("mae", mae, higher_is_better=False),
        MetricResult("rmse", rmse, higher_is_better=False),
        MetricResult("mape_pct", mape, higher_is_better=False),
    ]


@dataclass
class RunComparison:
    """Several runs by several metrics: grouped bar figure + markdown table."""

    runs: list[RunResult] = field(default_factory=list)

    def add(self, run: RunResult) -> None:
        self.runs.append(run)

    def figure(self, metric_names: list[str] | None = None) -> go.Figure:
        names = metric_names or sorted({m.name for r in self.runs for m in r.metrics})
        fig = go.Figure()
        for name in names:
            values = []
            for r in self.runs:
                m = r.get(name)
                values.append(m.value if m is not None else np.nan)
            fig.add_bar(name=name, x=[r.name for r in self.runs], y=values)
        fig.update_layout(barmode="group", title="Run comparison")
        return apply_theme(fig)

    def to_markdown(self) -> str:
        names = sorted({m.name for r in self.runs for m in r.metrics})
        header = "| run | " + " | ".join(names) + " |"
        sep = "|---" * (len(names) + 1) + "|"
        rows = [
            f"| {r.name} | "
            + " | ".join(f"{m.value:.4f}" if (m := r.get(n)) else "-" for n in names)
            + " |"
            for r in self.runs
        ]
        return "\n".join([header, sep, *rows])
