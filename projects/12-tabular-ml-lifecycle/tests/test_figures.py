"""Figure smoke tests: every committed chart type builds and carries the theme."""

import pandas as pd
from tabular_ml_lifecycle import figures
from tabular_ml_lifecycle.features import FeatureSelection


def _selection() -> FeatureSelection:
    mi = {
        "temp": 0.50,
        "atemp": 0.48,
        "hum": 0.10,
        "windspeed": 0.05,
        "weathersit": 0.08,
        "hour_sin": 0.30,
        "hour_cos": 0.30,
        "weekday_sin": 0.12,
        "weekday_cos": 0.11,
        "month_sin": 0.22,
        "month_cos": 0.22,
        "holiday": 0.01,
        "workingday": 0.09,
        "cnt_lag_1h": 0.60,
        "cnt_lag_24h": 0.72,
        "cnt_lag_168h": 0.65,
    }
    return FeatureSelection(
        candidates=list(mi),
        selected=[c for c in mi if c != "atemp"],
        mi_scores=mi,
        perm_val_mae_increase={c: v / 10 for c, v in mi.items()},
        pruned_pairs=[{"dropped": "atemp", "kept": "temp", "r": 0.99}],
        windows={},
        corr_threshold=0.9,
    )


def test_eda_figures_build(small_frame: pd.DataFrame) -> None:
    builders = [
        figures.rentals_by_hour_season_figure(small_frame),
        figures.temp_vs_rentals_figure(small_frame),
        figures.correlation_heatmap_figure(small_frame),
    ]
    for fig in builders:
        assert fig.layout.template is not None or fig.layout.paper_bgcolor == "#0f172a"
        assert fig.layout.title.text


def test_training_figures_build() -> None:
    loss = figures.mlp_loss_curves_figure([50.0, 40.0, 38.0], [52.0, 45.0, 46.0], 2)
    assert len(loss.data) == 2  # train + validation lines
    curves = figures.learning_curves_figure(
        {"lightgbm_hpo": {0.5: 40.0, 1.0: 35.0}, "mlp": {0.5: 42.0, 1.0: 37.0}}
    )
    assert len(curves.data) == 2
    ablation = figures.ablation_dotplot_figure(
        [
            {
                "variant": "dropout=on|wd=on|es=on",
                "val_mae": 60.0,
                "selected": True,
            },
            {
                "variant": "dropout=off|wd=off|es=off",
                "val_mae": 75.0,
                "selected": False,
            },
        ]
    )
    assert len(ablation.data) == 2  # grey variants + teal production config


def test_evaluation_figures_build(small_frame: pd.DataFrame) -> None:
    runs = {
        "seasonal_naive": {"mae": 90.0, "rmse": 120.0, "mape": 30.0},
        "ridge": {"mae": 70.0, "rmse": 95.0, "mape": 22.0},
        "mlp": {"mae": 60.0, "rmse": 85.0, "mape": 18.0},
    }
    comparison = figures.model_comparison_figure(runs)
    assert comparison.layout.title.text
    heatmap = figures.residual_heatmap_figure(
        small_frame.iloc[: 24 * 14].copy(), pd.Series(0.0, index=range(24 * 14)).to_numpy()
    )
    assert len(heatmap.data) == 2  # season + weather panels
    rvf = figures.residual_vs_fitted_figure(
        small_frame["cnt"].to_numpy()[:100], small_frame["cnt"].to_numpy()[:100] * 0.95
    )
    assert len(rvf.data) == 1
    boot = figures.bootstrap_ci_figure(
        __import__("numpy").linspace(10, 50, 100),
        {"point": 30.0, "lo": 22.0, "hi": 38.0, "n_boot": 2000},
    )
    assert boot.layout.title.text


def test_mi_lollipop_marks_pruned_grey() -> None:
    from tabular_ml_lifecycle.features import mi_lollipop_figure

    fig = mi_lollipop_figure(_selection())
    dots = [t for t in fig.data if t.mode == "markers"]
    assert len(dots) == 1
    assert list(dots[0].marker.color).count("#64748b") == 1  # exactly the pruned member
