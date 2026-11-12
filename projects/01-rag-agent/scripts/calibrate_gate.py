"""R6 evidence-gate calibration from the tuning-set diagnostics pass.

Reads an OPEN-gate diagnostics run (``--reports-dir reports/r6-diagnostics``,
launched with ``RAG_GATE_MIN_COVERAGE=0 RAG_GATE_MIN_MAX_SIMILARITY=0
VERIFY_DIAGNOSE_MECH=true``): every tuning row generated, so each trace
carries the gate signals (coverage / max-similarity) that a closed gate
would have acted on, plus the row's final verdict.

Two decisions come out:

1. **Mechanical-checker false-rejection rate** (acceptance guardrail ≤ 10%,
   denominator = judge-confirmed supported claims — from ``detail.verify``).
2. **Gate thresholds**: sweep ``min_coverage`` x ``min_max_similarity``
   candidates; per candidate report the refusal gain (non-correct rows a
   refusal would have fixed) beside the false-abstention cost (answerable
   rows a refusal would have killed). Candidates keeping the
   false-abstention rate on answerable rows ≤ 10% are ranked by gain.

Usage (from the project root, after the diagnostics run finished):

    uv run python scripts/calibrate_gate.py [--reports-dir reports/r6-diagnostics]
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FALSE_ABSTENTION_MAX = 0.10  # absolute guardrail on answerable tuning rows


@dataclass(frozen=True)
class Candidate:
    min_coverage: float
    min_max_similarity: float


def _candidates() -> list[Candidate]:
    cov_values = [0.0, 0.1, 0.2, 0.25, 0.3, 0.34, 0.4, 0.5, 0.6]
    sim_values = [0.0, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
    return [Candidate(c, s) for c in cov_values for s in sim_values]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=Path("reports/r6-diagnostics"))
    args = parser.parse_args()

    traces = json.loads((args.reports_dir / "question_traces.json").read_text(encoding="utf-8"))
    metrics = json.loads((args.reports_dir / "metrics.json").read_text(encoding="utf-8"))
    verify = metrics["detail"]["verify"]

    # --- 1. mechanical-checker false-rejection rate ---------------------------
    supported = verify["n_judge_supported"]
    false_rej = verify["mechanical_false_rejections"]
    mech_fail = verify["n_mechanical_fail"]
    rate = (false_rej / supported) if supported else None
    print("== mechanical checker (diagnose mode, tuning set) ==")
    print(
        f"  claims drafted={verify['n_drafted']} mech_failed={mech_fail} "
        f"judge_supported={supported}"
    )
    print(
        f"  false rejections={false_rej} "
        f"false-rejection rate={rate if rate is not None else 'n/a'} "
        f"(guardrail <= {FALSE_ABSTENTION_MAX})"
    )
    print(f"  PASS={rate is not None and rate <= FALSE_ABSTENTION_MAX}")

    # --- 2. threshold sweep ----------------------------------------------------
    # A refusal "fixes" a row whose final verdict is not correct; it "kills" an
    # answerable row that would have been correct. gate_refused rows under an
    # open gate are unexpected — report them.
    rows = [
        t for t in traces if t.get("gate_coverage") is not None and not t.get("gate_refused", False)
    ]
    skipped = len(traces) - len(rows)
    answerable = [t for t in rows if t["expected_behavior"] == "answer"]
    print(f"\n== threshold sweep ({len(rows)} rows scored, {skipped} skipped) ==")
    print(f"  answerable rows: {len(answerable)}")

    results = []
    for cand in _candidates():

        def _refuses(t: dict[str, Any], c: Candidate = cand) -> bool:
            return bool(
                t["gate_coverage"] < c.min_coverage
                or t["gate_max_similarity"] < c.min_max_similarity
            )

        fixed = [t for t in rows if _refuses(t) and t["verdict"] != "correct"]
        killed = [t for t in answerable if _refuses(t) and t["verdict"] == "correct"]
        gain = len(fixed)
        false_abstain_rate = (len(killed) / len(answerable)) if answerable else 0.0
        results.append((cand, gain, len(killed), false_abstain_rate))

    feasible = [r for r in results if r[3] <= FALSE_ABSTENTION_MAX]
    feasible.sort(key=lambda r: (-r[1], r[3], r[0].min_coverage, r[0].min_max_similarity))
    print(f"  candidates within guardrail: {len(feasible)}/{len(results)}")
    print("\n  top candidates (by gain, then false-abstention):")
    for c, g, k, far in feasible[:8]:
        print(
            f"    min_coverage={c.min_coverage:.2f} "
            f"min_max_similarity={c.min_max_similarity:.2f} "
            f"gain={g} false_abstentions={k} "
            f"false_abstention_rate={far:.3f}"
        )
    if not feasible:
        print("  WARNING: no candidate meets the guardrail — gate stays conservative")

    # --- 3. the open-gate default for reference --------------------------------
    open_gain = sum(1 for t in rows if t["verdict"] != "correct")
    print(f"\n  open-gate non-correct rows (the fixable pool): {open_gain}/{len(rows)}")


if __name__ == "__main__":
    main()
