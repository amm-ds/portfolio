"""Typer CLI: prepare → features → train → evaluate (or ``all`` in one go).

Each command is a thin orchestration layer over the library modules; dvc.yaml
stages mirror these entry points one-to-one. ``hpo`` is separate (minutes, not
seconds) and feeds the production ``hgb_tuned`` config.

``--data-source uci`` activates the real-data track; every artefact lands in
``data_uci/`` / ``reports_uci/`` so both tracks stay side by side. The
synthetic track remains the default (fully offline, CI-safe).

The ``*-m5`` / ``*-m5-full`` commands run the Walmart M5 headline track,
invoked manually or from CI (see README) — dvc.yaml does not cover them.
"""

import os

# Apple Accelerate (numpy's BLAS/LAPACK on macOS arm64) reads
# VECLIB_MAXIMUM_THREADS at library-init time and threadpoolctl cannot limit
# it (threadpool_info() is empty on this host). Accelerate's threaded BLAS
# reductions are NOT run-to-run reproducible, which makes any metric or
# report that flows through numpy/loky LAPACK byte-drift between runs — pin
# Accelerate to one thread BEFORE numpy loads so committed artefacts are
# byte-identical across runs. setdefault keeps an explicit user override.
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

from pathlib import Path
from typing import Annotated, Literal

import polars as pl
import typer
from portfolio_core.logging import get_logger

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.data import prepare
from demand_forecasting.evaluate import evaluate
from demand_forecasting.features import build_features, save_features
from demand_forecasting.model import fit_all, save_models
from demand_forecasting.probabilistic import run_probabilistic
from demand_forecasting.reconcile import reconcile_and_plot
from demand_forecasting.serving import build_serving_artifact

logger = get_logger(__name__)

app = typer.Typer(
    help="Hierarchical demand forecasting (synthetic/UCI pipeline + Walmart M5 track).",
    no_args_is_help=True,
)


def _settings_and_config(
    data_dir: Annotated[Path | None, typer.Option(help="Override data dir.")] = None,
    reports_dir: Annotated[Path | None, typer.Option(help="Override reports dir.")] = None,
    data_source: Annotated[
        Literal["synthetic", "uci"], typer.Option(help="Panel track (uci needs network once).")
    ] = "synthetic",
) -> tuple[DemandSettings, ForecastConfig]:
    base = DemandSettings()
    root = Path.cwd()
    if data_source == "uci" and data_dir is None:
        data_dir = root / "data_uci"
    if data_source == "uci" and reports_dir is None:
        reports_dir = root / "reports_uci"
    settings = DemandSettings(
        data_dir=data_dir or base.data_dir,
        reports_dir=reports_dir or base.reports_dir,
    )
    # params.yaml overlay first, then the CLI flag wins (an explicit
    # --data-source must not be clobbered by the params default)
    config = _config_from_params(ForecastConfig())
    return settings, config.model_copy(update={"data_source": data_source})


def _config_from_params(config: ForecastConfig) -> ForecastConfig:
    """Overlay params.yaml onto the config (dvc param changes are real).

    Only keys that match ForecastConfig fields are applied; unknown keys are
    ignored so the file can carry comments and per-stage extras.
    """
    import yaml  # type: ignore[import-untyped]

    path = Path("params.yaml")
    if not path.exists():
        return config
    data = yaml.safe_load(path.read_text()) or {}
    known = {k: v for k, v in data.items() if k in ForecastConfig.model_fields}
    return ForecastConfig(**known) if known else config


@app.command("prepare")
def prepare_data(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    data_source: Annotated[Literal["synthetic", "uci"], typer.Option()] = "synthetic",
) -> Path:
    """Build the panel (synthetic or UCI) and validate it through the DQ gates."""
    settings, config = _settings_and_config(data_dir, reports_dir, data_source)
    return prepare(settings, config)


@app.command()
def features(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    data_source: Annotated[Literal["synthetic", "uci"], typer.Option()] = "synthetic",
) -> Path:
    """Build leakage-safe lag + calendar features from the prepared panel."""
    settings, config = _settings_and_config(data_dir, reports_dir, data_source)
    panel = pl.read_parquet(settings.data_dir / "panel.parquet")
    frame = build_features(panel, config)
    return save_features(frame, settings)


@app.command()
def train(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    data_source: Annotated[Literal["synthetic", "uci"], typer.Option()] = "synthetic",
) -> Path:
    """Fit every model on the full history and persist them (deployment artefacts).

    Model selection is the honest time-CV backtest in ``evaluate``; this stage
    refits the chosen configuration on all available rows.
    """
    settings, config = _settings_and_config(data_dir, reports_dir, data_source)
    frame = pl.read_parquet(settings.data_dir / "features.parquet")
    models = fit_all(frame, config)
    return save_models(models, settings.data_dir / "models.pkl")


@app.command()
def hpo(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    trials: Annotated[int | None, typer.Option(help="Override trial count.")] = None,
    model: Annotated[
        Literal[
            "hgb",
            "xgb",
            "lgbm",
            "multistep_tweedie",
            "multistep_lgbm_tweedie",
            "multistep_lgbm_poisson",
        ],
        typer.Option(help="Booster arm to tune."),
    ] = "hgb",
) -> None:
    """Run seeded Optuna HPO for a production booster config (slow; not in ``all``)."""
    if model == "multistep_tweedie":
        from demand_forecasting.hpo import tune_multistep_tweedie

        settings, config = _settings_and_config(data_dir, reports_dir)
        tune_multistep_tweedie(settings, config, n_trials=trials or 12)
        return
    if model in ("multistep_lgbm_tweedie", "multistep_lgbm_poisson"):
        from demand_forecasting.hpo import tune_multistep_lgbm

        settings, config = _settings_and_config(data_dir, reports_dir)
        tune_multistep_lgbm(
            settings, config, n_trials=trials or 12, objective_name=model.rsplit("_", 1)[-1]
        )
        return
    from demand_forecasting.hpo import run_hpo

    settings, config = _settings_and_config(data_dir, reports_dir)
    run_hpo(settings, config, model=model, n_trials=trials)


@app.command("evaluate")
def evaluate_cmd(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    data_source: Annotated[Literal["synthetic", "uci"], typer.Option()] = "synthetic",
) -> None:
    """Backtest all models, reconcile, and compute probabilistic coverage."""
    settings, config = _settings_and_config(data_dir, reports_dir, data_source)
    result = evaluate(settings, config)
    reconcile_and_plot(settings, config, result)
    run_probabilistic(settings, config, multistep=result.multistep)


@app.command("build-serving")
def build_serving(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    data_source: Annotated[Literal["synthetic", "uci"], typer.Option()] = "synthetic",
) -> Path:
    """Build the showcase-API serving artifact (loads pickles; no retraining)."""
    settings, config = _settings_and_config(data_dir, reports_dir, data_source)
    return build_serving_artifact(settings, config)


@app.command()
def all(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    data_source: Annotated[Literal["synthetic", "uci"], typer.Option()] = "synthetic",
) -> None:
    """Run the full pipeline: prepare → features → train → evaluate (+extras)."""
    settings, config = _settings_and_config(data_dir, reports_dir, data_source)
    prepare(settings, config)
    panel = pl.read_parquet(settings.data_dir / "panel.parquet")
    frame = build_features(panel, config)
    save_features(frame, settings)
    save_models(fit_all(frame, config), settings.data_dir / "models.pkl")
    result = evaluate(settings, config)
    reconcile_and_plot(settings, config, result)
    run_probabilistic(settings, config, multistep=result.multistep)


@app.command("evaluate-m5")
def evaluate_m5(
    data_dir: Annotated[Path | None, typer.Option(help="M5 subset dir.")] = None,
    reports_dir: Annotated[Path | None, typer.Option(help="M5 reports dir.")] = None,
) -> None:
    """Run the M5 headline experiment (protocol m5_direct_v1) and write reports_m5/.

    Offline: reads the committed, checksum-pinned subset in data_m5/; writes
    metrics.json, probabilistic.json, evaluation_metadata.json, figures and
    report.html under reports_m5/ (minutes, not seconds — the real evaluate).
    """
    root = Path.cwd()
    data_dir = data_dir or root / "data_m5"
    reports_dir = reports_dir or root / "reports_m5"
    from demand_forecasting.m5_report import build_report
    from demand_forecasting.m5_track import run_m5_track, write_m5_artifacts

    result = run_m5_track(data_dir)
    write_m5_artifacts(result, reports_dir)
    build_report(reports_dir)


@app.command("tune-m5")
def tune_m5(
    data_dir: Annotated[Path | None, typer.Option(help="M5 subset dir.")] = None,
    params_path: Annotated[Path, typer.Option(help="params.yaml to update.")] = Path("params.yaml"),
    trials: Annotated[int, typer.Option(help="Optuna trials.")] = 30,
) -> None:
    """Tune the M5 lgbm booster (seeded Optuna TPE, selection origins only).

    Slow (tens of minutes): each trial early-stops on a nested 56-day block
    and pools WAPE over the last 2 selection origins. Writes the best params
    to the params.yaml ``m5_lgbm`` block; ``evaluate-m5`` reads them.
    """
    root = Path.cwd()
    data_dir = data_dir or root / "data_m5"
    from demand_forecasting.m5_tune import run_m5_tune

    run_m5_tune(data_dir, params_path=params_path, n_trials=trials)


@app.command("build-report-m5")
def build_report_m5(
    reports_dir: Annotated[Path | None, typer.Option(help="M5 reports dir.")] = None,
) -> Path:
    """Rebuild reports_m5/report.html (+figures) from the committed artifacts only."""
    root = Path.cwd()
    reports_dir = reports_dir or root / "reports_m5"
    from demand_forecasting.m5_report import build_report

    return build_report(reports_dir)


@app.command("demo-payload-m5")
def demo_payload_m5(
    data_dir: Annotated[Path | None, typer.Option(help="M5 subset dir.")] = None,
    reports_dir: Annotated[Path | None, typer.Option(help="M5 reports dir.")] = None,
) -> Path:
    """Build the forecast-workbench demo payload (reports_m5/demo_payload.json, schema v4).

    Recomputes the per-series catalog curves with the m5_track functions on
    the committed subset (seconds-to-minutes, NOT the full ~22-min evaluate)
    and drift-guards the per-series candidates' pooled test WAPE against the
    committed metrics block at 1e-9.
    """
    root = Path.cwd()
    data_dir = data_dir or root / "data_m5"
    reports_dir = reports_dir or root / "reports_m5"
    from demand_forecasting.m5_demo_payload import write_demo_payload

    return write_demo_payload(data_dir, reports_dir)


@app.command("evaluate-m5-full")
def evaluate_m5_full(
    data_dir: Annotated[Path | None, typer.Option(help="M5 full-panel raw dir.")] = None,
    reports_dir: Annotated[Path | None, typer.Option(help="M5 full reports dir.")] = None,
    n_origins: Annotated[int, typer.Option(help="Weekly origins (all but the last select).")] = 10,
    series_cap: Annotated[
        int | None, typer.Option(help="Ladder fallback: top items x all 10 stores.")
    ] = None,
    pooled_strategy: Annotated[
        Literal["direct", "recursive"],
        typer.Option(
            help="direct = one fit per (group, horizon); recursive = mlforecast per group."
        ),
    ] = "direct",
    n_estimators: Annotated[
        int | None, typer.Option(help="Smoke override for every lgbm arm.")
    ] = None,
    n_jobs_ets: Annotated[int, typer.Option(help="auto_ets worker processes.")] = 1,
    catalog_dump: Annotated[
        Path | None,
        typer.Option(
            help="Wave-32 catalog mode: fit every candidate at the test origin only, "
            "blend with the committed ensemble weights and write the catalog "
            "parquet + catalog_meta.json at this path."
        ),
    ] = None,
    catalog_size: Annotated[
        int,
        typer.Option(help="Catalog series count (top-units half + hardest-intermittency half)."),
    ] = 48,
) -> None:
    """Run the M5 full-panel experiment (protocol m5_full_v1), official hierarchical WRMSSE.

    Offline: reads the checksum-pinned full panel in data_m5/raw/ (Phase 0);
    writes metrics.json + evaluation_metadata.json under reports_m5_full/.
    Hours at full scale — run overnight (see the m5_full wave plan); --series-cap
    10000 selects the deterministic ladder, --pooled-strategy recursive the
    affordable pooled fits (the Phase-0 feasibility gate decides).

    --catalog-dump switches to the wave-32 catalog mode: ONLY the final (test)
    origin, at the committed configuration (--pooled-strategy is ignored there:
    the committed run was recursive; --series-cap defaults to the committed
    30490 when unset), the SAME candidate set, and the ensemble blended with
    the COMMITTED weights from reports_m5_full/metrics.json (never
    re-selected). The pooled group models still fit panel-wide at the origin.
    Expected runtime at full scale: ~2.5-3.5 h (the five lgbm arms measured
    ~80 min/origin at full scale in the committed run; batch auto_ets —
    wave-32-fixed — extrapolates to ~90 min from the 359 s / 2,000-series dry
    run; the committed 4.3 h/origin stays the conservative upper bound).
    """
    root = Path.cwd()
    data_dir = data_dir or root / "data_m5" / "raw"
    reports_dir = reports_dir or root / "reports_m5_full"
    if catalog_dump is not None:
        from demand_forecasting.m5_full_catalog import run_m5_full_catalog

        catalog_result = run_m5_full_catalog(
            data_dir,
            catalog_dump,
            metrics_path=reports_dir / "metrics.json",
            catalog_size=catalog_size,
            series_cap=series_cap if series_cap is not None else 30_490,
            pooled_strategy="recursive",  # the committed run's strategy
            n_estimators=n_estimators,
            n_jobs_ets=n_jobs_ets,
        )
        logger = get_logger(__name__)
        logger.info(
            "catalog mode done: %d series -> %s",
            catalog_result.meta["catalog_size"],
            catalog_dump,
        )
        return
    from demand_forecasting.m5_full import run_m5_full, write_m5_full_artifacts

    result = run_m5_full(
        data_dir,
        n_origins=n_origins,
        series_cap=series_cap,
        pooled_strategy=pooled_strategy,
        n_estimators=n_estimators,
        n_jobs_ets=n_jobs_ets,
    )
    write_m5_full_artifacts(result, reports_dir)


@app.command("demo-payload-m5-full")
def demo_payload_m5_full(
    data_dir: Annotated[Path | None, typer.Option(help="M5 full-panel raw dir.")] = None,
    reports_dir: Annotated[Path | None, typer.Option(help="M5 full reports dir.")] = None,
) -> Path:
    """Build the forecast-workbench demo payload for the FULL track (wave 32).

    Reads reports_m5_full/{metrics.json, catalog_forecasts.parquet,
    catalog_meta.json} (run evaluate-m5-full --catalog-dump first) and writes
    reports_m5_full/demo_payload.json — schema v4, the same keys the workbench
    reads for the subset track; fields the full metrics lack are filled from
    the catalog and marked in groups._scope.
    """
    root = Path.cwd()
    data_dir = data_dir or root / "data_m5" / "raw"
    reports_dir = reports_dir or root / "reports_m5_full"
    from demand_forecasting.m5_full_payload import write_demo_payload_full

    return write_demo_payload_full(data_dir, reports_dir)


@app.command("build-report-m5-full")
def build_report_m5_full(
    reports_dir: Annotated[Path | None, typer.Option(help="M5 full reports dir.")] = None,
) -> Path:
    """Rebuild reports_m5_full/report.html from the committed artifacts only.

    Same offline contract as build-report-m5: committed JSONs (+ the wave-32
    catalog parquet when present) in, self-contained interactive report.html
    out — no re-running anything.
    """
    root = Path.cwd()
    reports_dir = reports_dir or root / "reports_m5_full"
    from demand_forecasting.m5_full_report import build_report_full

    return build_report_full(reports_dir)


@app.command("build-figures-m5-full")
def build_figures_m5_full(
    reports_dir: Annotated[Path | None, typer.Option(help="M5 full reports dir.")] = None,
) -> Path:
    """Write reports_m5_full/figures/{html,json} from the committed artifacts only.

    The story figures (per-level WRMSSE, sample catalog series, ranked
    candidates, pooling panel) — offline, same contract as build-report-m5-full.
    """
    root = Path.cwd()
    reports_dir = reports_dir or root / "reports_m5_full"
    from demand_forecasting.m5_full_figures import build_figures_full

    return build_figures_full(reports_dir)


if __name__ == "__main__":
    app()
