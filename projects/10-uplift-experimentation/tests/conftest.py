"""Offline fixtures: a small Hillstrom-shaped slice + synthetic uplift data."""

import numpy as np
import pandas as pd
import polars as pl
import pytest


@pytest.fixture
def hillstrom_like() -> pl.DataFrame:
    """A tiny three-arm frame with the raw Hillstrom vocabulary (schema checks)."""
    return pl.DataFrame(
        {
            "recency": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
            "history_segment": ["1) $0 - $100"] * 12,
            "history": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 110.0, 120.0],
            "mens": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
            "womens": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
            "zip_code": ["Surburban", "Urban", "Rural"] * 4,
            "newbie": [0, 1] * 6,
            "channel": ["Phone", "Web", "Multichannel"] * 4,
            "segment": ["Mens E-Mail", "Womens E-Mail", "No E-Mail"] * 4,
            "visit": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
            "conversion": [0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1],
            "spend": [0.0, 0.0, 25.0, 0.0, 0.0, 40.0, 0.0, 0.0, 60.0, 0.0, 0.0, 80.0],
        }
    )


@pytest.fixture
def two_arm_frame() -> pd.DataFrame:
    """Larger randomized two-arm slice with a real covariate/outcome structure."""
    rng = np.random.default_rng(0)
    n = 2_000
    treatment = rng.integers(0, 2, n)
    history = rng.gamma(shape=2.0, scale=60.0, size=n)
    log_history = np.log1p(history)
    latent = 0.02 + 0.015 * (history > 120) + 0.01 * log_history / log_history.max()
    uplift = np.where(history > 120, 0.03, 0.0)
    p = np.clip(latent + treatment * uplift, 0, 1)
    conversion = rng.binomial(1, p)
    return pd.DataFrame(
        {
            "treatment": treatment,
            "conversion": conversion,
            "visit": rng.binomial(1, np.clip(0.1 + treatment * 0.05, 0, 1)),
            "spend": conversion * rng.uniform(20, 300, n),
            "log_history": log_history,
        }
    )
