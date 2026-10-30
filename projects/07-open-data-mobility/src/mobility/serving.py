"""Serving artifact for the showcase API (contract: SERVING.md).

``build_serving_artifact`` persists the tuned GBM pair into
``reports/models/serving/``:

- ``model.joblib`` — dict with ``gbm`` (mean), ``p90`` (quantile-0.9),
  ``feature_names`` (ordered input columns), ``target_transform`` (``None``
  here — GBMs are trained on raw counts; only the NN uses log1p).
- ``meta.json`` — feature schema, build metadata, and a worked example row
  (real zone_id + realistic feature values from the test window).
- ``zones.json`` — location_id/borough/zone reference for response enrichment.

The API (apps/showcase-api, GET/POST /projects/07-open-data-mobility/forecast)
loads exactly these three files; do not rename or reshape without updating
SERVING.md and the API in the same change.

Wave 15 (per-service retraining, the roadmap closure): the root bundle stays
the served yellow artifact, unchanged. A per-service retrained bundle —
green today — is fit by :func:`build_service_bundle` and persisted under
``serving/<service>/`` in the *identical* three-file contract, so the
showcase API's directory-parameterized loader can serve it from the
subdirectory without code changes. ``services.json`` (typed by
:class:`mobility.schemas.ServingRegistry`) indexes the bundles, and
:func:`predict_service` is the typed mobility-side reference for per-service
inference (the API mirrors it for yellow at the root path). This module stays
torch-free: the GBM factory lives in :mod:`mobility.gbm`.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import polars as pl
from portfolio_core.logging import get_logger

from mobility.config import MobilityConfig, get_config
from mobility.features import FEATURE_COLUMNS, _with_features
from mobility.gbm import _make_gbm, hpo_result
from mobility.schemas import ServiceEntry, ServiceForecast, ServingRegistry

logger = get_logger(__name__)

SERVING_DIR = "serving"
SERVICES_JSON = "services.json"
GREEN_RUN = "gbm_green_served"


def _serving_dir(cfg: MobilityConfig) -> Path:
    return cfg.models_dir / SERVING_DIR


#: Serving-arm registry: HPO kind → (run name, mean stem, p90 stem).
_ARMS: dict[str, tuple[str, str, str]] = {
    "gbm": ("gbm_tuned", "gbm_tuned", "gbm_p90_tuned"),
    "xgb": ("gbm_xgb_tuned", "gbm_xgb_tuned", "gbm_p90_xgb_tuned"),
    "lgbm": ("gbm_lgbm_tuned", "gbm_lgbm_tuned", "gbm_p90_lgbm_tuned"),
}


def select_serving_arm(cfg: MobilityConfig) -> tuple[str, str, str]:
    """Pick the served arm by validation MAE; ties keep the incumbent.

    Rule (wave 11): a challenger (xgb/lgbm) replaces ``gbm_tuned`` ONLY if its
    HPO ``best_val_mae`` on the shared embargoed validation window is strictly
    better, and its fitted artifacts exist on disk.
    """
    best: tuple[str, str, str] | None = None
    best_mae = float("inf")
    for kind, (run, stem, p90_stem) in _ARMS.items():
        result = hpo_result(cfg, kind)
        mean_ok = (cfg.models_dir / f"{stem}.joblib").exists()
        p90_ok = (cfg.models_dir / f"{p90_stem}.joblib").exists()
        if result is None or not (mean_ok and p90_ok):
            continue
        mae = float(result["best_val_mae"])
        if mae < best_mae:
            best_mae = mae
            best = (run, stem, p90_stem)
    if best is None:
        raise FileNotFoundError("no servable arm — run tune + train-baselines first")
    logger.info("serving arm: %s (val MAE %.4f)", best[0], best_mae)
    return best


def _example_row(cfg: MobilityConfig, zone_id: int) -> dict[str, float]:
    """Realistic features: the median test-window row for ``zone_id``."""
    test = pl.read_parquet(cfg.features_dir / "test.parquet")
    rows = test.filter(pl.col("zone_id") == zone_id)
    if rows.height == 0:
        raise ValueError(f"zone {zone_id} not present in the test window")
    medians = rows.select([pl.col(f).median() for f in FEATURE_COLUMNS])
    return {f: round(float(medians[f][0]), 4) for f in FEATURE_COLUMNS}


def build_serving_artifact(cfg: MobilityConfig | None = None, zone_id: int = 132) -> Path:
    """Persist the yellow bundle + per-service bundles + the services registry.

    The root three-file bundle is exactly the wave-7 contract (served yellow
    arm); the green bundle is the productionized per-service retraining fit
    (:func:`build_service_bundle`); ``services.json`` indexes both so a
    directory-parameterized loader can route by service.
    """
    cfg = cfg or get_config()
    run, stem, p90_stem = select_serving_arm(cfg)
    gbm = joblib.load(cfg.models_dir / f"{stem}.joblib")
    p90 = joblib.load(cfg.models_dir / f"{p90_stem}.joblib")

    zones = pl.read_parquet(cfg.zones_path).select(["location_id", "borough", "zone"])
    example_features = _example_row(cfg, zone_id)

    out = _serving_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    bundle: dict[str, Any] = {
        "gbm": gbm,
        "p90": p90,
        "feature_names": list(FEATURE_COLUMNS),
        # GBMs predict raw pickup counts; the log1p transform applies only
        # to TemporalNet, which is not served here.
        "target_transform": None,
    }
    joblib.dump(bundle, out / "model.joblib")

    built_at = datetime.now(UTC).isoformat()
    meta: dict[str, Any] = {
        "feature_names": list(FEATURE_COLUMNS),
        "n_features": len(FEATURE_COLUMNS),
        "built_at": built_at,
        "train_runs": [run],
        "example": {"zone_id": zone_id, "features": example_features},
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    (out / "zones.json").write_text(json.dumps(zones.to_dicts(), indent=2) + "\n")
    logger.info(
        "serving artifact (%s) -> %s (example zone %d: %s)",
        run,
        out,
        zone_id,
        {k: example_features[k] for k in list(example_features)[:4]},
    )

    green_dir = build_service_bundle(cfg, "green", zone_id=zone_id)
    registry = ServingRegistry(
        services={
            "yellow": ServiceEntry(
                dir=".", train_runs=[run], n_features=len(FEATURE_COLUMNS), built_at=built_at
            ),
            "green": ServiceEntry(
                dir="green",
                train_runs=[GREEN_RUN],
                n_features=len(FEATURE_COLUMNS),
                built_at=json.loads((green_dir / "meta.json").read_text())["built_at"],
            ),
        }
    )
    (out / SERVICES_JSON).write_text(registry.model_dump_json(indent=2) + "\n")
    logger.info("per-service bundles -> %s (%s)", green_dir, SERVICES_JSON)
    return out


def _green_feature_frame(cfg: MobilityConfig) -> pl.DataFrame:
    """All curated green months as the standard feature frame (lags + target).

    Local to this module (not imported from ``mobility.transfer``) so the
    serving build stays torch-free — transfer.py pulls ``mobility.model``.
    """
    if not cfg.green_zone_hour_demand_path.exists():
        raise FileNotFoundError(
            f"missing {cfg.green_zone_hour_demand_path} — run `mobility join` (green slice)"
        )
    return (
        _with_features(pl.scan_parquet(cfg.green_zone_hour_demand_path), cfg)
        .drop("pickup_count")  # superseded by target, mirroring build_features
        .collect(engine="streaming")
    )


def _frame_example_row(feats: pl.DataFrame, zone_id: int) -> dict[str, float]:
    """Median feature row of ``zone_id`` within a service's feature frame."""
    rows = feats.filter(pl.col("zone_id") == zone_id)
    if rows.height == 0:
        raise ValueError(f"zone {zone_id} not present in the service feature frame")
    medians = rows.select([pl.col(f).median() for f in FEATURE_COLUMNS])
    return {f: round(float(medians[f][0]), 4) for f in FEATURE_COLUMNS}


def fit_service_gbms(
    cfg: MobilityConfig,
) -> tuple[Any, Any, int, pl.DataFrame]:
    """Fit the per-service green GBM pair on green's own curated history.

    Recipe = the measured wave-14 control arm (``gbm_green_retrained``): the
    default ``gbm_mean`` family fit per-service — extended over every curated
    green month, since a served artifact trains on all available history.
    The transfer study's Jan-Feb→March control remains the honest
    out-of-sample evidence for the recipe (beats green persistence on
    MAE/RMSE/MAPE).
    """
    feats = _green_feature_frame(cfg)
    X = feats.select(FEATURE_COLUMNS).to_numpy().astype("float32")
    y = feats["target"].to_numpy().astype("float32")
    gbm = _make_gbm(cfg.gbm.model_dump(), seed=cfg.seed)
    gbm.fit(X, y)
    p90 = _make_gbm(cfg.gbm.model_dump(), seed=cfg.seed, quantile=0.9)
    p90.fit(X, y)
    logger.info("green service fit: %d zone-hours, default GBM pair", feats.height)
    return gbm, p90, feats.height, feats


def build_service_bundle(cfg: MobilityConfig, service: str, zone_id: int = 132) -> Path:
    """Fit + persist the per-service bundle under ``serving/<service>/``.

    Same three-file contract as the root (yellow) bundle (SERVING.md), so
    the showcase API's loader can serve the subdirectory unchanged.
    """
    if service != "green":
        raise ValueError(
            f"no per-service fit for {service!r}: 'yellow' is the root bundle, "
            "only 'green' has a per-service retrained fit today"
        )
    gbm, p90, n_rows, feats = fit_service_gbms(cfg)
    zones = pl.read_parquet(cfg.zones_path).select(["location_id", "borough", "zone"])
    example_features = _frame_example_row(feats, zone_id)

    out = _serving_dir(cfg) / service
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "gbm": gbm,
            "p90": p90,
            "feature_names": list(FEATURE_COLUMNS),
            "target_transform": None,
        },
        out / "model.joblib",
    )
    meta = {
        "feature_names": list(FEATURE_COLUMNS),
        "n_features": len(FEATURE_COLUMNS),
        "built_at": datetime.now(UTC).isoformat(),
        "train_runs": [GREEN_RUN],
        "example": {"zone_id": zone_id, "features": example_features},
        "service": service,
        "fit": {
            "recipe": "default GBM family per-service (gbm_mean config) + quantile-0.9 p90",
            "train_rows": n_rows,
            "evidence": "wave-14 control gbm_green_retrained (green Jan-Feb -> March)",
        },
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    (out / "zones.json").write_text(json.dumps(zones.to_dicts(), indent=2) + "\n")
    logger.info("%s bundle (%s, %d rows) -> %s", service, GREEN_RUN, n_rows, out)
    return out


def load_service_bundle(cfg: MobilityConfig | None, service: str) -> dict[str, Any]:
    """Load one service's bundle; ``yellow`` is the root bundle (back-compat)."""
    cfg = cfg or get_config()
    out = _serving_dir(cfg) if service == "yellow" else _serving_dir(cfg) / service
    if not out.exists():
        raise FileNotFoundError(
            f"no {service!r} bundle under {_serving_dir(cfg)} — run `mobility "
            "build-serving-artifact` first"
        )
    bundle = joblib.load(out / "model.joblib")
    meta = json.loads((out / "meta.json").read_text())
    zones = json.loads((out / "zones.json").read_text())
    return {"bundle": bundle, "meta": meta, "zones": zones}


def predict_service(
    cfg: MobilityConfig | None,
    service: str,
    zone_id: int,
    features: dict[str, float],
) -> ServiceForecast:
    """Typed per-service forecast — the reference the showcase API mirrors.

    Raises ``FileNotFoundError`` when the service has no bundle (the API maps
    that to 503) and ``ValueError`` on unknown zone_id or missing features
    (mapped to 422).
    """
    artifacts = load_service_bundle(cfg, service)
    bundle, meta, zones = artifacts["bundle"], artifacts["meta"], artifacts["zones"]
    zone_row = next((z for z in zones if z.get("location_id") == zone_id), None)
    if zone_row is None:
        raise ValueError(f"unknown zone_id {zone_id}")
    feature_names: list[str] = list(meta.get("feature_names") or bundle["feature_names"])
    missing = [f for f in feature_names if f not in features]
    if missing:
        raise ValueError(f"missing features: {', '.join(missing)}")

    row = np.array([[float(features[f]) for f in feature_names]])
    pred = max(0.0, float(bundle["gbm"].predict(row)[0]))
    p90 = max(0.0, float(bundle["p90"].predict(row)[0]))
    tt = bundle.get("target_transform")
    if tt == "log1p":  # contract fidelity; GBM bundles are always None
        pred = float(np.expm1(pred))
        p90 = float(np.expm1(p90))
    return ServiceForecast(
        service=service,
        zone_id=zone_id,
        borough=str(zone_row.get("borough", "?")),
        zone=str(zone_row.get("zone", "?")),
        prediction=round(pred, 3),
        p90=round(p90, 3),
    )


def load_serving_artifact(cfg: MobilityConfig | None = None) -> dict[str, Any]:
    """Round-trip loader used by tests (and mirrors the API's load path)."""
    cfg = cfg or get_config()
    out = _serving_dir(cfg)
    bundle = joblib.load(out / "model.joblib")
    meta = json.loads((out / "meta.json").read_text())
    zones = json.loads((out / "zones.json").read_text())
    return {"bundle": bundle, "meta": meta, "zones": zones}
