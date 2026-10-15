"""Markdown report assembly for the routing-optimization showcase.

Pure functions from evaluation records (:class:`~routing_optimization.evaluate.
InstanceEvaluation`) to markdown tables: per-instance detail, per-solver
summary, and per-family aggregation — reporting BOTH gaps the benchmark
cares about: distance gap % and the vehicle-count delta (Solomon ranks
vehicles first, distance second). Shared math helpers (``gap_pct``,
``family_of``) live here and are re-exported by ``evaluate`` for compatibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from routing_optimization.evaluate import InstanceEvaluation


def family_of(instance: str) -> str:
    """Solomon family of an instance: C101 -> C1, RC208 -> RC2, R112 -> R1."""
    letters = instance.rstrip("0123456789")
    digits = instance[len(letters) :]
    return f"{letters}{digits[0]}" if digits else letters


def gap_pct(distance: float, best_known: float) -> float:
    """Distance gap in percent relative to the best-known value."""
    return (distance - best_known) / best_known * 100.0


def _veh_delta_str(delta: int | None) -> str:
    """Formatted signed vehicle-count delta ('n/a' when the reference has none)."""
    if delta is None:
        return "n/a"
    return f"+{delta}" if delta > 0 else str(delta)


def results_markdown(evaluations: list[InstanceEvaluation]) -> str:
    """Full per-instance markdown results table (distance + vehicle gaps)."""
    lines = [
        "| instance | best known (dist / veh) | solver | distance | vehicles | gap % | "
        "veh Δ | runtime (ms) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for ev in evaluations:
        ref = (
            f"{ev.best_known:.2f} / {ev.best_known_vehicles}"
            if ev.best_known is not None and ev.best_known_vehicles is not None
            else (f"{ev.best_known:.2f} / n/a" if ev.best_known is not None else "n/a")
        )
        for r in ev.runs:
            gap = (
                "n/a"
                if ev.best_known is None
                else f"{gap_pct(r.total_distance, ev.best_known):.2f}"
            )
            delta = (
                r.n_vehicles - ev.best_known_vehicles
                if ev.best_known_vehicles is not None
                else None
            )
            best_marker = " **(best)**" if r == ev.best() else ""
            lines.append(
                f"| {ev.instance} | {ref} "
                f"| {r.solver}{best_marker} | {r.total_distance:.2f} | {r.n_vehicles} "
                f"| {gap} | {_veh_delta_str(delta)} | {r.runtime_s * 1e3:.1f} |"
            )
    return "\n".join(lines)


def summary_markdown(evaluations: list[InstanceEvaluation]) -> str:
    """Mean gap / runtime / vehicles per solver across instances, with mean
    vehicle-count delta vs the references (benchmark's primary criterion)."""
    lines = [
        "| solver | mean gap % | mean distance | mean vehicles | mean veh Δ | mean runtime (ms) |",
        "|---|---|---|---|---|---|",
    ]
    solvers = sorted({r.solver for ev in evaluations for r in ev.runs})
    for solver in solvers:
        gaps = [
            gap_pct(r.total_distance, ev.best_known)
            for ev in evaluations
            for r in ev.runs
            if r.solver == solver and ev.best_known is not None
        ]
        deltas = [
            r.n_vehicles - ev.best_known_vehicles
            for ev in evaluations
            for r in ev.runs
            if r.solver == solver and ev.best_known_vehicles is not None
        ]
        runs = [r for ev in evaluations for r in ev.runs if r.solver == solver]
        mean_gap = f"{sum(gaps) / len(gaps):.2f}" if gaps else "n/a"
        mean_delta = f"{sum(deltas) / len(deltas):+.2f}" if deltas else "n/a"
        mean_dist = sum(r.total_distance for r in runs) / len(runs)
        mean_veh = sum(r.n_vehicles for r in runs) / len(runs)
        mean_rt = sum(r.runtime_s for r in runs) / len(runs) * 1e3
        lines.append(
            f"| {solver} | {mean_gap} | {mean_dist:.2f} | {mean_veh:.1f} "
            f"| {mean_delta} | {mean_rt:.1f} |"
        )
    return "\n".join(lines)


def family_markdown(evaluations: list[InstanceEvaluation]) -> str:
    """Mean distance gap AND mean vehicle delta per Solomon family per solver."""
    lines = [
        "| family | instances | solver | mean gap % | mean veh Δ |",
        "|---|---|---|---|---|",
    ]
    families = sorted({family_of(ev.instance) for ev in evaluations})
    for fam in families:
        members = [ev for ev in evaluations if family_of(ev.instance) == fam and ev.best_known]
        for solver in sorted({r.solver for ev in members for r in ev.runs}):
            gaps = [
                gap_pct(r.total_distance, ev.best_known)
                for ev in members
                for r in ev.runs
                if r.solver == solver and ev.best_known is not None
            ]
            deltas = [
                r.n_vehicles - ev.best_known_vehicles
                for ev in members
                for r in ev.runs
                if r.solver == solver and ev.best_known_vehicles is not None
            ]
            if gaps:
                mean_delta = f"{sum(deltas) / len(deltas):+.2f}" if deltas else "n/a"
                lines.append(
                    f"| {fam} | {len(members)} | {solver} "
                    f"| {sum(gaps) / len(gaps):.2f} | {mean_delta} |"
                )
    return "\n".join(lines)
