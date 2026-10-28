"""Optuna tuning of the M5 headline-track LightGBM (wave 25; wave 27 pass).

``cli tune-m5`` runs a seeded TPE study (~25-30 trials) and writes the best
booster config to the params.yaml ``m5_lgbm`` block; ``evaluate-m5`` reads it
via :func:`demand_forecasting.m5_track.load_m5_lgbm_params`. Selection-origins
only, per the track's honesty rule — the scored-once test origins are never
read here. Wave 27: the study runs over the expanded wave-27 feature space
(the tuner attaches the panel statics exactly like the track), and the
min_child_samples/colsample_bytree ranges widen per the M5-practice research
(min_data_in_leaf x feature_fraction interplay).

Objective (fixed a priori, documented):

- **Early stopping (nested split)** — one preprocessing of the training frame
  of the LAST selection origin; the fit rows end ``TUNE_ES_DAYS`` days before
  that origin and the eval set is the trailing block of the same training
  history (teacher-forced features from actuals, all of it SELECTION data —
  leakage-free). LightGBM ``early_stopping`` on L1 picks ``best_iteration_``.
- **Objective value** — with ``n_estimators = best_iteration_``, refit
  through the track's exact mlforecast wrapper (:func:`_lgbm_forecast`, same
  feature space as the committed run) at the last ``TUNE_OBJECTIVE_ORIGINS``
  selection origins and return the pooled WAPE over those windows.

Determinism: TPESampler with a fixed seed, LightGBM ``n_jobs=1`` +
``force_row_wise`` + fixed seed (the repo's byte-identity contract), a fixed
origin order, no pruning (pruned trials would make the study order-dependent).
"""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from portfolio_core.logging import get_logger

from demand_forecasting.m5_data import (
    encode_events,
    load_m5_subset,
    rolling_origins,
    split_exogenous,
)
from demand_forecasting.m5_track import (
    HORIZON,
    LGBM_PARAM_KEYS,
    MIN_TRAIN_DAYS,
    N_ORIGINS,
    N_SELECTION_ORIGINS,
    ORIGIN_SPACING_DAYS,
    SEED,
    _actual_window,
    _attach_panel_features,
    _lgbm_forecast,
    _mlforecast_for,
)

logger = get_logger(__name__)

TUNE_N_TRIALS = 30
#: the early-stopping eval block is the trailing 56 days of the fit's training
#: history (a nested split — it ends at the last selection origin, never after).
TUNE_ES_DAYS = 56
#: LightGBM early-stopping patience (rounds without L1 improvement).
TUNE_ES_ROUNDS = 50
#: upper cap on the booster's n_estimators (the committed value is the
#: best_iteration_ the early stopping found, ≤ this cap).
TUNE_N_ESTIMATORS_CAP = 800
#: the objective pools WAPE over the last N selection origins.
TUNE_OBJECTIVE_ORIGINS = 2

_SEARCH_SPACE: dict[str, tuple[str, Any]] = {
    "learning_rate": ("log", (0.02, 0.3)),
    "num_leaves": ("int_log", (16, 512)),
    # wave 27: widened per the M5-practice research — the strong public
    # solutions lean on larger min_data_in_leaf with feature_fraction 0.5-0.9
    # (leaf-count/feature-sampling interplay), so both ranges stretch
    "min_child_samples": ("int", (5, 300)),
    "colsample_bytree": ("float", (0.4, 1.0)),
    "n_estimators": ("int", (100, TUNE_N_ESTIMATORS_CAP)),
}


def _suggest(trial: Any) -> dict[str, Any]:
    """One trial's booster params over the fixed search space."""
    params: dict[str, Any] = {}
    for key, (kind, bounds) in _SEARCH_SPACE.items():
        lo, hi = bounds
        if kind == "log":
            params[key] = float(trial.suggest_float(key, lo, hi, log=True))
        elif kind == "int_log":
            params[key] = int(trial.suggest_int(key, lo, hi, log=True))
        elif kind == "int":
            params[key] = int(trial.suggest_int(key, lo, hi))
        else:
            params[key] = float(trial.suggest_float(key, lo, hi))
    return params


def _es_model(params: dict[str, Any], seed: int) -> Any:
    """A fresh unfitted booster carrying the trial params."""
    from lightgbm import LGBMRegressor

    return LGBMRegressor(
        random_state=seed,
        verbosity=-1,
        n_jobs=1,
        force_row_wise=True,
        **params,
    )


def _early_stop_fit(
    prep: pd.DataFrame,
    model: Any,
    cutoff: pd.Timestamp,
    params: dict[str, Any],
) -> int:
    """Fit on rows ≤ cutoff with early stopping on the trailing block.

    Returns ``best_iteration_`` (≥1); when early stopping never triggers the
    cap is returned.
    """
    import lightgbm as lgb

    feature_cols = [c for c in prep.columns if c not in ("unique_id", "ds", "y")]
    fit_mask = prep["ds"] <= cutoff
    es_mask = ~fit_mask
    if fit_mask.sum() == 0 or es_mask.sum() == 0:
        raise ValueError("nested early-stopping split is empty")
    model.fit(
        prep.loc[fit_mask, feature_cols],
        prep.loc[fit_mask, "y"],
        eval_set=[(prep.loc[es_mask, feature_cols], prep.loc[es_mask, "y"])],
        eval_metric="l1",
        callbacks=[lgb.early_stopping(TUNE_ES_ROUNDS, verbose=False)],
    )
    best = getattr(model, "best_iteration_", None) or int(params["n_estimators"])
    return int(max(best, 1))


def run_m5_tune(
    data_dir: Path,
    *,
    params_path: Path | str = "params.yaml",
    n_trials: int = TUNE_N_TRIALS,
    seed: int = SEED,
) -> dict[str, Any]:
    """Run the seeded study, write the ``m5_lgbm`` block, return the block."""
    import optuna

    y_all, x_all, s_all = load_m5_subset(Path(data_dir))
    series_ids = sorted(y_all["unique_id"].unique().tolist())
    dates = np.sort(y_all["ds"].unique())
    state_of = s_all.drop_duplicates("unique_id").set_index("unique_id")["state_id"]
    x_enc = encode_events(x_all, x_all["unique_id"].map(state_of))

    origins = rolling_origins(dates, N_ORIGINS, HORIZON, MIN_TRAIN_DAYS, ORIGIN_SPACING_DAYS)
    n_sel = len(origins) - (N_ORIGINS - N_SELECTION_ORIGINS)
    selection = origins[:n_sel]
    obj_origins = selection[-TUNE_OBJECTIVE_ORIGINS:]
    last_sel_date = pd.Timestamp(dates[selection[-1]])
    cutoff = last_sel_date - pd.to_timedelta(TUNE_ES_DAYS - 1, unit="D")
    logger.info(
        "m5 tune: %d trials, objective = pooled WAPE over selection origins %s "
        "(cutoff %s, seed %d)",
        n_trials,
        [str(pd.Timestamp(dates[o]).date()) for o in obj_origins],
        cutoff.date(),
        seed,
    )

    # per-origin cached frames (trial-independent); the panel statics are
    # attached here so the tuner fits the exact wave-27 feature space
    origin_frames: dict[int, tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray]] = {}
    for o in obj_origins:
        odate = pd.Timestamp(dates[o])
        train = y_all[y_all["ds"] <= odate]
        hist_exog, future_exog = split_exogenous(x_enc, series_ids, odate, HORIZON)
        _attach_panel_features(train, hist_exog, future_exog, s_all)
        actuals = _actual_window(y_all, series_ids, odate, HORIZON)
        origin_frames[o] = (train, hist_exog, future_exog, actuals)

    # the nested early-stopping matrix: training frame of the LAST selection
    # origin merged with exog, preprocessed once (trial-independent)
    train_last = y_all[y_all["ds"] <= last_sel_date]
    hist_last, _ = split_exogenous(x_enc, series_ids, last_sel_date, HORIZON)
    _attach_panel_features(train_last, hist_last, hist_last, s_all)  # idempotent
    train_m_last = train_last.merge(hist_last, on=["unique_id", "ds"], how="left", validate="1:1")
    prep_cache: pd.DataFrame | None = None

    def _prep() -> pd.DataFrame:
        """The trial-independent early-stop matrix, built once."""
        nonlocal prep_cache
        if prep_cache is None:
            fc = _mlforecast_for(_es_model({"n_estimators": 10}, seed))
            prep_cache = fc.preprocess(
                train_m_last,
                id_col="unique_id",
                time_col="ds",
                target_col="y",
                static_features=[],
            )
            logger.info("m5 tune: early-stop matrix %s cached", prep_cache.shape)
        return prep_cache

    def _objective(trial: Any) -> float:
        params = _suggest(trial)
        best_iter = _early_stop_fit(_prep(), _es_model(params, seed), cutoff, params)
        fit_params = {k: v for k, v in params.items() if k != "n_estimators"}
        fit_params["n_estimators"] = best_iter
        abs_err = 0.0
        volume = 0.0
        for o in obj_origins:
            train, hist_exog, future_exog, actuals = origin_frames[o]
            pred = _lgbm_forecast(
                train,
                hist_exog,
                future_exog,
                seed,
                series_ids=series_ids,
                lgbm_params=fit_params,
            )
            abs_err += float(np.abs(pred - actuals).sum())
            volume += float(actuals.sum())
        value = abs_err / volume if volume > 0 else float("nan")
        logger.info(
            "m5 tune trial %d: WAPE %.4f (best_iter %d, lr %.4f, leaves %d)",
            trial.number,
            value,
            best_iter,
            params["learning_rate"],
            params["num_leaves"],
        )
        return value

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.optimize(_objective, n_trials=n_trials, show_progress_bar=False)

    best = dict(study.best_params)
    # committed n_estimators: re-derive best_iteration_ under the best params
    best_iter = _early_stop_fit(_prep(), _es_model(best, seed), cutoff, best)
    best["n_estimators"] = best_iter
    block = {k: best[k] for k in LGBM_PARAM_KEYS if k in best}
    logger.info(
        "m5 tune best: WAPE %.4f -> %s",
        study.best_value,
        {k: round(v, 6) if isinstance(v, float) else v for k, v in block.items()},
    )
    write_m5_lgbm_params(
        params_path, block, best_value=study.best_value, n_trials=len(study.trials)
    )
    return block


def write_m5_lgbm_params(
    params_path: Path | str,
    block: dict[str, Any],
    *,
    best_value: float,
    n_trials: int,
) -> None:
    """Write the ``m5_lgbm`` block into params.yaml, preserving everything else.

    Textual edit: an existing top-level ``m5_lgbm:`` block is replaced in
    place, otherwise the block is appended — comments and unrelated keys are
    untouched.
    """
    path = Path(params_path)
    text = path.read_text() if path.exists() else ""
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line == "m5_lgbm:":
            # drop the block's own auto-generated note (the contiguous run of
            # comment/blank lines directly above it, which always contains a
            # "# M5 headline-track lgbm" marker line) so a re-tune does not
            # leave an orphaned stale note behind
            k = len(out) - 1
            seen_marker = False
            while k >= 0 and (out[k].strip() == "" or out[k].lstrip().startswith("#")):
                if out[k].lstrip().startswith("# M5 headline-track lgbm"):
                    seen_marker = True
                k -= 1
            if seen_marker:
                del out[k + 1 :]
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or lines[i].strip() == ""):
                i += 1
            continue  # drop the old block
        out.append(line)
        i += 1
    while out and out[-1].strip() == "":
        out.pop()
    note = (
        f"# M5 headline-track lgbm (wave 27) — best of a seeded {n_trials}-trial "
        "Optuna TPE\n# study on the selection origins only over the wave-27 feature "
        "space (cli tune-m5;\n# nested 56-day early-stopping split, objective = pooled "
        f"WAPE over the last 2 selection origins;\n# study best {best_value:.4f}). "
        "Wave-25 predecessor (30 trials, old feature space): n_estimators 126,\n# "
        "learning_rate 0.05980272162403059, num_leaves 393, min_child_samples 197, "
        "colsample_bytree 0.5146641352420852."
    )
    rendered = "\n".join(f"{k}: {block[k]}" for k in LGBM_PARAM_KEYS if k in block)
    out.extend(["", note, "m5_lgbm:", *[f"  {ln}" for ln in rendered.splitlines()]])
    path.write_text("\n".join(out) + "\n")
    logger.info("m5 tune: m5_lgbm block -> %s", path)
