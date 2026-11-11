#!/usr/bin/env python3
"""Committed figure axis-limit gate ("check the limits of the charts").

Two failure classes from the audit trail, caught at CI time over every
committed figure payload:

1. **Clipped authored ranges** — a fixed ``layout.*axis.range`` that cuts off
   trace data (the curve hits a wall and disappears). FAIL.
2. **Pinned far-too-wide ranges** — an authored window more than 5x the data
   span, wasting most of the canvas (the "flat curve in a sea of nothing"
   family). WARN, reported for the figure diet. Full unit-interval windows
   ([0, 1] rate/metric scales) are a plotting convention and are skipped.

Log axes: plotly stores authored log ranges in log10 units, so authored-range
checks are skipped for them; their DATA must still be strictly positive
(non-positive values on a log axis break rendering). Category/date axes have
no numeric window and are skipped.

Run: uv run python scripts/check_figure_axes.py
"""

import base64
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any, cast

REPO = Path(__file__).resolve().parents[1]

_CLIP_TOLERANCE = 1e-9
_OVERSHOOT_WARN_RATIO = 5.0

_BDATA_FMT = {
    "f8": ("d", 8),
    "f4": ("f", 4),
    "i8": ("q", 8),
    "i4": ("i", 4),
    "u4": ("I", 4),
}


def decode_array(value: object) -> list[float]:
    """Plotly typed-array record ({dtype, bdata}) or plain list → floats."""
    if isinstance(value, dict) and "bdata" in value:
        spec = _BDATA_FMT.get(str(value.get("dtype")))
        if spec is None:
            return []
        fmt, size = spec
        raw = base64.b64decode(str(value["bdata"]))
        n = len(raw) // size
        return [float(v) for v in struct.unpack(f"<{n}{fmt}", raw[: n * size])]
    if isinstance(value, list):
        return [float(v) for v in value if isinstance(v, (int, float))]
    return []


def axis_ranges(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any], list[float]]]:
    """(layout axis key, axis dict, trace values bound to that axis).

    Subplot-aware: each trace carries ``xaxis``/``yaxis`` refs ("y", "y3")
    naming the layout axis ("yaxis", "yaxis3") it draws on. Values pooled
    across axes would false-flag a correctly-scaled subplot panel.
    """
    layout = payload.get("layout", {})
    data = payload.get("data", [])
    axes: dict[str, dict[str, Any]] = {}

    def bucket(ref: object, is_x: bool) -> dict[str, Any]:
        suffix = ""
        if ref not in (None, "x", "y") and str(ref)[:1] in ("x", "y"):
            suffix = str(ref)[1:]
        key = f"{'x' if is_x else 'y'}axis{suffix}"
        if key not in axes:
            raw = layout.get(key)
            axes[key] = {"values": [], "raw": raw if isinstance(raw, dict) else {}}
        return axes[key]

    for trace in data:
        if not isinstance(trace, dict):
            continue
        xb = bucket(trace.get("xaxis", "x"), True)
        yb = bucket(trace.get("yaxis", "y"), False)
        cast(list[float], xb["values"]).extend(decode_array(trace.get("x")))
        cast(list[float], yb["values"]).extend(decode_array(trace.get("y")))
    return [
        (key, cast(dict[str, Any], b["raw"]), cast(list[float], b["values"]))
        for key, b in axes.items()
    ]


def check_figure(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return [f"{path.name}: unreadable payload ({e})"], []
    for key, axis, values in axis_ranges(payload):
        finite = [v for v in values if math.isfinite(v)]
        if not finite:
            continue
        if axis.get("type") == "log":
            if any(v <= 0 for v in finite):
                errors.append(
                    f"{path.name} {key}: log axis carries non-positive data "
                    f"(min {min(finite):.6g}) — rendering breaks"
                )
            continue  # authored log ranges are log10 units; skip range checks
        rng = axis.get("range")
        if not (isinstance(rng, list) and len(rng) == 2):
            continue
        lo, hi = float(rng[0]), float(rng[1])
        dmin, dmax = min(finite), max(finite)
        if lo > dmin + _CLIP_TOLERANCE or hi < dmax - _CLIP_TOLERANCE:
            errors.append(
                f"{path.name} {key}: authored range [{lo:.6g}, {hi:.6g}] clips "
                f"data [{dmin:.6g}, {dmax:.6g}]"
            )
        span_data = dmax - dmin
        span_range = hi - lo
        # rate/metric axes conventionally occupy the full unit interval even
        # when one curve hugs a corner — that is a plotting convention, not
        # wasted canvas. Flag only windows that are both wide AND off-unit.
        unit_window = lo >= 0 and 1 <= hi <= 1.1 and all(0 <= v <= 1.05 for v in finite)
        if span_data > 0 and span_range > span_data * _OVERSHOOT_WARN_RATIO and not unit_window:
            warnings.append(
                f"{path.name} {key}: authored window {span_range:.4g} is "
                f"{span_range / span_data:.1f}x the data span {span_data:.4g}"
            )
    return errors, warnings


def main() -> int:
    all_errors: list[str] = []
    all_warnings: list[str] = []
    figures = sorted(REPO.glob("projects/*/reports*/figures/*.json"))
    for fig in figures:
        errors, warnings = check_figure(fig)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
    for w in all_warnings:
        print(f"WARN {w}")
    for e in all_errors:
        print(f"ERROR {e}")
    if all_errors:
        print(
            f"figure-axes: {len(all_errors)} clipped/over-limit axis(es) "
            f"across {len(figures)} figures"
        )
        return 1
    print(
        f"figure-axes: OK ({len(figures)} figures; "
        f"{len(all_warnings)} over-wide window warning(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
