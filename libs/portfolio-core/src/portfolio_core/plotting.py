"""Single visual identity for every figure in the portfolio (ADR-0005)."""

from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import plotly.io as pio

_TEMPLATE: dict[str, Any] = {
    "layout": {
        "template": "plotly_dark",
        "font": {"family": "Inter, system-ui, sans-serif", "size": 14},
        "colorway": [
            "#2dd4bf",  # teal
            "#38bdf8",  # sky
            "#f472b6",  # pink
            "#fbbf24",  # amber
            "#a78bfa",  # violet
            "#34d399",  # emerald
        ],
        "paper_bgcolor": "#0f172a",
        "plot_bgcolor": "#0f172a",
        "margin": {"l": 60, "r": 30, "t": 60, "b": 50},
        "title": {"x": 0.02, "xanchor": "left"},
        "hovermode": "x unified",
    }
}

pio.templates["portfolio"] = go.layout.Template(_TEMPLATE)
pio.templates.default = "portfolio"

DEFAULT_WIDTH = 1000
DEFAULT_HEIGHT = 560


def apply_theme(
    fig: go.Figure, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT
) -> go.Figure:
    """Apply the portfolio theme in place and return the figure."""
    fig.update_layout(width=width, height=height, template="portfolio")
    return fig


def save_html(fig: go.Figure, path: str | Path, title: str | None = None) -> Path:
    """Write a self-contained (CDN plotly.js) HTML figure for docs embedding."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(p, include_plotlyjs="cdn", full_html=True, auto_open=False)
    return p


def save_json(fig: go.Figure, path: str | Path) -> Path:
    """Write a figure JSON payload consumed by the React showcase app."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.write_json(str(p))
    return p
