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

    rb.build(
        tmp_path,
        figures={
            "bars": go.Figure(go.Bar(x=["a"], y=[1])),
            "line": go.Figure(go.Scatter(x=["a"], y=[2])),
        },
    )
    assert (tmp_path / "metrics.json").exists()
    assert json.loads((tmp_path / "metrics.json").read_text())["m1"]["f1"] == 0.8
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "figures" / "bars.html").exists()
    body = (tmp_path / "report.html").read_text()
    # figures are embedded as interactive divs, not dead relative links
    assert body.count('class="plotly-graph-div"') == 2
    assert body.count("cdn.plot.ly") == 1  # CDN bundle included exactly once
    assert 'href="figures/' not in body


def test_eval_report_mermaid_embedding(tmp_path: Path) -> None:
    r = EvalReport(title="Demo")
    r.add_mermaid("Architecture", 'flowchart LR\n  A["ingest"] --> B["embed"]')
    body = r.write(tmp_path / "report.html").read_text()
    assert '<pre class="mermaid">' in body
    assert "A[&quot;ingest&quot;] --&gt; B[&quot;embed&quot;]" in body  # escaped, no raw HTML
    assert "mermaid.esm.min.js" in body


def test_runs_from_metrics_skips_detail_blocks(tmp_path: Path) -> None:
    from portfolio_eval.report import runs_from_metrics

    (tmp_path / "metrics.json").write_text(
        json.dumps(
            {
                "model_a": {"f1": 0.9, "note": "nested dicts are not metrics"},
                "detail": {"heldout": {"f1": 0.8}},
                "_meta": {"seed": 42},
            }
        )
    )
    runs = runs_from_metrics(tmp_path)
    assert [r.name for r in runs] == ["model_a"]
    assert [m.name for m in runs[0].metrics] == ["f1"]


def test_figures_from_json_roundtrip(tmp_path: Path) -> None:
    import plotly.graph_objects as go
    from portfolio_eval.report import figures_from_json

    figs_dir = tmp_path / "figures"
    figs_dir.mkdir()
    (figs_dir / "bars.json").write_text(
        go.Figure(go.Bar(x=["a"], y=[1])).to_json(), encoding="utf-8"
    )
    loaded = figures_from_json(figs_dir)
    assert list(loaded) == ["bars"]
    assert loaded["bars"].data[0].y[0] == 1


def test_mermaid_blocks_from_story(tmp_path: Path) -> None:
    from portfolio_eval.report import mermaid_blocks_from_story

    story = (
        "project_id: p\n"
        "sections:\n"
        "  - id: background\n"
        "    text_md: |\n"
        "      Some prose.\n\n"
        "      ```mermaid\n"
        "      flowchart LR\n"
        "        A --> B\n"
        "      ```\n"
        "      More prose.\n"
    )
    (tmp_path / "story.yaml").write_text(story, encoding="utf-8")
    blocks = mermaid_blocks_from_story(tmp_path)
    assert list(blocks) == ["background diagram 1"]
    assert "A --> B" in blocks["background diagram 1"]
    assert mermaid_blocks_from_story(tmp_path / "missing") == {}
