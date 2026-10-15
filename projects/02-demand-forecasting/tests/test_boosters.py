"""XGBoost / LightGBM arms: determinism, config wiring, and ladder membership."""

import numpy as np
from demand_forecasting.config import ForecastConfig
from demand_forecasting.model import model_specs


def _x_y(features, config):
    from demand_forecasting.model import to_xy

    spec = next(s for s in model_specs() if s.name == "hgb")
    return to_xy(features, config, spec)


def test_boosters_are_deterministic(features, config: ForecastConfig) -> None:
    """Same seed → bitwise-identical predictions for both boosting arms."""
    x, y, _, _ = _x_y(features, config)
    for name in ("xgb_tuned", "lgbm_tuned"):
        spec = next(s for s in model_specs() if s.name == name)
        m1 = spec.build(config).fit(x, y)
        m2 = spec.build(config).fit(x, y)
        p1, p2 = m1.predict(x), m2.predict(x)
        assert np.array_equal(p1, p2), f"{name} is not deterministic"
        assert np.isfinite(p1).all()


def test_boosters_use_tuned_config(features, config: ForecastConfig) -> None:
    """The arms are built from their production (HPO) configs."""
    x, y, _, _ = _x_y(features, config)
    xgb = next(s for s in model_specs() if s.name == "xgb_tuned").build(config)
    lgbm = next(s for s in model_specs() if s.name == "lgbm_tuned").build(config)
    assert xgb.named_steps["reg"].get_params()["max_depth"] == config.xgb_tuned.max_depth
    assert lgbm.named_steps["reg"].get_params()["num_leaves"] == config.lgbm_tuned.num_leaves
    # smoke-fit on a slice keeps the test fast
    xgb.fit(x[:400], y[:400])
    lgbm.fit(x[:400], y[:400])
    assert xgb.predict(x[:5]).shape == (5,)


def test_hpo_spaces_cover_required_params() -> None:
    """Each arm tunes exactly the documented hyperparameter set."""
    from demand_forecasting.hpo import SPACES

    assert set(SPACES["xgb"]) == {
        "learning_rate",
        "n_estimators",
        "max_depth",
        "subsample",
        "colsample_bytree",
        "reg_lambda",
    }
    assert set(SPACES["lgbm"]) == {
        "learning_rate",
        "n_estimators",
        "num_leaves",
        "min_child_samples",
        "reg_lambda",
    }
