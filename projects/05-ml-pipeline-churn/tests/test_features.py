"""Unit tests for the custom transformers: shapes, caps, missing flags."""

import numpy as np
import pytest
from churn_pipeline.config import pd
from churn_pipeline.features import MissingValueIndicator, OutlierCapper
from sklearn.exceptions import NotFittedError


@pytest.fixture()
def numeric_frame() -> pd.DataFrame:
    """Two numeric columns, one clean and one with NaN + a huge outlier."""
    return pd.DataFrame(
        {
            "a": np.linspace(0.0, 100.0, 101),
            "b": np.concatenate([np.full(100, 5.0), [9_999.0]]),
        }
    )


def test_capper_fit_transform_shapes(numeric_frame: pd.DataFrame) -> None:
    capper = OutlierCapper(0.01, 0.99)
    out = capper.fit_transform(numeric_frame)
    assert out.shape == numeric_frame.shape
    assert isinstance(out, np.ndarray)


def test_capper_bounds_respected(numeric_frame: pd.DataFrame) -> None:
    capper = OutlierCapper(0.01, 0.99).fit(numeric_frame)
    out = capper.transform(numeric_frame)
    upper = capper.upper_caps_
    assert (out <= upper).all(), "no value may exceed the learned upper cap"
    assert out.max() < 100.0, "the 9_999 outlier must be clipped"
    np.testing.assert_allclose(capper.lower_caps_, np.array([1.0, 5.0]))


def test_capper_handles_nan() -> None:
    X = np.array([[1.0, np.nan], [2.0, 3.0], [3.0, 4.0], [4.0, 5.0], [5.0, 6.0]])
    capper = OutlierCapper().fit(X)
    out = capper.transform(X)
    assert np.isnan(out[:, 1]).sum() == 1, "NaNs pass through for the imputer"


def test_capper_rejects_inverted_quantiles() -> None:
    with pytest.raises(ValueError, match="quantile_low"):
        OutlierCapper(0.9, 0.1).fit(np.arange(20.0).reshape(-1, 2))


def test_indicator_appends_flags_and_passthrough(messy_frame: pd.DataFrame) -> None:
    numeric = messy_frame[["age", "monthly_charges"]].to_numpy(dtype=float)
    ind = MissingValueIndicator()
    out = ind.fit_transform(numeric)
    assert out.shape == (5, 4), "2 passthrough + 2 flag columns"
    np.testing.assert_allclose(out[:, :2], numeric), "passthrough columns unchanged"
    assert out[1, 2] == 1.0 and out[0, 2] == 0.0, "age_was_missing flag"
    assert out[2, 3] == 1.0, "monthly_charges_was_missing flag"


def test_indicator_feature_names(messy_frame: pd.DataFrame) -> None:
    ind = MissingValueIndicator().fit(messy_frame[["age", "monthly_charges"]])
    names = ind.get_feature_names_out(["age", "monthly_charges"])
    assert list(names) == [
        "age",
        "monthly_charges",
        "age_was_missing",
        "monthly_charges_was_missing",
    ]


def test_indicator_subset_columns(messy_frame: pd.DataFrame) -> None:
    numeric = messy_frame[["age", "monthly_charges"]].to_numpy(dtype=float)
    ind = MissingValueIndicator(columns=[1])
    out = ind.fit_transform(numeric)
    assert out.shape == (5, 3)
    assert out[2, 2] == 1.0, "only monthly_charges gets a flag"


def test_indicator_rejects_out_of_bounds_columns() -> None:
    with pytest.raises(ValueError, match="out of bounds"):
        MissingValueIndicator(columns=[5]).fit(np.zeros((3, 2)))


def test_not_fitted_raises() -> None:
    with pytest.raises(NotFittedError):
        OutlierCapper().transform(np.zeros((2, 2)))
    with pytest.raises(NotFittedError):
        MissingValueIndicator().transform(np.zeros((2, 2)))
