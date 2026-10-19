"""Single visual identity for every figure in the portfolio (ADR-0005)."""

from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import plotly.io as pio

_TEMPLATE: dict[str, Any] = {
    "layout": {
        "template": "plotly_dark",
        "font": {"family": "Inter, system-ui, sans-serif", "size": 14, "color": "#e2e8f0"},
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
        "title": {
            "x": 0.02,
            "xanchor": "left",
            "yanchor": "top",
            "pad": {"t": 12},
            "font": {"color": "#f1f5f9", "size": 17},
        },
        # Axis text must read on the dark canvas — both primary and secondary.
        # Gridlines are deliberately visible slate (not near-black): "contrast"
        # audit found grids/ticks illegible at embedded size.
        "xaxis": {
            "tickfont": {"color": "#e2e8f0"},
            "title": {"font": {"color": "#e2e8f0"}},
            "gridcolor": "#293548",
            "zerolinecolor": "#3b4a61",
            "linecolor": "#3b4a61",
        },
        "yaxis": {
            "tickfont": {"color": "#e2e8f0"},
            "title": {"font": {"color": "#e2e8f0"}},
            "gridcolor": "#293548",
            "zerolinecolor": "#3b4a61",
            "linecolor": "#3b4a61",
        },
        "yaxis2": {
            "tickfont": {"color": "#e2e8f0"},
            "title": {"font": {"color": "#e2e8f0"}},
            "gridcolor": "#293548",
            "zerolinecolor": "#3b4a61",
            "linecolor": "#3b4a61",
        },
        "hovermode": "x unified",
        # Hover cards must read on any background: light card, dark text.
        "hoverlabel": {
            "bgcolor": "#f8fafc",
            "font": {"color": "#0f172a", "size": 13, "family": "Inter, system-ui, sans-serif"},
            "bordercolor": "#334155",
        },
        # Horizontal legend pinned above the plot area so it can never overlap
        # the title or the takeaway annotation; per-figure overrides win.
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "x": 0.02,
            "xanchor": "left",
        },
        "showlegend": True,
    }
}

pio.templates["portfolio"] = go.layout.Template(_TEMPLATE)
pio.templates.default = "portfolio"

DEFAULT_WIDTH = 1000
DEFAULT_HEIGHT = 560


_HOVERLABEL: dict[str, Any] = {
    "bgcolor": "#f8fafc",
    "font": {"color": "#0f172a", "size": 13, "family": "Inter, system-ui, sans-serif"},
    "bordercolor": "#334155",
}


_AXIS_VISIBLE: dict[str, Any] = {
    "tickfont": {"color": "#e2e8f0"},
    "gridcolor": "#293548",
    "zerolinecolor": "#3b4a61",
    "linecolor": "#3b4a61",
}


def apply_theme(
    fig: go.Figure, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT
) -> go.Figure:
    """Apply the portfolio theme in place and return the figure.

    ``hoverlabel`` and the visible-axis defaults (tick/grid/zeroline colors,
    title color) are set EXPLICITLY, not only via the template: template
    defaults do not serialize into figure JSON, and the showcase app serves
    the JSON — so anything left only in the template never reaches the
    rendered chart and every regeneration silently drops it. Per-figure
    overrides still win (we only fill what the figure left unset).
    """
    fig.update_layout(
        width=width,
        height=height,
        template="portfolio",
        hoverlabel=dict(_HOVERLABEL),
    )
    layout = fig.layout
    title_font = layout.title.font
    if title_font.color is None:
        fig.update_layout(title={"font": {"color": "#f1f5f9", "size": 17}})
    for ax_name in ("xaxis", "yaxis", "yaxis2"):
        ax = getattr(layout, ax_name, None)
        if ax is None:
            continue
        patch: dict[str, Any] = {}
        tf = ax.tickfont
        if not (tf and tf.color):
            patch["tickfont"] = _AXIS_VISIBLE["tickfont"]
        if ax.gridcolor is None:
            patch["gridcolor"] = _AXIS_VISIBLE["gridcolor"]
        if ax.zerolinecolor is None:
            patch["zerolinecolor"] = _AXIS_VISIBLE["zerolinecolor"]
        if ax.linecolor is None:
            patch["linecolor"] = _AXIS_VISIBLE["linecolor"]
        at = ax.title.font
        if not (at and at.color):
            patch.setdefault("title", {})["font"] = {"color": "#e2e8f0"}
        if patch:
            fig.update_layout({ax_name: patch})
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


# ---------------------------------------------------------------------------
# Storytelling conventions (wave 3): every figure states its takeaway; baselines
# are visually demoted so the improvement reads instantly (grey dashed), and the
# best run is promoted (accent, thicker). Shared by all projects.
# ---------------------------------------------------------------------------

_BASELINE_HINTS: tuple[str, ...] = ("naive", "random", "lag", "majority", "persistence")


def is_baseline_run(name: str) -> bool:
    """True for run names that denote a naive/random baseline."""
    lowered = name.lower()
    return any(h in lowered for h in _BASELINE_HINTS)


def add_takeaway(fig: go.Figure, takeaway: str) -> go.Figure:
    """Render a one-line insight under the title (the figure's 'so what').

    Implemented as a second line of the title itself (small, muted span) —
    a separate annotation collides with the title on the dark template
    because both anchor just above the plot area.

    The takeaway makes the title two lines, so the template's top-pinned
    horizontal legend would overlap it; the legend drops below the plot
    instead (the house convention for crowded figures, cf. 09/10) unless
    the figure already positioned its legend explicitly.
    """
    title = fig.layout.title
    head = title.text if title.text else ""
    combined = (
        f"{head}<br><span style='font-size:13px;color:#cbd5e1'>{takeaway}</span>"
        if head
        else f"<span style='font-size:13px;color:#cbd5e1'>{takeaway}</span>"
    )
    fig.update_layout(
        title={**title.to_plotly_json(), "text": combined},
        margin={"t": 90, "l": 60, "r": 30, "b": 50},
    )
    # An untouched legend has no explicit position in the figure layout (the
    # template default applies at render time) — only then move it; figures
    # that positioned their own legend keep it. Reading ``fig.layout.legend``
    # materializes an empty Legend, so test the serialized dict, not the obj.
    legend_pos = fig.layout.legend.to_plotly_json() if fig.layout.legend is not None else {}
    if "y" not in legend_pos and "orientation" not in legend_pos:
        fig.update_layout(
            legend={
                **legend_pos,
                "orientation": "h",
                "yanchor": "top",
                "y": -0.15,
                "x": 0.02,
                "xanchor": "left",
            },
        )
    return fig


def style_runs(
    fig: go.Figure, best: str | None = None, baseline_hints: tuple[str, ...] = _BASELINE_HINTS
) -> go.Figure:
    """Restyle traces: baselines grey dashed, the best run accent and thicker.

    Matches on trace name (case-insensitive substring against ``baseline_hints``).
    Bar traces reject ``line`` styling, so they get marker-only treatment. Traces
    without a name are left untouched.
    """
    for trace in fig.data:
        name = getattr(trace, "name", None)
        if not name:
            continue
        lowered = str(name).lower()
        is_bar = getattr(trace, "type", None) in ("bar", "histogram")
        if best is not None and best.lower() in lowered:
            if is_bar:
                trace.update(marker={"line": {"width": 1.5, "color": "#2dd4bf"}})
            else:
                trace.update(line={"width": 3.5}, marker={"size": 10})
        elif any(h in lowered for h in baseline_hints):
            if is_bar:
                trace.update(marker={"color": "#64748b"})
            else:
                trace.update(
                    line={"color": "#64748b", "dash": "dash", "width": 1.5},
                    marker={"color": "#64748b"},
                )
    return fig
