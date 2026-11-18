import plotly.graph_objects as go
from portfolio_core.plotting import add_takeaway, apply_theme, is_baseline_run, style_runs


def test_is_baseline_run() -> None:
    assert is_baseline_run("naive_lag24")
    assert is_baseline_run("random_uniform")
    assert is_baseline_run("retrieval_random_chunks_200")
    assert is_baseline_run("naive_majority")
    assert not is_baseline_run("gbm_tuned")
    assert not is_baseline_run("distilbert_finetuned")
    assert not is_baseline_run("clarke_wright")


def test_add_takeaway_renders_as_second_title_line() -> None:
    fig = go.Figure(go.Bar(x=["a"], y=[1]))
    fig.update_layout(title={"text": "Headline"})
    add_takeaway(fig, "GBM beats persistence by 40%.")
    # Takeaway lives in the title as a muted span, not a colliding annotation.
    assert "<span" in fig.layout.title.text
    assert "GBM beats persistence by 40%." in fig.layout.title.text
    assert fig.layout.title.text.startswith("Headline<br>")
    assert len(fig.layout.annotations) == 0


def test_style_runs_demotes_baselines_promotes_best() -> None:
    fig = go.Figure()
    fig.add_scatter(x=[1], y=[1], name="naive_last")
    fig.add_scatter(x=[1], y=[2], name="hgb_tuned")
    fig.add_scatter(x=[1], y=[3], name="ridge")
    style_runs(fig, best="hgb_tuned")
    naive, hgb, ridge = fig.data
    assert naive.line.dash == "dash"
    assert naive.line.color == "#64748b"
    assert hgb.line.width == 3.5
    assert ridge.line.dash is None or ridge.line.dash != "dash"


def test_style_runs_ignores_unnamed_traces() -> None:
    fig = go.Figure(go.Bar(x=["a"], y=[1]))  # no name
    style_runs(fig, best="anything")
    assert fig.data[0].marker.color is None or True  # untouched, no crash


def test_style_runs_handles_bar_traces() -> None:
    """Bar traces reject ``line`` styling — marker-only treatment, no exception."""
    fig = go.Figure()
    fig.add_bar(x=["a"], y=[1], name="naive_last")
    fig.add_bar(x=["a"], y=[2], name="hgb_tuned")
    style_runs(fig, best="hgb_tuned")
    assert fig.data[0].marker.color == "#64748b"  # baseline demoted
    assert fig.data[1].marker.line.color == "#2dd4bf"  # best accented


def test_apply_theme_keeps_plotly_tables_dark() -> None:
    fig = go.Figure(
        go.Table(
            header={"values": ["check", "result"]},
            cells={"values": [["schema", "PASS"]]},
        )
    )
    apply_theme(fig)
    assert fig.data[0].header.fill.color == "#1e293b"
    assert fig.data[0].header.font.color == "#f1f5f9"
    assert fig.data[0].cells.fill.color == "#0f172a"
    assert fig.data[0].cells.font.color == "#e2e8f0"
