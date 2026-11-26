"""Repeated-splits side analysis: artifact structure, recompute, and the core.

The committed ``reports/repeated_splits.json`` must recompute its own summary
from its per-split values; the hermetic tests run the whole flow (prepare →
train → evaluate → repeated splits) on the synthetic CI track, including the
reproduction STOP gate.
"""

import json
from pathlib import Path

import numpy as np
import pytest
from churn_pipeline.cli import evaluate_core, prepare_core, train_core
from churn_pipeline.config import ChurnConfig
from churn_pipeline.repeated_splits import (
    ReproductionMismatchError,
    repeated_splits_core,
    run_one_split,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_committed_repeated_splits_structure_and_summary_recompute() -> None:
    """The committed artifact validates against its own per-split values."""
    data = json.loads((PROJECT_ROOT / "reports" / "repeated_splits.json").read_text())
    assert data["schema_version"] == 1
    assert data["config"]["params_sha256"]
    assert data["reproduction"]["matches_committed"] is True
    committed = data["reproduction"]["committed"]
    reproduced = data["reproduction"]["reproduced"]
    assert reproduced["calibrated_opt"] == committed["calibrated_opt"]
    assert abs(reproduced["calibrated_cost"] - committed["calibrated_cost"]) <= 0.5
    assert abs(reproduced["naive_cost"] - committed["naive_cost"]) <= 0.5

    assert data["n_splits"] == 20
    assert len(data["splits"]) == len(data["seeds"]) == data["n_splits"]
    assert len(set(data["seeds"])) == data["n_splits"]
    required = {
        "seed",
        "n_train",
        "n_holdout",
        "holdout_churners",
        "calibrated_opt",
        "calibrated_cost",
        "naive_cost",
        "cost_delta",
        "month_to_month_rule",
    }
    for split in data["splits"]:
        assert required <= set(split), split["seed"]
        assert split["cost_delta"] == split["calibrated_cost"] - split["naive_cost"]
        rule = split["month_to_month_rule"]
        assert {"cost", "n_contacted", "contacted_churners", "delta_vs_contact_everyone"} <= set(
            rule
        )
        assert rule["contacted_churners"] <= rule["n_contacted"] <= split["n_holdout"]

    deltas = np.asarray([s["cost_delta"] for s in data["splits"]], dtype=float)
    summary = data["summary"]["cost_delta"]
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    assert summary["median"] == float(np.median(deltas))
    assert summary["p2_5"] == float(lo)
    assert summary["p97_5"] == float(hi)
    assert summary["min"] == float(deltas.min())
    assert summary["max"] == float(deltas.max())
    assert summary["all_below_zero"] is bool((deltas < 0).all())

    rule_costs = np.asarray([s["month_to_month_rule"]["cost"] for s in data["splits"]], dtype=float)
    rule_lo, rule_hi = np.percentile(rule_costs, [2.5, 97.5])
    rule_summary = data["summary"]["month_to_month_rule_cost"]
    assert rule_summary["median"] == float(np.median(rule_costs))
    assert rule_summary["p2_5"] == float(rule_lo)
    assert rule_summary["p97_5"] == float(rule_hi)

    thresholds = [float(s["calibrated_opt"]) for s in data["splits"]]
    opt_summary = data["summary"]["calibrated_opt"]
    assert opt_summary["median"] == float(np.median(thresholds))
    assert opt_summary["min"] == min(thresholds)
    assert opt_summary["max"] == max(thresholds)
    assert opt_summary["n_distinct"] == len(set(thresholds))


def _frozen_cfg(small_cfg: ChurnConfig) -> ChurnConfig:
    """Pin the production config so train/repeated-splits share one config."""
    return small_cfg.model_copy(
        update={"model_family": "logreg", "model_params": {"C": 0.1, "l1_ratio": 0.0}}
    )


def test_run_one_split_is_deterministic(small_cfg: ChurnConfig) -> None:
    """Same seed -> identical pricing; the split carries every required key."""
    cfg = _frozen_cfg(small_cfg)
    prepare_core(cfg)
    import polars as pl

    df = pl.read_parquet(cfg.data_dir / "churn.parquet").to_pandas()
    first = run_one_split(cfg, df, seed=11)
    second = run_one_split(cfg, df, seed=11)
    assert first == second
    assert first["cost_delta"] == first["calibrated_cost"] - first["naive_cost"]
    other = run_one_split(cfg, df, seed=12)
    assert other["seed"] == 12


def test_repeated_splits_core_end_to_end(small_cfg: ChurnConfig, params_file: Path) -> None:
    """The side analysis passes its gate, writes the JSON, adds the figure
    strip, and leaves the baseline metrics untouched."""
    cfg = _frozen_cfg(small_cfg)
    prepare_core(cfg)
    train_core(cfg, params_file=params_file)
    evaluate_core(cfg)
    metrics_before = (cfg.reports_dir / "metrics.json").read_text()

    out_path = repeated_splits_core(cfg, n_splits=3, base_seed=11, params_file=params_file)
    data = json.loads(out_path.read_text())

    assert data["n_splits"] == 3
    assert data["seeds"] == [11, 12, 13]
    assert data["reproduction"]["matches_committed"] is True
    assert data["summary"]["cost_delta"]["median"] == float(
        np.median([s["cost_delta"] for s in data["splits"]])
    )
    # the baseline artifact is untouched by the side analysis
    assert (cfg.reports_dir / "metrics.json").read_text() == metrics_before
    # the bootstrap figure gained the strip as a 4th trace
    fig = json.loads((cfg.reports_dir / "figures" / "bootstrap_ci.json").read_text())
    assert len(fig["data"]) == 4
    assert len(fig["data"][3]["x"]) == 3


def test_reproduction_gate_aborts_before_writing(small_cfg: ChurnConfig, params_file: Path) -> None:
    """A committed-number mismatch stops the run and writes nothing."""
    cfg = _frozen_cfg(small_cfg)
    prepare_core(cfg)
    train_core(cfg, params_file=params_file)
    evaluate_core(cfg)
    metrics_path = cfg.reports_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text())
    metrics["selected_model_calibrated"]["business_cost"] += 100.0
    metrics_path.write_text(json.dumps(metrics, indent=2))

    with pytest.raises(ReproductionMismatchError):
        repeated_splits_core(cfg, n_splits=2, base_seed=11, params_file=params_file)
    assert not (cfg.reports_dir / "repeated_splits.json").exists()
