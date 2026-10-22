"""Data layer: checksum-pinned fetch, schema mapping, DQ gates, experiment frames.

Primary analysis arm: one campaign (default ``Mens E-Mail``) vs the ``No E-Mail``
control. The third arm (``Womens E-Mail``) is excluded from the primary modeling
frame and reported in EDA — a two-arm read keeps the causal estimands
unambiguous. ``load_experiment_frame_multi`` additionally retains all three
arms with per-arm assignment indicators; it backs the secondary multi-treatment
uplift read (see ``multiarm``).
"""

from datetime import date
from pathlib import Path
from typing import cast

import numpy as np
import polars as pl
from portfolio_core.io import fetch, sha256_of
from portfolio_core.logging import get_logger
from portfolio_core.schemas import DatasetContract

from uplift_experimentation.config import UpliftConfig

log = get_logger(__name__)

RAW_COLS = [
    "recency",
    "history_segment",
    "history",
    "mens",
    "womens",
    "zip_code",
    "newbie",
    "channel",
    "segment",
    "visit",
    "conversion",
    "spend",
]

SEGMENTS = ["Mens E-Mail", "Womens E-Mail", "No E-Mail"]

BINARY_FLAG_COLS = ("mens", "womens", "newbie", "visit", "conversion")


def fetch_hillstrom(cfg: UpliftConfig) -> Path:
    """Fetch the pinned CSV (idempotent: cached when the sha256 matches)."""
    dest = cfg.data_dir / "raw" / "hillstrom.csv"
    if cfg.hillstrom_source.startswith(("http://", "https://")):
        fetch(cfg.hillstrom_source, dest, expected_sha256=cfg.hillstrom_sha256 or None)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_bytes(Path(cfg.hillstrom_source).read_bytes())
        if cfg.hillstrom_sha256 and sha256_of(dest) != cfg.hillstrom_sha256.lower():
            raise ValueError(f"checksum mismatch for local source {cfg.hillstrom_source}")
    return dest


def _gate_and_select(raw: pl.DataFrame) -> pl.DataFrame:
    """Column presence + DQ gates + 0/1 flag sanity, shared by both frame builders."""
    missing = [c for c in RAW_COLS if c not in raw.columns]
    if missing:
        raise ValueError(f"hillstrom source is missing required columns: {', '.join(missing)}")
    df = raw.select(RAW_COLS)
    run_dq_gates(df)
    for col in BINARY_FLAG_COLS:
        bad = df[col].is_not_null() & ~df[col].is_in([0, 1])
        if bad.sum() > 0:
            raise ValueError(f"column {col} has non-binary values")
    return df


def load_experiment_frame(cfg: UpliftConfig, raw_path: Path | None = None) -> pl.DataFrame:
    """Load the raw CSV, gate it, and build the two-arm modeling frame.

    Adds ``treatment`` (1 = campaign arm), ``log_history`` (CUPED covariate,
    pre-period spend), keeps outcomes (visit/conversion/spend) and the
    pre-treatment covariates only. The third email arm is dropped here and
    its EDA retained in the report.
    """
    path = raw_path or fetch_hillstrom(cfg)
    # spend starts with many zero rows: polars would infer Int64 and fail on
    # the first decimal value later in the file.
    raw = pl.read_csv(path, schema_overrides={"spend": pl.Float64})
    df = _gate_and_select(raw)

    two_arm = df.filter(
        pl.col("segment").is_in([cfg.treatment_segment, cfg.control_segment])
    ).with_columns(
        (pl.col("segment") == cfg.treatment_segment).cast(pl.Int8).alias("treatment"),
        pl.col("history").log1p().alias("log_history"),
    )
    log.info(
        "load: %d rows (%s arm: %d, control: %d)",
        two_arm.height,
        cfg.treatment_segment,
        int(two_arm["treatment"].sum()),
        int((1 - two_arm["treatment"]).sum()),
    )
    return two_arm


def load_experiment_frame_multi(cfg: UpliftConfig, raw_path: Path | None = None) -> pl.DataFrame:
    """Build the three-arm frame backing the multi-treatment uplift read.

    Retains every row and adds ``treated_mens`` / ``treated_womens`` (1 =
    assigned to that campaign arm, 0 otherwise) so each arm can be scored
    against the shared ``No E-Mail`` control. The primary two-arm frame
    (``load_experiment_frame``) is unchanged.
    """
    path = raw_path or fetch_hillstrom(cfg)
    raw = pl.read_csv(path, schema_overrides={"spend": pl.Float64})
    df = _gate_and_select(raw)
    multi = df.with_columns(
        (pl.col("segment") == "Mens E-Mail").cast(pl.Int8).alias("treated_mens"),
        (pl.col("segment") == "Womens E-Mail").cast(pl.Int8).alias("treated_womens"),
        pl.col("history").log1p().alias("log_history"),
    )
    log.info(
        "load_multi: %d rows (mens: %d, womens: %d, control: %d)",
        multi.height,
        int(multi["treated_mens"].sum()),
        int(multi["treated_womens"].sum()),
        int(((multi["treated_mens"] + multi["treated_womens"]) == 0).sum()),
    )
    return multi


def run_dq_gates(df: pl.DataFrame) -> None:
    """Platform DQ gates: null rates, ranges, segment vocabulary, binary flags."""
    from portfolio_core.dq import DQReport

    report = DQReport(dataset="hillstrom_email", n_rows=df.height)
    for col in RAW_COLS:
        null_rate = float(df[col].is_null().sum()) / df.height
        report.check_null_rate(col, null_rate, 0.01)
    report.check_range("recency", *minmax(df, "recency"), 1.0, 12.0)
    report.check_range("history", *minmax(df, "history"), 0.0, 10_000.0)
    report.check_range("spend", *minmax(df, "spend"), 0.0, 10_000.0)
    segments = df["segment"].unique().to_list()
    if sorted(segments) != sorted(SEGMENTS):
        raise ValueError(f"unexpected segment vocabulary: {segments}")
    report.check_range("visit", *minmax(df, "visit"), 0.0, 1.0)
    report.check_range("conversion", *minmax(df, "conversion"), 0.0, 1.0)
    report.raise_if_failed()


def minmax(df: pl.DataFrame, col: str) -> tuple[float, float]:
    s = df[col].drop_nulls()
    if s.len() == 0:
        return float("nan"), float("nan")
    return float(cast(float, s.min())), float(cast(float, s.max()))


def segment_summary(df: pl.DataFrame) -> pl.DataFrame:
    """Per-arm sizes and outcome rates for EDA (all three arms)."""
    return (
        df.group_by("segment", maintain_order=True)
        .agg(
            pl.len().alias("n"),
            pl.col("visit").mean().alias("visit_rate"),
            pl.col("conversion").mean().alias("conversion_rate"),
            pl.col("spend").mean().alias("mean_spend"),
            pl.col("history").mean().alias("mean_history"),
            pl.col("recency").mean().alias("mean_recency"),
        )
        .sort("segment")
    )


def write_contract(cfg: UpliftConfig, df: pl.DataFrame, raw_path: Path) -> Path:
    """Persist the platform DatasetContract for the prepared frame."""
    contract = DatasetContract(
        name="hillstrom_email_mens_vs_control",
        source=cfg.hillstrom_source,
        license="MineThatData challenge data (research use; see data-registry/hillstrom.md)",
        snapshot_date=date.today(),
        checksum_sha256=sha256_of(raw_path),
        n_rows=df.height,
    )
    out = cfg.data_dir / "dataset_contract.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(contract.model_dump_json(indent=2))
    return out


def experiment_read(df: pl.DataFrame) -> dict[str, float]:
    """Naive difference-in-means read of conversion, per arm."""
    t = df.filter(pl.col("treatment") == 1)
    c = df.filter(pl.col("treatment") == 0)
    n_t, n_c = t.height, c.height
    p_t = float(cast(float, t["conversion"].mean()))
    p_c = float(cast(float, c["conversion"].mean()))
    var_t = float(np.var(t["conversion"].to_numpy(), ddof=1))
    var_c = float(np.var(c["conversion"].to_numpy(), ddof=1))
    return {
        "n_treated": n_t,
        "n_control": n_c,
        "conv_rate_treated": p_t,
        "conv_rate_control": p_c,
        "ate": p_t - p_c,
        "ate_se": float(np.sqrt(var_t / n_t + var_c / n_c)),
        "var_treated": var_t,
        "var_control": var_c,
    }
