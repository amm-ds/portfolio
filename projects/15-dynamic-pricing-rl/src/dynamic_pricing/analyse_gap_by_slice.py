"""Slice the paired RL - B1 gap by elasticity tercile and stock pressure.

Grade pass 6 (option B). Reads only ``reports/test_episodes.json`` and
``reports/sealed_access.json`` (read-count guard; the log itself is never
modified). Writes the computed block into ``reports/metrics.json`` under the
top-level ``analysis`` key. Every copied number traces to this module.

Run: ``uv run python -m dynamic_pricing.analyse_gap_by_slice``
"""

import hashlib
import json
from pathlib import Path
from typing import Any, TypedDict

import numpy as np
from numpy.typing import NDArray

PROJECT = Path(__file__).resolve().parents[2]
REPORTS = PROJECT / "reports"
SEED = 42
N_RESAMPLES = 2_000


class EpisodeSlice(TypedDict):
    """One slice's paired outcome: mean gap, percentile CI, episode count."""

    mean_gap: float
    ci95: list[float]
    n: int


def _bootstrap(diff: NDArray[np.float64]) -> tuple[float, float, float, int]:
    """Percentile CI over episode-level resamples (seed 42), and the count of
    resamples whose mean is below zero (for the 'not luck' wording)."""
    rng = np.random.default_rng(SEED)
    n = diff.size
    draws = np.array([float(diff[rng.integers(0, n, size=n)].mean()) for _ in range(N_RESAMPLES)])
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return float(diff.mean()), float(lo), float(hi), int((draws < 0).sum())


def _slice(diff: NDArray[np.float64]) -> EpisodeSlice:
    mean, lo, hi, _ = _bootstrap(diff)
    return {"mean_gap": mean, "ci95": [lo, hi], "n": int(diff.size)}


def _guard_sealed_log() -> None:
    """Refuse to run if the sealed log is missing or carries > 3 reads."""
    path = REPORTS / "sealed_access.json"
    if not path.exists():
        raise SystemExit(f"sealed access log missing: {path}")
    entries = json.loads(path.read_text())
    if len(entries) > 3:
        raise SystemExit(f"sealed access log has {len(entries)} reads (> 3); refusing")


def analyse() -> dict[str, Any]:
    """Compute the slice analysis from the committed per-episode records."""
    _guard_sealed_log()
    payload = json.loads((REPORTS / "test_episodes.json").read_text())
    test = payload["sets"]["test"]
    specs = test["specs"]
    rl = np.asarray(test["policies"]["RL"]["normalised_profit"], dtype=np.float64)
    b1 = np.asarray(test["policies"]["B1"]["normalised_profit"], dtype=np.float64)
    if not (len(specs) == rl.size == b1.size and rl.size > 0):
        raise SystemExit("spec/policy length mismatch in test_episodes.json")
    epsilon = np.asarray([s["epsilon"] for s in specs], dtype=np.float64)
    rho = np.asarray([s["rho"] for s in specs], dtype=np.float64)
    diff = rl - b1  # paired RL - B1 per episode (negative = RL behind)

    sensitivity = np.abs(epsilon)
    cut_low, cut_high = np.quantile(sensitivity, [1 / 3, 2 / 3])
    terciles = {
        "low": sensitivity <= cut_low,
        "mid": (sensitivity > cut_low) & (sensitivity <= cut_high),
        "high": sensitivity > cut_high,
    }
    return {
        "by_elasticity_tercile": {name: _slice(diff[mask]) for name, mask in terciles.items()},
        "elasticity_cuts_abs_epsilon": [float(cut_low), float(cut_high)],
        "rl_win_share": float(np.mean(rl > b1)),
        "by_rho": {str(level): _slice(diff[rho == level]) for level in (0.7, 1.0, 1.3)},
        "resamples_below_zero": _bootstrap(diff)[3],
        "n_resamples": N_RESAMPLES,
        "seed": SEED,
        "n_episodes": int(diff.size),
    }


def main() -> None:
    """Compute the block and merge it into reports/metrics.json."""
    block = analyse()
    script = Path(__file__).resolve()
    analysis = {
        "gap_by_slice": {
            "source": "reports/test_episodes.json",
            "script": str(script.relative_to(PROJECT)),
            "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
            "method": (
                "per-episode paired RL \u2212 B1 normalised-profit difference; "
                "episode-unit percentile bootstrap, 2,000 resamples, seed 42"
            ),
            **block,
        }
    }
    metrics_path = REPORTS / "metrics.json"
    metrics = json.loads(metrics_path.read_text())
    # Merge, not replace: any other analysis keys are preserved.
    metrics.setdefault("analysis", {})["gap_by_slice"] = analysis["gap_by_slice"]
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(analysis, indent=2))


if __name__ == "__main__":
    main()
