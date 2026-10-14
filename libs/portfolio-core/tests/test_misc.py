from pathlib import Path

import plotly.graph_objects as go
from portfolio_core.config import Settings
from portfolio_core.llm import MockProviderUnsetError, build_model
from portfolio_core.manifest import ProjectInfo, load_index
from portfolio_core.plotting import save_html, save_json


def test_build_model_mock_mode() -> None:
    model = build_model(Settings(), mock_response='{"ok": true}')
    assert model is not None


def test_build_model_requires_mock_response_without_key() -> None:
    try:
        build_model(Settings())
    except MockProviderUnsetError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected MockProviderUnsetError")


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


def test_mock_model_supports_streaming() -> None:
    """The offline mock must work for run_stream (SSE chat), not just run."""
    import asyncio

    from pydantic_ai import Agent

    model = build_model(Settings(), mock_response="hello world")
    agent = Agent(model, output_type=str)

    async def collect() -> str:
        text = ""
        async with agent.run_stream("hi") as result:
            async for delta in result.stream_text():
                text += delta
        return text

    assert asyncio.run(collect()) == "hello world"
