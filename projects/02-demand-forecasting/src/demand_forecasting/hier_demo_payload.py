"""Hierarchy explorer demo payload (wave 23b) — schema v1 for the
``hierarchy-explorer`` showcase demo (see ``demos/hierarchy-explorer.yaml``).

Builds ``reports/hier_demo_payload.json`` — a compact, fully precomputed
catalog for the hierarchical track (protocol ``hierarchical_rolling_v1``, the
wave-23a track committed in ``reports_hier/metrics.json``):

- top-level blocks: ``groups`` (per-group per-level rmae/mae per variant,
  coherence per variant, and the headline — copied from the COMMITTED
  ``reports_hier/metrics.json`` after the drift guard passes), ``catalog``
  (12 nodes across both benchmark hierarchies), and ``evaluation_metadata``
  (protocol, scored origins, candidates, the metrics source path);
- per catalog node x the 3 most recent committed origins: the level name,
  parent path, children count, the as-of-origin history (bounded window of
  2 seasonal cycles), the horizon-window actuals, and curves for
  ``seasonal_naive`` / ``auto_ets`` / ``lgbm_global`` /
  ``lgbm_global+bottom_up`` / ``lgbm_global+mint_shrink`` — re-run through
  the SAME scoring core as the committed metrics (``score_hierarchy``), so
  the payload curves are structurally identical to the run that produced
  the committed scalars — plus the per-node coherence error of both
  reconciled variants on the horizon window.

Catalog selection is deterministic and volume-based (documented in
``_select_catalog``): at each hierarchy level the top-K nodes by total
historical volume are picked (ties broken by node id), so a rebuild picks
exactly the same nodes.

Drift guard: the builder re-runs the full scoring for both groups and
asserts the re-run reproduces EVERY committed scalar the payload carries —
per-level mae/rmae for all 12 variants, coherence for all variants, the
headline block, and the rmae recomputed from the retained scored frame via
``mae_rmae_by_level`` — all at tolerance 1e-9. Any mismatch raises instead
of shipping. Because the re-run reproduces the committed run, the ``groups``
block can be copied from ``reports_hier/metrics.json`` verbatim.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]  # no stubs in the venv
from portfolio_core.logging import get_logger

from demand_forecasting.config import ForecastConfig
from demand_forecasting.evaluate import _json_safe
from demand_forecasting.hierarchical import (
    CANDIDATES,
    VARIANTS,
    GroupSpec,
    level_members,
    level_names,
    load_group_frames,
    mae_rmae_by_level,
    score_hierarchy,
)

logger = get_logger(__name__)

DEMO_ID = "hierarchy-explorer"
PROJECT_ID = "02-demand-forecasting"
PAYLOAD_SCHEMA_VERSION = 1
PAYLOAD_NAME = "hier_demo_payload.json"
METRICS_SOURCE = "reports_hier/metrics.json"
# The 5 variants the explorer charts per node (auto_theta omitted: the
# payload carries the floor, the best statistical arm, the ML base, and both
# reconciliations of the ML base).
CURVE_VARIANTS = (
    "seasonal_naive",
    "auto_ets",
    "lgbm_global",
    "lgbm_global+bottom_up",
    "lgbm_global+mint_shrink",
)
RECONCILED_VARIANTS = ("lgbm_global+bottom_up", "lgbm_global+mint_shrink")
# Catalog entries are built for the N most recent committed origins per group.
N_ORIGINS_PER_GROUP = 3
# As-of-origin history window, in seasonal cycles (~2 cycles by contract).
HISTORY_CYCLES = 2
DRIFT_TOL = 1e-9

# Per-group catalog quotas by LEVEL NAME (level_names() keys: the total is
# always included; every other level contributes its top-K nodes by total
# historical volume — see _select_catalog). 6 nodes per group = 12 total:
#   Labour       — total, 2 regions, 2 gender x region, 1 bottom
#   TourismSmall — total, 1 purpose, 1 state, 3 bottom (city/noncity mix by volume)
CATALOG_QUOTAS: dict[str, dict[str, int]] = {
    "Labour": {"Country/Region": 2, "Country/Gender/Region": 2, "bottom": 1},
    "TourismSmall": {"Country/Purpose": 1, "Country/Purpose/State": 1, "bottom": 3},
}


# ---------------------------------------------------------------------------
# Catalog selection (deterministic, volume-based)
# ---------------------------------------------------------------------------


def _node_volume(Y_df: pd.DataFrame) -> dict[str, float]:
    """Total historical volume (sum of y over all periods) per node id."""
    vol = Y_df.groupby("unique_id")["y"].sum()
    return {str(u): float(v) for u, v in vol.items()}


def _select_catalog(
    Y_df: pd.DataFrame,
    tags: dict[str, np.ndarray],
    quotas: dict[str, int],
) -> list[str]:
    """Deterministic catalog: the total node plus, per level, the top-K nodes
    by total historical volume (ties broken by node id string).

    The total node is ``tags``' first key's single member (the hierarchy
    root). Levels missing from ``quotas`` contribute nothing; a quota larger
    than the level's size takes the whole level.
    """
    levels = level_names(tags)
    members = level_members(tags)
    vol = _node_volume(Y_df)
    picked = sorted(members["total"], key=lambda u: (-vol[u], u))
    for level in levels[1:]:
        k = quotas.get(level, 0)
        if k <= 0:
            continue
        picked.extend(sorted(members[level], key=lambda u: (-vol[u], u))[:k])
    return picked


# ---------------------------------------------------------------------------
# Hierarchy structure helpers (parent path / children via S's 0/1 rows + tags)
# ---------------------------------------------------------------------------


def _pattern(S: np.ndarray, idx: int) -> np.ndarray:
    """The bottom-membership pattern of one node: which bottom series
    aggregate into it (S rows are 0/1 aggregation vectors)."""
    return np.asarray(S[idx] > 0.0)


class _HierarchyNav:
    """Level-aware navigation over one aggregation tree.

    The benchmarks are partition trees: every node has exactly one ancestor
    per level above it, and its children are the next level's members whose
    bottom set is contained in its own. Pattern containment is NON-strict so
    single-child chains (a mid node whose set equals its only child's) link
    correctly — strict-subset logic mis-parents those.
    """

    def __init__(
        self,
        S: np.ndarray,
        uids: list[str],
        levels: list[str],
        members: dict[str, set[str]],
    ) -> None:
        self.S = S
        self.uids = uids
        self.levels = levels
        self.level_of = {u: level for level in levels for u in members[level]}
        self.members = members

    def index(self, node: str) -> int:
        return self.uids.index(node)

    def parent_path(self, node: str) -> list[str]:
        """Ancestor ids ordered total -> direct parent (empty for the total)."""
        pat = _pattern(self.S, self.index(node))
        path: list[str] = []
        for level in self.levels[: self.levels.index(self.level_of[node])]:
            ancestors = [
                u for u in self.members[level] if np.all(_pattern(self.S, self.index(u)) >= pat)
            ]
            if len(ancestors) != 1:  # pragma: no cover - partition-tree invariant
                raise ValueError(f"{node}: level {level} ancestors {ancestors} != 1")
            path.append(ancestors[0])
        return path

    def children(self, node: str) -> list[str]:
        """Immediate children: the next level's members under this node."""
        level = self.level_of[node]
        if level == self.levels[-1]:
            return []
        child_level = self.levels[self.levels.index(level) + 1]
        pat = _pattern(self.S, self.index(node))
        return sorted(
            u for u in self.members[child_level] if np.all(_pattern(self.S, self.index(u)) <= pat)
        )


# ---------------------------------------------------------------------------
# Catalog entries (per node x origin)
# ---------------------------------------------------------------------------


def _round_curve(v: np.ndarray) -> list[float]:
    """Display rounding for payload curves (4 decimals, as the workbench)."""
    return [round(float(x), 4) for x in v]


def _node_coherence(
    fc: dict[str, np.ndarray], idx: int, actual: np.ndarray, child_rows: list[int]
) -> dict[str, float]:
    """Per-node coherence error of the reconciled variants on the horizon.

    Same hand-testable definition as the track: mean over window periods of
    ``|fc_node - sum children_fc| / max(|actual_node|, 1)`` — the children's
    forecasts sum exactly the bottom rows under the node (S partitions).
    """
    out: dict[str, float] = {}
    den = np.maximum(np.abs(actual), 1.0)
    for name in RECONCILED_VARIANTS:
        pred = fc[name][idx]
        child_sum = fc[name][child_rows].sum(axis=0) if child_rows else pred
        out[name] = round(float(np.mean(np.abs(pred - child_sum) / den)), 6)
    return out


def _catalog_entry(
    node: str,
    group: str,
    nav: _HierarchyNav,
    Y_df: pd.DataFrame,
    pooled: pd.DataFrame,
    origin_dates: list[str],
    spec: GroupSpec,
) -> dict[str, Any]:
    """One catalog node with a per-origin block for the committed origins."""
    uids = nav.uids
    idx = nav.index(node)
    child_rows = [nav.index(c) for c in nav.children(node)]
    m = spec.season_length
    entries: list[dict[str, Any]] = []
    for origin in origin_dates:
        cutoff = pd.Timestamp(origin)
        sub = pooled[(pooled["unique_id"] == node) & (pooled["origin"] == origin)].sort_values("ds")
        hist = Y_df[(Y_df["unique_id"] == node) & (Y_df["ds"] <= cutoff)].sort_values("ds")
        hist = hist.tail(HISTORY_CYCLES * m)
        fc = {v: sub[v].to_numpy(dtype=float) for v in CURVE_VARIANTS}
        actual = sub["actual"].to_numpy(dtype=float)
        entry: dict[str, Any] = {
            "origin": origin,
            "history": {
                "dates": [str(d.date()) for d in hist["ds"]],
                "y": _round_curve(hist["y"].to_numpy(dtype=float)),
            },
            "actuals": {
                "dates": [str(d.date()) for d in sub["ds"]],
                "y": _round_curve(actual),
            },
            "models": {v: {"y_pred": _round_curve(fc[v])} for v in CURVE_VARIANTS},
        }
        if child_rows:
            # parent nodes carry the reconciled-variants' coherence gap;
            # bottom nodes are trivially coherent (no children) — omitted
            all_fc = {
                v: pooled[pooled["origin"] == origin]
                .pivot(index="unique_id", columns="ds", values=v)
                .loc[uids]
                .to_numpy(dtype=float)
                for v in RECONCILED_VARIANTS
            }
            entry["coherence"] = _node_coherence(all_fc, idx, actual, child_rows)
        entries.append(entry)
    return {
        "node": node,
        "group": group,
        "level": nav.level_of[node],
        "parent_path": nav.parent_path(node),
        "children_count": len(child_rows),
        "children": nav.children(node),
        "origins": entries,
    }


# ---------------------------------------------------------------------------
# Drift guard
# ---------------------------------------------------------------------------


def _assert_matches(path: str, actual: Any, committed: Any, tol: float) -> None:
    """Recursive float comparison over the committed scalar tree."""
    if isinstance(committed, dict):
        if not isinstance(actual, dict):
            raise ValueError(f"drift guard: {path} expected a dict, got {type(actual).__name__}")
        for key, val in committed.items():
            if key not in actual:
                raise ValueError(f"drift guard: {path}.{key} missing from the re-run block")
            _assert_matches(f"{path}.{key}", actual[key], val, tol)
    elif isinstance(committed, list):
        if not isinstance(actual, list) or len(actual) != len(committed):
            raise ValueError(f"drift guard: {path} list shape mismatch")
        for i, val in enumerate(committed):
            _assert_matches(f"{path}[{i}]", actual[i], val, tol)
    elif isinstance(committed, bool) or committed is None or isinstance(committed, int | str):
        if actual != committed:
            raise ValueError(
                f"drift guard: {path}: recomputed {actual!r} != committed {committed!r}"
            )
    elif isinstance(committed, float):
        if not isinstance(actual, int | float) or not np.isclose(
            float(actual), committed, rtol=tol, atol=tol
        ):
            raise ValueError(
                f"drift guard: {path}: recomputed {actual!r} != committed {committed!r}"
            )


def _drift_guard(
    rerun: dict[str, Any],
    committed: dict[str, Any],
    pooled: pd.DataFrame,
    tags: dict[str, np.ndarray],
) -> None:
    """Assert the re-run reproduced every committed scalar the payload carries.

    Compares the full metrics block (per-level mae/rmae for every variant,
    coherence, headline, bootstrap, origin plan) at 1e-9, then recomputes the
    per-level table from the retained scored frame via ``mae_rmae_by_level``
    as an independent path to the same numbers.
    """
    for key in (
        "protocol",
        "freq",
        "season_length",
        "horizon",
        "min_train",
        "origins",
        "candidates",
        "levels",
        "per_level",
        "coherence",
        "headline",
        "bootstrap",
    ):
        _assert_matches(
            f"groups.{committed['group']}.{key}", rerun.get(key), committed[key], DRIFT_TOL
        )
    levels = level_names(tags)
    members = level_members(tags)
    per_level, _ = mae_rmae_by_level(pooled, members, levels, VARIANTS)
    for variant, by_level in per_level.items():
        for level, entry in by_level.items():
            _assert_matches(
                f"groups.{committed['group']}.per_level.{variant}.{level}",
                entry,
                committed["per_level"][variant][level],
                DRIFT_TOL,
            )


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def build_hier_demo_payload(
    metrics: dict[str, Any],
    group_frames: dict[str, tuple[pd.DataFrame, np.ndarray, dict[str, np.ndarray], GroupSpec]],
    config: ForecastConfig,
    *,
    catalog_quotas: dict[str, dict[str, int]] | None = None,
    n_origins: int = N_ORIGINS_PER_GROUP,
) -> dict[str, Any]:
    """Assemble the hierarchy-explorer payload.

    ``metrics`` is the committed ``reports_hier/metrics.json`` content;
    ``group_frames`` supplies each group's in-memory frames (the toy-hierarchy
    tests build them directly; the CLI path loads them from ``data_hier/``).
    The scoring is re-run through ``score_hierarchy`` (the same core that
    wrote the committed metrics) and drift-guarded against them at 1e-9.
    """
    committed_groups = metrics["groups"]
    quotas_by_group = catalog_quotas or CATALOG_QUOTAS

    groups_payload: dict[str, Any] = {}
    catalog: list[dict[str, Any]] = []
    for group in committed_groups:
        committed = committed_groups[group]
        Y_df, S, tags, spec = group_frames[group]
        rerun, pooled = score_hierarchy(group, Y_df, S, tags, spec, config)
        _drift_guard(rerun, committed, pooled, tags)
        # the re-run reproduced the committed scalars: copy them verbatim
        groups_payload[group] = {
            "group": group,
            "freq": committed["freq"],
            "season_length": committed["season_length"],
            "horizon": committed["horizon"],
            "levels": committed["levels"],
            "origins": committed["origins"],
            "candidates": committed["candidates"],
            "per_level": committed["per_level"],
            "coherence": committed["coherence"],
            "headline": committed["headline"],
        }
        # the 3 most recent committed origins (the guard pinned the plan)
        origin_dates = list(committed["origins"]["dates"])[-n_origins:]
        nav = _HierarchyNav(
            S, list(Y_df["unique_id"].unique()), level_names(tags), level_members(tags)
        )
        for node in _select_catalog(Y_df, tags, quotas_by_group.get(group, {})):
            catalog.append(_catalog_entry(node, group, nav, Y_df, pooled, origin_dates, spec))
        logger.info(
            "%s: catalog nodes %s on origins %s..%s",
            group,
            [c["node"] for c in catalog if c["group"] == group],
            origin_dates[0],
            origin_dates[-1],
        )

    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "demo": DEMO_ID,
        "project": PROJECT_ID,
        "groups": groups_payload,
        "catalog": catalog,
        "evaluation_metadata": {
            "protocol": committed_groups[next(iter(committed_groups))]["protocol"],
            "origins": {
                g: {
                    "dates": committed_groups[g]["origins"]["dates"],
                    "n": committed_groups[g]["origins"]["n"],
                    "catalog_origins": committed_groups[g]["origins"]["dates"][-n_origins:],
                }
                for g in committed_groups
            },
            "candidates": list(CANDIDATES),
            "curve_variants": list(CURVE_VARIANTS),
            "source": METRICS_SOURCE,
        },
    }


def write_hier_demo_payload(
    data_dir: Path,
    reports_dir: Path,
    metrics_path: Path,
    config: ForecastConfig,
) -> Path:
    """Build the hierarchy-explorer payload and persist it under ``reports/``.

    Re-runs the hierarchical scoring for both benchmark groups (minutes, not
    seconds — the same cost as the committed run), drift-guards the re-run
    against the committed ``reports_hier/metrics.json``, and writes
    ``reports/hier_demo_payload.json``.
    """
    metrics = json.loads(Path(metrics_path).read_text())
    group_frames = {group: load_group_frames(data_dir, group) for group in metrics["groups"]}
    payload = build_hier_demo_payload(metrics, group_frames, config)
    out = Path(reports_dir) / PAYLOAD_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_json_safe(payload), indent=2)
    out.write_text(text + "\n")
    logger.info(
        "hierarchy-explorer payload: %d catalog nodes -> %s (%d bytes)",
        len(payload["catalog"]),
        out,
        len(text.encode()),
    )
    return out
