"""Seedable synthetic data generators — offline/CI fallbacks for every project."""

import hashlib
from typing import Any

import numpy as np
import polars as pl


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def retail_hierarchy(
    seed: int = 42, n_days: int = 730, n_stores: int = 4, n_products: int = 6
) -> pl.DataFrame:
    """Daily sales for a store-by-product hierarchy with trend and weekly seasonality."""
    r = _rng(seed)
    dates = np.datetime64("2023-01-01") + np.arange(n_days).astype("timedelta64[D]")
    dow = (dates.astype("datetime64[D]").view("int64") - 4) % 7  # 2023-01-01 was a Sunday
    rows: dict[str, list[Any]] = {"date": [], "store": [], "product": [], "units": [], "price": []}
    for s in range(n_stores):
        store_base = 20 + 8 * s
        trend = np.linspace(0, 3 + s, n_days)
        for p in range(n_products):
            base = store_base * (1 + 0.35 * p)
            price = float(np.round(r.uniform(5, 50), 2))
            weekly = 1 + 0.25 * np.sin(2 * np.pi * dow / 7)
            noise = r.normal(0, 0.12, n_days)
            units = (
                np.maximum(0, base * (1 + trend / 10) * weekly * (1 + noise)).round().astype(int)
            )
            rows["date"].extend(dates.astype(str).tolist())
            rows["store"].extend([f"store_{s}"] * n_days)
            rows["product"].extend([f"product_{p}"] * n_days)
            rows["units"].extend(units.tolist())
            rows["price"].extend([price] * n_days)
    return pl.DataFrame(rows)


def telemetry(seed: int = 42, n: int = 5_000, anomaly_rate: float = 0.02) -> pl.DataFrame:
    """Multivariate telemetry with injected contextual anomalies."""
    if not 0 < anomaly_rate < 0.5:
        raise ValueError("anomaly_rate must be in (0, 0.5)")
    r = _rng(seed)
    t = np.arange(n)
    cpu = 40 + 15 * np.sin(2 * np.pi * t / 288) + r.normal(0, 4, n)
    mem = 55 + 10 * np.sin(2 * np.pi * t / 288 + 1) + r.normal(0, 3, n)
    lat = 120 + 30 * np.sin(2 * np.pi * t / 720 + 2) + r.normal(0, 10, n)
    n_anom = int(n * anomaly_rate)
    idx = r.choice(n, n_anom, replace=False)
    cpu[idx] += r.uniform(30, 50, n_anom)
    lat[idx] *= r.uniform(2, 5, n_anom)
    return pl.DataFrame(
        {
            "ts": (np.datetime64("2024-01-01") + t.astype("timedelta64[m]")).astype(str).tolist(),
            "cpu": np.clip(cpu, 0, 100).round(2),
            "mem": np.clip(mem, 0, 100).round(2),
            "latency_ms": np.round(lat, 1),
            "is_anomaly": np.isin(t, idx),
        }
    )


def churn(seed: int = 42, n: int = 5_000) -> pl.DataFrame:
    """Messy telecom/e-commerce churn: mixed dtypes, missingness, outliers, drift."""
    r = _rng(seed)
    age = np.clip(r.normal(45, 12, n), 18, 90).round(1)
    tenure = np.clip(r.exponential(24, n), 0, 240).round(1)
    monthly_charges = np.clip(r.normal(70, 25, n), 10, 300).round(2)
    support_calls = r.poisson(1.2, n)
    contract = r.choice(["month-to-month", "one-year", "two-year"], n, p=[0.55, 0.3, 0.15])
    logit = (
        -3.5
        + 0.04 * (monthly_charges - 70)
        + 0.35 * support_calls
        - 0.03 * tenure
        + np.where(contract == "month-to-month", 1.4, 0)
        + np.where(contract == "two-year", -1.2, 0)
    )
    prob = 1 / (1 + np.exp(-logit))
    churned = r.random(n) < prob
    # deliberate messiness
    age[r.random(n) < 0.02] = np.nan
    support_calls = support_calls.astype(float)
    support_calls[r.random(n) < 0.03] = np.nan
    monthly_charges[np.argmax(monthly_charges)] = 9_999.0  # outlier
    return pl.DataFrame(
        {
            "age": age,
            "tenure_months": tenure,
            "monthly_charges": monthly_charges,
            "support_calls": support_calls,
            "contract": contract,
            "churned": churned,
        }
    )


def checksum_of_frame(df: pl.DataFrame) -> str:
    """Stable checksum of a dataframe's canonical bytes (for dataset contracts)."""
    h = hashlib.sha256()
    h.update(df.serialize())
    return h.hexdigest()
