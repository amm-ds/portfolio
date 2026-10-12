import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from portfolio_core.timecv import TimeSeriesCV


@given(
    st.integers(min_value=20, max_value=2000),
    st.integers(min_value=1, max_value=5),
    st.integers(min_value=0, max_value=10),
)
def test_no_leakage_between_train_and_val(n: int, n_splits: int, gap: int) -> None:
    assume = n > n_splits * (gap + 2) + gap + 2
    if not assume:
        return
    cv = TimeSeriesCV(n_splits=n_splits, gap=gap)
    for fold in cv.split(n):
        assert len(np.intersect1d(fold.train_idx, fold.val_idx)) == 0
        assert fold.train_idx.max() < fold.val_idx.min() - gap + 1
        assert fold.train_idx.max() < fold.val_idx.min()


@given(st.integers(min_value=50, max_value=500), st.integers(min_value=2, max_value=4))
def test_validation_folds_are_ordered(n: int, n_splits: int) -> None:
    cv = TimeSeriesCV(n_splits=n_splits)
    folds = list(cv.split(n))
    starts = [f.val_idx.min() for f in folds]
    assert starts == sorted(starts)
    assert len(folds) == n_splits


def test_rejects_invalid_params() -> None:
    with pytest.raises(ValueError):
        TimeSeriesCV(n_splits=0)
    with pytest.raises(ValueError):
        TimeSeriesCV(gap=-1)
    with pytest.raises(ValueError):
        list(TimeSeriesCV(n_splits=5).split(4))
