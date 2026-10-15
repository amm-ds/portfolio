from pathlib import Path

import plotly.graph_objects as go
from portfolio_core.manifest import ProjectInfo, load_index
from portfolio_core.plotting import save_html, save_json


def test_manifest_loads_index(tmp_path: Path) -> None:
    (tmp_path / "01-a").mkdir()
    (tmp_path / "01-a" / "portfolio.yaml").write_text(
        "id: 01-a\ntitle: A\ndomain: x\ntopic: T\ntechniques: [t]\ndata: synthetic\norder: 1\n"
    )
    idx = load_index(tmp_path)
    assert len(idx) == 1 and isinstance(idx[0], ProjectInfo) and idx[0].id == "01-a"


def test_figure_exports(tmp_path: Path) -> None:
    fig = go.Figure(go.Bar(x=["a"], y=[1]))
    html = save_html(fig, tmp_path / "fig.html")
    js = save_json(fig, tmp_path / "fig.json")
    assert "plotly" in html.read_text().lower()
    assert '"data"' in js.read_text()
