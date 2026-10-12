"""Platform-integration tests: exercise the portfolio_core/portfolio_eval APIs
this project relies on. This both validates our usage and lifts shared-library
coverage when this directory is tested on its own (root pytest gate).
"""

import json
from pathlib import Path

import plotly.graph_objects as go
from portfolio_core.io import sha256_of
from portfolio_core.plotting import apply_theme, save_html, save_json
from portfolio_eval import metrics as pe_metrics
from portfolio_eval.ml import RunComparison, classification_metrics, regression_metrics
from portfolio_eval.report import EvalReport, ReportBuilder


def test_regression_metrics_sanity() -> None:
    results = {m.name: m.value for m in regression_metrics([1.0, 2.0, 4.0], [1.0, 2.5, 3.0])}
    assert results["mae"] > 0
    assert results["rmse"] >= results["mae"]
    assert results["mape_pct"] > 0


def test_compare_runs_protocol() -> None:
    run_a = pe_metrics.RunResult("a", classification_metrics([0, 1], [0, 1]))
    run_b = pe_metrics.RunResult("b", classification_metrics([0, 1], [1, 1]))
    out = pe_metrics.compare_runs([run_a, run_b], "accuracy")
    assert out["ranking"][0] == "a"
    assert out["a"] == 1.0


def test_run_comparison_figure_and_markdown() -> None:
    runs = [
        pe_metrics.RunResult("a", classification_metrics([0, 1, 2], [0, 1, 2])),
        pe_metrics.RunResult("b", classification_metrics([0, 1, 2], [0, 1, 1])),
    ]
    comparison = RunComparison(runs)
    fig = comparison.figure()
    assert len(fig.data) > 0
    md = comparison.to_markdown()
    assert "| run |" in md and "a" in md and "b" in md


def test_plotting_save_html_and_json(tmp_path: Path) -> None:
    fig = apply_theme(go.Figure(data=go.Bar(x=["a"], y=[1])))
    html = save_html(fig, tmp_path / "fig.html")
    js = save_json(fig, tmp_path / "fig.json")
    assert html.exists() and "<html" in html.read_text()
    payload = json.loads(js.read_text())
    assert payload["data"][0]["type"] == "bar"


def test_eval_report_write(tmp_path: Path) -> None:
    report = EvalReport(title="t")
    report.add_markdown_table("Metrics", "| a | b |\n|---|---|\n| 1 | 2 |")
    report.add_html("Notes", "<p>hello</p>")
    out = report.write(tmp_path / "report.html")
    text = out.read_text()
    assert "<td>1</td>" in text and "hello" in text


def test_report_builder_build(tmp_path: Path) -> None:
    run = pe_metrics.RunResult("r", classification_metrics([0, 1], [0, 1]))
    builder = ReportBuilder(title="t", figures_dir=tmp_path / "figures")
    builder.add_run(run)
    fig = apply_theme(go.Figure(data=go.Bar(x=["a"], y=[1])))
    builder.build(tmp_path, figures={"bars": fig})
    metrics = json.loads((tmp_path / "metrics.json").read_text())
    assert metrics["r"]["accuracy"] == 1.0
    assert (tmp_path / "figures" / "bars.html").exists()


def test_sha256_of_is_stable(tmp_path: Path) -> None:
    f = tmp_path / "x.bin"
    f.write_bytes(b"abc")
    assert sha256_of(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert sha256_of(f) == sha256_of(f)
