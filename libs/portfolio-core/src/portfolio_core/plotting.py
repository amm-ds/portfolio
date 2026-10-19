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

# House layout standard (user-specified): short title + smaller subtitle as a
# second title line, legend at the RIGHT outside the plot, margins that always
# show both axis labels. Anything the figure set explicitly still wins — these
# only fill unset values, and they are serialized so served JSON carries them.
_TITLE_FONT = {"color": "#f1f5f9", "size": 16}
_SUBTITLE_SIZE = "12.5px"
_MARGINS = {"l": 70, "r": 140, "t": 110, "b": 70}
_LEGEND_RIGHT = {
    "orientation": "v",
    "x": 1.02,
    "xanchor": "left",
    "y": 1,
    "yanchor": "top",
    "font": {"size": 13, "color": "#e2e8f0"},
    "bgcolor": "rgba(0,0,0,0)",
}


def _legend_is_positioned(layout: Any) -> bool:
    """True when the figure deliberately placed its legend (any non-default)."""
    leg = layout.legend
    orient = getattr(leg, "orientation", None)
    y = getattr(leg, "y", None)
    x = getattr(leg, "x", None)
    return orient is not None or y is not None or x is not None


def apply_theme(
    fig: go.Figure, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT
) -> go.Figure:
    """Apply the portfolio theme in place and return the figure.

    Theme defaults are set EXPLICITLY (not only via the template): template
    defaults do not serialize into figure JSON, and the showcase app serves
    the JSON — anything left only in the template never reaches the rendered
    chart and every regeneration silently drops it. Per-figure overrides
    still win (we only fill what the figure left unset).
    """
    fig.update_layout(
        width=width,
        height=height,
        template="portfolio",
        hoverlabel=dict(_HOVERLABEL),
    )
    layout = fig.layout
    # Title: standard font when unset.
    title_font = layout.title.font
    if title_font.color is None and title_font.size is None:
        fig.update_layout(title={"font": dict(_TITLE_FONT)})
    elif title_font.color is None:
        fig.update_layout(title={"font": {"color": _TITLE_FONT["color"]}})
    # Margins: fill to the house standard (never shrink a figure's own).
    m = layout.margin
    patch_m = {
        key: val
        for key, val in _MARGINS.items()
        if getattr(m, key, None) is None or getattr(m, key) < val
    }
    if patch_m:
        fig.update_layout(margin=patch_m)
    # Legend: right-vertical unless the figure placed it deliberately.
    if layout.showlegend is not False and not _legend_is_positioned(layout):
        fig.update_layout(legend=dict(_LEGEND_RIGHT))
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
    """Render the figure's longer explanation as a second, smaller title line.

    House layout: short headline title + 12.5px muted subtitle; the legend
    sits at the RIGHT, so the two-line title never collides with it, and the
    top margin (110) fits both lines without clipping. A figure that
    positioned its own legend keeps it.
    """
    title = fig.layout.title
    head = title.text if title.text else ""
    span = f"<span style='font-size:{_SUBTITLE_SIZE};color:#cbd5e1'>"
    combined = f"{head}<br>{span}{takeaway}</span>" if head else f"{span}{takeaway}</span>"
    m = fig.layout.margin
    fig.update_layout(
        title={**title.to_plotly_json(), "text": combined},
        margin={
            "l": m.l if m.l is not None else _MARGINS["l"],
            "r": m.r if m.r is not None else _MARGINS["r"],
            "t": max(m.t or 0, _MARGINS["t"]),
            "b": m.b if m.b is not None else _MARGINS["b"],
        },
    )
    # An untouched legend has no explicit position in the figure layout (the
    # template default applies at render time) — only then move it to the
    # right; figures that positioned their own legend keep it. Reading
    # ``fig.layout.legend`` materializes an empty Legend, so test the dict.
    legend_pos = fig.layout.legend.to_plotly_json() if fig.layout.legend is not None else {}
    if "y" not in legend_pos and "orientation" not in legend_pos and "x" not in legend_pos:
        fig.update_layout(legend=dict(_LEGEND_RIGHT))
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
