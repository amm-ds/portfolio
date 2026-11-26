#!/usr/bin/env python3
"""Headline-number drift check (review finding 5, next-wave W4).

Each project card quotes one or two headline numbers in its README and
story. Those numbers drift from the committed metrics files. This check
re-derives every headline number from its committed source and asserts the
declared copy surfaces still contain it, formatted the way the copy prints
it.

Exit codes:
  0 — every claim verified (or only KNOWN_DRIFT entries failed).
  1 — drift outside the KNOWN_DRIFT list (new drift: stop and triage,
      do not mass-edit copy).

Coverage note: project 04 is covered via its committed fresh-holdout
cascade record (baseline and cascade macro-F1 plus the cloud-equivalent
cost); project 01 via its committed final_v3 F1 summary and the promoted S3
retrieval sweep.

Run: uv run python scripts/check_headline_numbers.py [--check]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Entries here are drift the check KNOWS about and must not fail on.
# "uncovered:<project>" marks projects without a clean scalar claim.
KNOWN_DRIFT: set[str] = set()


def _load(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _fmt(x: float, digits: int) -> str:
    return f"{x:.{digits}f}"


def _thousands(x: float) -> str:
    return f"{x:,.0f}"


# --- per-project value extractors (committed source -> formatted strings) ---


def _m01() -> list[str]:
    f1 = _load("projects/01-rag-agent/reports/final_v3_e2e/f1_summary.json")
    s3 = _load(
        "projects/01-rag-agent/reports/retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json"
    )
    return [_fmt(f1["f1"], 4), _fmt(s3["metrics"]["recall_at_5"], 3)]


def _m02() -> list[str]:
    m = _load("projects/02-demand-forecasting/reports_m5_full/metrics.json")
    v = m["test"]["convex_ensemble"]["official_wrmsse"]
    naive = m["test"]["seasonal_naive"]["official_wrmsse"]
    red = (naive - v) / naive * 100
    return [_fmt(v, 4), f"{red:.1f}"]


def _m03() -> list[str]:
    m = _load("projects/03-anomaly-detection/reports/nab_metrics.json")
    return [
        _fmt(m["overall"]["pa_k_2"]["range_precision"], 3),
        _thousands(float(m["overall"]["alerts_fired"])),
        _fmt(m["pa_k_2_precision_interval"]["lo"], 3),
        _fmt(m["pa_k_2_precision_interval"]["hi"], 3),
    ]


def _m04() -> list[str]:
    c = _load("projects/04-nlp-classification/reports/llm_cascade.json")
    fresh = c["fresh holdout"]
    return [
        _fmt(fresh["baseline_f1_macro"], 4),
        _fmt(fresh["cascade_f1_macro"], 4),
        _fmt(c["ops"]["est_cost_usd"], 6),
    ]


def _m05() -> list[str]:
    m = _load("projects/05-ml-pipeline-churn/reports/metrics.json")
    return [
        _thousands(float(m["selected_model_calibrated"]["business_cost"])),
        _thousands(float(m["naive_majority"]["business_cost"])),
    ]


def _m06() -> list[str]:
    m = _load("projects/06-routing-optimization/reports/metrics.json")
    iv = m["intervals"]["mean_gap_pct"]
    return [_fmt(iv["point"], 2), _fmt(iv["lo"], 2), _fmt(iv["hi"], 2)]


def _m07() -> list[str]:
    m = _load("projects/07-open-data-mobility/reports/metrics.json")
    naive = m["naive_lag24"]["mae"]
    gbm = m["gbm_tuned"]["mae"]
    red = (naive - gbm) / naive * 100
    return [_fmt(gbm, 3), _fmt(naive, 3), f"{red:.1f}"]


def _m08() -> list[str]:
    m = _load("projects/08-inference-serving/reports/metrics.json")
    for cell in m["cells"]:
        if cell.get("model") == "qwen3.6:35b-a3b-q4_K_M" and cell.get("concurrency") == 1:
            return [_fmt(cell["agg_tok_per_s"], 1)]
    raise KeyError("q4_K_M c1 cell not found")


def _m09() -> list[str]:
    m = _load("projects/09-agentic-workflows/reports/metrics.json")
    t = m["detail"]["pass_rate_intervals"]["answer_success"]
    h = m["detail"]["heldout"]["pass_rate_intervals"]["answer_success"]
    return [f"{t['passed']}/{t['n']}", f"{h['passed']}/{h['n']}"]


_M10_PAIRED_CI = re.compile(
    r"<li>vs <b>(?P<arm>random|mail-everyone)</b>[^<]*?paired profit difference CI "
    r"\[(?P<lo>\u2212?\$[\d,]+), (?P<hi>\u2212?\$[\d,]+)\]"
)


def _signed_money(text: str) -> str:
    """Report form ``$718`` / minus-sign ``$5,808`` -> copy form ``+$718`` / unchanged."""
    return text if text.startswith("\u2212") else f"+{text}"


def _m10() -> list[str]:
    m = _load("projects/10-uplift-experimentation/reports/metrics.json")
    delta = m["t_learner"]["profit_delta_vs_random"]
    contract = _load("projects/10-uplift-experimentation/data/dataset_contract.json")
    # The paired T-learner-minus-baseline intervals are persisted in the
    # committed report.html only (the metrics `_meta.ci` block was replaced by
    # the provenance stamp), so the gate reads them from the report.
    report = (ROOT / "projects/10-uplift-experimentation/reports/report.html").read_text(
        encoding="utf-8"
    )
    intervals = {match["arm"]: match for match in _M10_PAIRED_CI.finditer(report)}
    if set(intervals) != {"random", "mail-everyone"}:
        raise ValueError("report.html is missing a paired T-learner baseline interval")
    values = [_thousands(delta), f"{contract['n_rows']:,}"]
    for arm in ("random", "mail-everyone"):
        values += [_signed_money(intervals[arm]["lo"]), _signed_money(intervals[arm]["hi"])]
    return values


def _m11() -> list[str]:
    m = _load("projects/11-data-engineering/reports/metrics.json")
    be = m["summary"]["by_engine"]
    # README prints the multiplication sign U+00D7; build it via escape so
    # RUF001 (ambiguous character) stays quiet — the copy really uses U+00D7.
    times = "\u00d7"
    return [
        f"{times}{be['polars']['geomean_speedup_vs_pandas']:.1f}",
        f"{times}{be['duckdb']['geomean_speedup_vs_pandas']:.1f}",
    ]


def _m12() -> list[str]:
    m = _load("projects/12-tabular-ml-lifecycle/reports/metrics.json")
    point = m["validation_tie_interval"]["point"]
    minus = chr(0x2212) if point < 0 else ""
    return [_fmt(m["mlp"]["mae"], 1), f"{minus}{abs(point):.2f}"]


def _m13() -> list[str]:
    m = _load("projects/13-model-serving/reports/metrics.json")
    p50_ms = m["serving"]["native"]["concurrency"]["c1"]["p50_s"] * 1000
    return [f"{p50_ms:.1f}"]


def _m15() -> list[str]:
    m = _load("projects/15-dynamic-pricing-rl/reports/metrics.json")
    return [
        _fmt(m["test"]["policies"]["RL"]["mean_normalised_profit"], 4),
        _fmt(m["primary"]["relative_lift_pct"], 2),
    ]


CLAIMS: list[dict[str, Any]] = [
    {
        "project": "15-dynamic-pricing-rl",
        "label": "sealed RL mean + relative lift versus B1",
        "values": _m15,
        "surfaces": ["README.md", "story.yaml"],
    },
    {
        "project": "01-rag-agent",
        "label": "final_v3 F1 + promoted S3 recall@5",
        "values": _m01,
        "surfaces": ["README.md", "story.yaml"],
    },
    {
        "project": "02-demand-forecasting",
        "label": "headline WRMSSE + reduction",
        "values": _m02,
        "surfaces": ["README.md", "story.yaml"],
    },
    {
        "project": "03-anomaly-detection",
        "label": "2%-budget precision + CI + raw alerts",
        "values": _m03,
        "surfaces": ["README.md", "story.yaml"],
    },
    {
        "project": "04-nlp-classification",
        "label": "fresh macro-F1 baseline -> cascade + cascade cost",
        "values": _m04,
        "surfaces": ["README.md", "story.yaml"],
    },
    {
        "project": "05-ml-pipeline-churn",
        "label": "served cost + contact-everyone cost",
        "values": _m05,
        "surfaces": ["README.md", "story.yaml"],
    },
    {
        "project": "06-routing-optimization",
        "label": "mean gap + bootstrap CI",
        "values": _m06,
        "surfaces": ["README.md", "story.yaml"],
    },
    {
        "project": "07-open-data-mobility",
        "label": "served/naive MAE + reduction",
        "values": _m07,
        "surfaces": ["README.md", "story.yaml"],
    },
    {
        "project": "08-inference-serving",
        "label": "q4_K_M aggregate tok/s (cost basis)",
        "values": _m08,
        "surfaces": ["README.md"],
    },
    {
        "project": "09-agentic-workflows",
        "label": "tuning + held-out answer counts",
        "values": _m09,
        "surfaces": ["README.md", "story.yaml"],
    },
    {
        "project": "10-uplift-experimentation",
        "label": "delta vs random + two-arm size + paired baseline CIs (report.html)",
        "values": _m10,
        "surfaces": ["README.md", "story.yaml"],
    },
    {
        "project": "11-data-engineering",
        "label": "geomean speedups",
        "values": _m11,
        "surfaces": ["README.md"],
    },
    {
        "project": "12-tabular-ml-lifecycle",
        "label": "served MAE + tie point",
        "values": _m12,
        "surfaces": ["README.md", "story.yaml"],
    },
    {
        "project": "13-model-serving",
        "label": "single-request p50 (ms)",
        "values": _m13,
        "surfaces": ["README.md", "story.yaml"],
    },
]


def check_claim(claim: dict[str, Any]) -> list[str]:
    """Return failure descriptions (empty = verified)."""
    project = claim["project"]
    failures: list[str] = []
    try:
        expected = claim["values"]()
    except Exception as exc:
        return [f"{project}: could not derive headline from metrics: {exc}"]
    for surface in claim["surfaces"]:
        path = ROOT / "projects" / project / surface
        if not path.exists():
            failures.append(f"{project}/{surface}: surface missing")
            continue
        text = path.read_text(encoding="utf-8")
        for value in expected:
            if value not in text:
                failures.append(f"{project}/{surface}: headline {value!r} not found")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 on drift outside KNOWN_DRIFT (CI mode); default prints a report",
    )
    parser.parse_args()

    all_failures: list[str] = []
    for claim in CLAIMS:
        all_failures.extend(check_claim(claim))

    new_drift = [f for f in all_failures if not _is_known(f)]
    known = [f for f in all_failures if _is_known(f)]

    print(f"headline-numbers: {len(CLAIMS)} claims checked, {len(all_failures)} finding(s)")
    for failure in all_failures:
        tag = "known" if _is_known(failure) else "NEW"
        print(f"  [{tag}] {failure}")
    if known:
        print(f"known drift entries: {len(known)} (see KNOWN_DRIFT in the script)")
    if new_drift:
        print(f"headline-numbers: {len(new_drift)} NEW drift finding(s)")
        return 1
    print("headline-numbers: OK (no unknown drift)")
    return 0


def _is_known(failure: str) -> bool:
    for entry in KNOWN_DRIFT:
        if entry.startswith("uncovered:") and failure.startswith(f"{entry.split(':', 1)[1]}:"):
            return True
    return False


if __name__ == "__main__":
    sys.exit(main())
