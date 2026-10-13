"""NSL-KDD production track (wave 7): real network-flow telemetry behind the
same ``DatasetContract``, as a transfer probe for the champion detector.

The official UNB page (https://www.unb.ca/cic/datasets/nsl.html) no longer
serves the files ("this dataset is no longer available"), so the pinned
mirrors below (byte-identical copies of KDDTrain+.TXT / KDDTest+.TXT) are
fetched with checksum verification via ``portfolio_core.io.fetch``.

Honest caveats, by construction:

- The NSL-KDD train/test splits are *labeled* and the test set contains
  attack categories unseen in training — this is a transfer probe, not a
  leaderboard entry.
- Feature semantics differ completely from telemetry (flow statistics vs.
  CPU/memory/latency), and prevalence is ~54-57% anomalies — not the 2%
  operating point this project tunes for.
- The three categorical KDD columns (``protocol_type``, ``service``, ``flag``)
  are factorized to integer codes purely so distance/tree detectors run;
  one-hot encoding would be the production choice.
"""

import json
from pathlib import Path
from typing import Any

import polars as pl
from portfolio_core.io import fetch
from portfolio_core.logging import get_logger
from portfolio_core.schemas import DatasetContract
from portfolio_core.synthetic import checksum_of_frame
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, roc_auc_score

from anomaly_detection.config import AnomalyConfig

logger = get_logger(__name__)

KDD_FEATURE_COLUMNS: tuple[str, ...] = (
    "duration",
    "protocol_type",
    "service",
    "flag",
    "src_bytes",
    "dst_bytes",
    "land",
    "wrong_fragment",
    "urgent",
    "hot",
    "num_failed_logins",
    "logged_in",
    "num_compromised",
    "root_shell",
    "su_attempted",
    "num_root",
    "num_file_creations",
    "num_shells",
    "num_access_files",
    "num_outbound_cmds",
    "is_host_login",
    "is_guest_login",
    "count",
    "srv_count",
    "serror_rate",
    "srv_serror_rate",
    "rerror_rate",
    "srv_rerror_rate",
    "same_srv_rate",
    "diff_srv_rate",
    "srv_diff_host_rate",
    "dst_host_count",
    "dst_host_srv_count",
    "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate",
    "dst_host_serror_rate",
    "dst_host_srv_serror_rate",
    "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate",
)
CATEGORICAL_COLUMNS: tuple[str, ...] = ("protocol_type", "service", "flag")
LABEL_COLUMN = "label"
DIFFICULTY_COLUMN = "difficulty"

KDD_SOURCES: dict[str, dict[str, str]] = {
    "train": {
        "url": "https://raw.githubusercontent.com/jmnwong/NSL-KDD-Dataset/master/KDDTrain%2B.txt",
        "sha256": "1b86d2f957b33082081bba410fe129b475efebcc13c9014c3f447c8271aadf95",
    },
    "test": {
        "url": "https://raw.githubusercontent.com/jmnwong/NSL-KDD-Dataset/master/KDDTest%2B.txt",
        "sha256": "fa46b0935342616aa83b7c2578db355b6a7aaabbc492248172c7a1e8b7ab8f84",
    },
}
NSL_LICENSE = "UNB CIC NSL-KDD: redistribution allowed with citation (Tavallaee et al., 2009)"


def parse_nsl_txt(path: Path) -> pl.DataFrame:
    """Parse a KDD*+.TXT file (43 comma-separated columns, no header)."""
    df = pl.read_csv(
        path,
        has_header=False,
        new_columns=[*KDD_FEATURE_COLUMNS, LABEL_COLUMN, DIFFICULTY_COLUMN],
        schema_overrides={c: pl.String for c in CATEGORICAL_COLUMNS},
    )
    if df.width != 43:
        raise ValueError(f"expected 43 columns, got {df.width} in {path}")
    return df


def feature_frame(df: pl.DataFrame) -> pl.DataFrame:
    """Map the 43-column KDD frame to a numeric feature matrix.

    The 38 numeric features pass through; the three categorical columns are
    factorized to integer codes (documented caveat above).
    """
    numeric = [c for c in KDD_FEATURE_COLUMNS if c not in CATEGORICAL_COLUMNS]
    out = df.select(
        *numeric,
        *[pl.col(c).cast(pl.Categorical).to_physical().alias(c) for c in CATEGORICAL_COLUMNS],
    )
    return out


def nsl_dir(config: AnomalyConfig) -> Path:
    return config.data_path / "nsl"


def load_nsl(config: AnomalyConfig) -> tuple[pl.DataFrame, pl.DataFrame, DatasetContract]:
    """Fetch (checksum-pinned), parse, and persist the NSL-KDD train/test sets."""
    directory = nsl_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    frames: dict[str, pl.DataFrame] = {}
    for split, source in KDD_SOURCES.items():
        txt = directory / f"KDD{split.title()}+.txt"
        parquet = directory / f"{split}.parquet"
        if not parquet.exists():
            if not txt.exists():
                logger.info("fetching %s", source["url"])
                fetch(source["url"], txt, expected_sha256=source["sha256"])
            df = parse_nsl_txt(txt)
            df.write_parquet(parquet)
            logger.info("parsed %s -> %s (%d rows)", txt.name, parquet, df.height)
        frames[split] = pl.read_parquet(parquet)
    contract = DatasetContract(
        name="nsl-kdd",
        source=KDD_SOURCES["train"]["url"],
        license=NSL_LICENSE,
        snapshot_date=config.snapshot_date,
        checksum_sha256=checksum_of_frame(frames["train"]),
        n_rows=frames["train"].height,
    )
    (directory / "dataset_contract.json").write_text(contract.model_dump_json(indent=2))
    return frames["train"], frames["test"], contract


def transfer_probe(config: AnomalyConfig) -> dict[str, Any]:
    """Champion-family transfer probe: IsolationForest on NSL-KDD.

    Unsupervised fit on the labeled train split (mixed normal + known
    attacks), scored on the test split against the binary label
    (normal = 0, any attack = 1).
    """
    train, test, contract = load_nsl(config)
    x_train = feature_frame(train).to_numpy()
    x_test = feature_frame(test).to_numpy()
    y_test = (test[LABEL_COLUMN] != "normal").to_numpy().astype(int)
    y_train = (train[LABEL_COLUMN] != "normal").to_numpy().astype(int)

    model = IsolationForest(
        n_estimators=config.n_estimators,
        contamination=config.contamination,
        random_state=config.seed,
        n_jobs=-1,
    )
    logger.info(
        "NSL-KDD transfer probe: fit on %d train rows, scoring %d test rows",
        x_train.shape[0],
        x_test.shape[0],
    )
    model.fit(x_train)
    scores = -model.decision_function(x_test)
    result: dict[str, Any] = {
        "dataset": contract.name,
        "n_train": int(x_train.shape[0]),
        "n_test": int(x_test.shape[0]),
        "n_features": int(x_train.shape[1]),
        "train_anomaly_rate": float(y_train.mean()),
        "test_anomaly_rate": float(y_test.mean()),
        "roc_auc": float(roc_auc_score(y_test, scores)),
        "pr_auc": float(average_precision_score(y_test, scores)),
        "caveats": [
            "labeled train/test transfer probe, not a leaderboard entry",
            "test attacks include categories unseen in training",
            "flow statistics, not telemetry semantics; ~57% test prevalence vs 2% operating point",
            "categorical columns factorized, not one-hot",
        ],
    }
    logger.info(
        "NSL-KDD probe: ROC-AUC=%.4f PR-AUC=%.4f (prevalence %.3f)",
        result["roc_auc"],
        result["pr_auc"],
        result["test_anomaly_rate"],
    )
    return result


def run_nsl_probe(config: AnomalyConfig) -> dict[str, Any]:
    """NSL stage: run and persist ``reports/nsl_probe.json``."""
    result = transfer_probe(config)
    out = config.reports_path / "nsl_probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    logger.info("wrote %s", out)
    return result
