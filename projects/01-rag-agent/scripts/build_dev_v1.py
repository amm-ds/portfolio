"""Build dev_v1: a seeded 20-question dev split from the tuning-65 set.

Stage 3 of the phase0-infra handoff (2026-11-22). Selects 12 single-hop,
4 multi-hop, and 4 unanswerable questions from ``src/rag_agent/eval_questions.json``
in file order, freezes the ids with a sha256 manifest, and writes a leakage
report (zero exact duplicates against sealed-120, final_v3, heldout-55).

Required report statements: 20 questions is too few for F1 decisions —
retrieval recall@5 and MRR are the decision metrics until dev reaches 65;
and dev_v1 comes from the tuning set, which chose the retrieval config, so
dev results are not clean for those choices — only final_v3 is unbiased.

    uv run python scripts/build_dev_v1.py
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TUNING = ROOT / "src" / "rag_agent" / "eval_questions.json"
SEED = 42
TARGETS = {"single_hop": 12, "multi_hop": 4, "unanswerable": 4}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    rng = random.Random(SEED)  # noqa: S311 - seeded reproducibility, not security
    tuning = json.loads(TUNING.read_text(encoding="utf-8"))
    picked: list[dict[str, Any]] = []
    ids: list[int] = []
    for category, n in TARGETS.items():
        candidates = [i for i, q in enumerate(tuning) if q["category"] == category]
        sampled = rng.sample(candidates, n)
        ids.extend(sampled)
        picked.extend(tuning[i] for i in sampled)
    if len(picked) != 20:
        raise SystemExit(f"expected 20 picks, got {len(picked)}")

    ids.sort()  # tuning-file indices are the stable ids (the set has no id field)
    tuning_sha = sha256_file(TUNING)
    manifest = {
        "source": "src/rag_agent/eval_questions.json",
        "source_sha256": tuning_sha,
        "seed": SEED,
        "counts": TARGETS,
        "ids": ids,
        "note": (
            "20 questions is too few for F1 decisions: retrieval recall@5 and "
            "MRR are the decision metrics until dev reaches 65. dev_v1 is drawn "
            "from the tuning set, which chose the retrieval config "
            "(params.yaml retrieval_best); dev results are not clean for those "
            "choices - only final_v3 gives an unbiased number."
        ),
    }
    out = ROOT / "data" / "dev_v1.sha256.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def questions(path: Path) -> list[str]:
        return [q["question"] for q in json.loads(path.read_text(encoding="utf-8"))]

    dev_questions = [q["question"] for q in picked]
    leakage = {}
    for name, path in (
        ("sealed_120", ROOT / "data/golden_sealed_v2.json"),
        ("final_v3", ROOT / "data/golden_final_v3.json"),
        ("heldout_55", ROOT / "data/golden_heldout.json"),
    ):
        existing = {q.strip().lower() for q in questions(path)} if path.exists() else set()
        dupes = [q for q in dev_questions if q.strip().lower() in existing]
        leakage[name] = {"exact_duplicates": len(dupes), "checked": path.exists()}
    report: list[str] = [
        "# dev_v1 leakage report",
        "",
        f"Source: tuning-65 (`{TUNING.relative_to(ROOT)}`), sha256 `{tuning_sha}`.",
        f"Selected ids (seed {SEED}): {ids}",
        "",
        "## Leakage (zero exact duplicates required)",
        "",
    ]
    for name, result in leakage.items():
        status = (
            "PASS"
            if result["exact_duplicates"] == 0 and result["checked"]
            else ("SKIP (set absent)" if not result["checked"] else "FAIL")
        )
        report.append(f"- {name}: {result['exact_duplicates']} exact duplicates — {status}")
    report += [
        "",
        "## Decision-metrics note",
        "",
        str(manifest["note"]),
        "",
    ]
    (ROOT / "reports" / "dev_v1_report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"ids": len(ids), "leakage": leakage}, indent=1))
    print("written: data/dev_v1.sha256.json, reports/dev_v1_report.md")


if __name__ == "__main__":
    main()
