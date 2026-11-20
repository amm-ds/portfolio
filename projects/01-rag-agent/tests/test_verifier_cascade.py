"""Verifier cascade tests. Offline: no Ollama, no network, no checkpoint."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rag_agent.verifier_cascade import (
    JUDGE_ACCEPT_CUT,
    assign_folds,
    cascade_decision,
    cv_evaluate,
    fit_final_band,
    generate_grid,
    rubric_prompt,
    select_band,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPLIT = PROJECT_ROOT / "data" / "calibration" / "verifier_split.json"
FOLDS = PROJECT_ROOT / "reports" / "verifier_cascade_dev" / "folds.json"
SCORES = PROJECT_ROOT / "reports" / "verifier_challenger" / "predictions.jsonl"
CLAIMS = PROJECT_ROOT / "data" / "calibration" / "claims.jsonl"


def _require(path: Path, what: str) -> None:
    if not path.exists():
        pytest.skip(f"{what} not present in this checkout")


def _split() -> dict:
    _require(SPLIT, "verifier_split.json")
    return json.loads(SPLIT.read_text(encoding="utf-8"))


def test_decision_boundaries() -> None:
    assert cascade_decision(0.9, 0.2, 0.8) == "accept"  # s >= t_hi
    assert cascade_decision(0.8, 0.2, 0.8) == "accept"  # boundary inclusive
    assert cascade_decision(0.1, 0.2, 0.8) == "reject"  # s <= t_lo
    assert cascade_decision(0.2, 0.2, 0.8) == "reject"  # boundary inclusive
    assert cascade_decision(0.5, 0.2, 0.8) == "defer"  # strictly between


def test_decision_rejects_inverted_band() -> None:
    with pytest.raises(ValueError):
        cascade_decision(0.5, 0.8, 0.8)
    with pytest.raises(ValueError):
        cascade_decision(0.5, 0.9, 0.8)


def test_grid_from_unique_scores_enforces_t_lo_below_t_hi() -> None:
    grid = generate_grid([0.3, 0.1, 0.3, 0.9])
    assert grid == [(0.1, 0.3), (0.1, 0.9), (0.3, 0.9)]
    scores = [0.3, 0.1, 0.3, 0.9]
    assert len(grid) == len(set(scores)) * (len(set(scores)) - 1) // 2
    for t_lo, t_hi in grid:
        assert t_lo < t_hi


def test_folds_disjoint_cover_dev_and_reproduce() -> None:
    split = _split()
    _require(CLAIMS, "calibration claims.jsonl")
    labels = {
        row["id"]: row["label"]
        for row in (
            json.loads(line)
            for line in CLAIMS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    dev_by_label: dict[str, list[str]] = {}
    for claim_id in split["dev"]:
        dev_by_label.setdefault(labels[claim_id], []).append(claim_id)
    folds = assign_folds(dev_by_label, k=5, seed=42)
    assert set(folds) == set(split["dev"])
    assert len(folds) == 96
    # every label appears in every fold (stratification)
    for ids in dev_by_label.values():
        per_fold: dict[int, int] = {}
        for claim_id in ids:
            per_fold[folds[claim_id]] = per_fold.get(folds[claim_id], 0) + 1
        assert sorted(per_fold) == [0, 1, 2, 3, 4]
    # committed folds.json matches regeneration (folds frozen before scoring)
    _require(FOLDS, "folds.json")
    committed = json.loads(FOLDS.read_text(encoding="utf-8"))
    assert committed["assignments"] == {cid: folds[cid] for cid in sorted(folds)}
    assert committed["seed"] == 42 and committed["k"] == 5


def _toy_rows() -> list[dict]:
    # 4 supported, 4 unsupported; judge defers resolve as listed.
    return [
        {"id": f"c{i}", "label": lab, "score": s, "judge_accepts": j}
        for i, (lab, s, j) in enumerate(
            [
                ("supported", 0.95, True),
                ("supported", 0.85, True),
                ("supported", 0.50, False),
                ("supported", 0.10, True),
                ("unsupported", 0.90, True),
                ("unsupported", 0.60, False),
                ("unsupported", 0.40, False),
                ("unsupported", 0.05, False),
            ]
        )
    ]


def test_cv_evaluate_counts_fa_fr_and_deferred() -> None:
    rows = _toy_rows()
    folds = {row["id"]: i % 2 for i, row in enumerate(rows)}
    result = cv_evaluate((0.20, 0.90), folds=folds, dev_rows=rows)
    # decisions: 0.95 accept, 0.85 defer->accept, 0.50 defer->reject, 0.10 reject,
    #             0.90 accept, 0.60 defer->reject, 0.40 defer->reject, 0.05 reject
    assert result["fa_k"] == 1  # only 0.90 (0.85 is a supported row)
    assert result["fr_k"] == 2  # 0.50 deferred+rejected, 0.10 hard-rejected
    assert result["deferred_k"] == 4  # 0.85, 0.50, 0.60, 0.40
    assert result["fa_n"] == 4 and result["fr_n"] == 4


def test_fit_final_band_equals_single_fold_over_all_rows() -> None:
    rows = _toy_rows()
    band = (0.20, 0.90)
    fit = fit_final_band(band, rows)
    direct = cv_evaluate(band, {row["id"]: 0 for row in rows}, rows)
    for key in ("fa_k", "fr_k", "deferred_k"):
        assert fit[key] == direct[key]


def test_select_band_qualifying_and_tie_breaks() -> None:
    rows = _toy_rows()
    dev_ids = {row["id"] for row in rows}
    cv = [
        {"t_lo": 0.1, "t_hi": 0.9, "fa_rate": 0.05, "fr_rate": 0.05, "deferred_share": 0.3},
        {"t_lo": 0.2, "t_hi": 0.9, "fa_rate": 0.05, "fr_rate": 0.05, "deferred_share": 0.2},
        {"t_lo": 0.1, "t_hi": 0.8, "fa_rate": 0.05, "fr_rate": 0.05, "deferred_share": 0.2},
        {"t_lo": 0.3, "t_hi": 0.95, "fa_rate": 0.0, "fr_rate": 0.2, "deferred_share": 0.1},
    ]
    chosen = select_band(cv, dev_ids=dev_ids, row_ids=dev_ids)
    # lowest deferred among qualifying (0.2): tie between t_hi 0.9 / 0.8 -> higher t_hi
    # first? no: tie-break is lower FA (equal), then lower t_hi, then lower t_lo.
    assert (chosen["t_lo"], chosen["t_hi"]) == (0.1, 0.8)
    none = select_band([cv[3]], dev_ids=dev_ids, row_ids=dev_ids)
    assert none is None


def test_select_band_rejects_non_dev_input() -> None:
    rows = _toy_rows()
    dev_ids = {row["id"] for row in rows}
    cv = [
        {
            "t_lo": 0.1,
            "t_hi": 0.9,
            "fa_rate": 0.05,
            "fr_rate": 0.05,
            "deferred_share": 0.3,
        }
    ]
    with pytest.raises(ValueError, match="non-DEV"):
        select_band(cv, dev_ids=dev_ids, row_ids=dev_ids | {"test_claim_001"})


def test_rubric_prompt_matches_judge_shape() -> None:
    prompt = rubric_prompt("Q?", "CTX", "ANS")
    assert prompt == "Question: Q?\n\nContext:\nCTX\n\nAnswer:\nANS"


def test_judge_accept_cut_is_rubric_midpoint() -> None:
    assert JUDGE_ACCEPT_CUT == 0.5


def test_scores_file_has_all_dev_ids_with_score_and_split() -> None:
    _require(SCORES, "verifier_challenger predictions.jsonl")
    split = _split()
    rows = {
        row["id"]: row
        for row in (
            json.loads(line)
            for line in SCORES.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    for claim_id in [*split["dev"], *split["test"]]:
        assert claim_id in rows
        assert 0.0 <= rows[claim_id]["score"] <= 1.0
        assert rows[claim_id]["split"] in ("dev", "test")
