import json
from pathlib import Path

from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.report import EvalReport, ReportBuilder


def test_eval_report_writes_html(tmp_path: Path) -> None:
    r = EvalReport(title="Demo")
    r.add_markdown_table("T", "| a | b |\n|---|---|\n| 1 | 2 |")
    r.add_html("Fig", "<p>hi</p>")
    out = r.write(tmp_path / "report.html")
    body = out.read_text()
    assert "Demo" in body and "<th>a</th>" in body and "<td>1</td>" in body


def test_report_builder_end_to_end(tmp_path: Path) -> None:
    rb = ReportBuilder(title="Demo", figures_dir=tmp_path / "figures")
    rb.add_run(RunResult("m1", [MetricResult("f1", 0.8)]))
    import plotly.graph_objects as go

    rb.build(tmp_path, figures={"bars": go.Figure(go.Bar(x=["a"], y=[1]))})
    assert (tmp_path / "metrics.json").exists()
    assert json.loads((tmp_path / "metrics.json").read_text())["m1"]["f1"] == 0.8
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "figures" / "bars.html").exists()
