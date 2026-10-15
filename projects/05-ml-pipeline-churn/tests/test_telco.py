"""Telco real-data track: loader mapping, DQ gates, slice-report correctness (offline)."""

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from churn_pipeline.cli import evaluate_core, load_telco_frame, prepare_core, train_core
from churn_pipeline.config import ChurnConfig
from churn_pipeline.evaluate import cost_surface_figure, slice_report
from sklearn.metrics import recall_score

TELCO_HEADER = (
    "customerID,gender,SeniorCitizen,Partner,Dependents,tenure,PhoneService,MultipleLines,"
    "InternetService,OnlineSecurity,OnlineBackup,DeviceProtection,TechSupport,StreamingTV,"
    "StreamingMovies,Contract,PaperlessBilling,PaymentMethod,MonthlyCharges,TotalCharges,Churn"
)


def _telco_csv(tmp_path: Path, n: int = 60) -> Path:
    """Deterministic inline telco fixture (no network)."""
    rng = np.random.default_rng(3)
    genders = rng.choice(["Female", "Male"], n)
    seniors = rng.choice(["0", "1"], n)
    contracts = rng.choice(["Month-to-month", "One year", "Two year"], n, p=[0.55, 0.3, 0.15])
    tenure = rng.integers(0, 72, n)
    charges = np.round(rng.uniform(20, 150, n), 2)
    p_churn = np.where(contracts == "Month-to-month", 0.45, 0.08) + 0.15 * (seniors == "1")
    churn = rng.random(n) < p_churn
    rows = [
        f"ID-{i},{genders[i]},{seniors[i]},Yes,No,{tenure[i]},Yes,No,DSL,No,No,No,No,No,No,"
        f"{contracts[i]},Yes,Electronic check,{charges[i]},{charges[i] * tenure[i]:.2f},"
        f"{'Yes' if churn[i] else 'No'}"
        for i in range(n)
    ]
    # a blank TotalCharges row exercises the tolerant parse
    rows[0] = rows[0].rsplit(",", 2)[0] + ",,Yes"
    path = tmp_path / "telco_fixture.csv"
    path.write_text(TELCO_HEADER + "\n" + "\n".join(rows) + "\n")
    return path


def test_load_telco_frame_maps_schema(tmp_path: Path) -> None:
    csv = _telco_csv(tmp_path)
    df = load_telco_frame(str(csv))
    assert df.height == 60
    assert df.columns == [
        "tenure_months",
        "monthly_charges",
        "contract",
        "internet_service",
        "gender",
        "senior_citizen",
        "churned",
    ]
    assert set(df["contract"].unique().to_list()) <= {"month-to-month", "one-year", "two-year"}
    assert df["churned"].dtype == pl.Boolean
    assert set(df["senior_citizen"].unique().to_list()) <= {"yes", "no"}
    assert df["monthly_charges"].null_count() == 0  # blank TotalCharges didn't leak


def test_load_telco_frame_rejects_wrong_columns(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="missing required columns"):
        load_telco_frame(str(bad))


def test_telco_end_to_end_offline(small_telco_cfg: ChurnConfig, tmp_path: Path) -> None:
    csv = _telco_csv(tmp_path, n=300)
    cfg = small_telco_cfg.model_copy(update={"telco_source": str(csv), "telco_sha256": ""})
    params = tmp_path / "params.yaml"
    params.write_text("model_family: auto\nhpo_trials: 6\n")

    prepare_core(cfg)
    train_core(cfg, params_file=params)
    evaluate_core(cfg)

    df = pl.read_parquet(cfg.data_dir / "churn.parquet")
    assert df.height == 300
    contract = json.loads((cfg.data_dir / "dataset_contract.json").read_text())
    assert contract["name"] == "churn_telco"

    metrics = json.loads((cfg.reports_dir / "metrics.json").read_text())
    assert "slices" in metrics["_meta"]
    slices = metrics["_meta"]["slices"]
    assert "overall" in slices and any(k.startswith("gender=") for k in slices)
    assert (cfg.reports_dir / "figures" / "fairness_slices.json").exists()
    assert (cfg.reports_dir / "figures" / "cost_surface.json").exists()


def test_slice_report_matches_sklearn() -> None:
    """Per-slice recall equals sklearn's recall on the masked rows."""
    cfg = ChurnConfig(data_source="telco")
    y_true = np.array([1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 1, 0])
    proba = np.array([0.9, 0.2, 0.4, 0.8, 0.1, 0.3, 0.7, 0.1, 0.6, 0.2, 0.85, 0.15])
    gender = np.array(["F", "M", "F", "M", "F", "M", "F", "M", "F", "M", "F", "M"])
    thr = 0.5
    report = slice_report(cfg, y_true, proba, thr, {"gender": gender}, min_slice_n=2)
    for value in ("F", "M"):
        mask = gender == value
        expect = recall_score(y_true[mask], (proba[mask] >= thr).astype(int))
        assert report[f"gender={value}"]["recall"] == pytest.approx(expect)
    assert report["overall"]["n"] == len(y_true)
    assert report["overall"]["business_cost"] >= 0


def test_cost_surface_marks_operating_point() -> None:
    cfg = ChurnConfig(data_source="telco")
    y_true = np.array([1, 0, 1, 1, 0, 0, 1, 0])
    proba = np.array([0.9, 0.2, 0.4, 0.8, 0.1, 0.3, 0.7, 0.15])
    fig = cost_surface_figure(cfg, y_true, proba)
    heat = next(d for d in fig.data if d.type == "heatmap")
    star = next(d for d in fig.data if getattr(d, "mode", None) == "markers")
    assert len(heat.z) == 19 and len(heat.z[0]) == len(cfg.threshold_grid)
    assert star.x[0] in cfg.threshold_grid and star.y[0] in heat.y
