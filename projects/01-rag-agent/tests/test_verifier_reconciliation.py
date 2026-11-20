"""Reconciliation check tests. Offline: no Ollama, no network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from verifier_reconciliation import (  # noqa: E402
    COMMITTED_FA_ALL_CLAIMS_K,
    ENTAILMENT_SYSTEM_PROMPT_FRAGMENTS,
    RECON_TOLERANCE_CLAIMS,
    agreement,
    confusion_2x2,
    rates,
)

CALIBRATE_JUDGE = PROJECT_ROOT / "scripts" / "calibrate_judge.py"
RUBRIC_CACHE = PROJECT_ROOT / "reports" / "verifier_cascade_dev" / "local_verdicts.jsonl"
ENTAILMENT_CACHE = (
    PROJECT_ROOT / "reports" / "verifier_reconciliation" / "entailment_verdicts.jsonl"
)
CLAIMS = PROJECT_ROOT / "data" / "calibration" / "claims.jsonl"


def test_entailment_system_prompt_is_verbatim_in_calibrate_judge() -> None:
    source = CALIBRATE_JUDGE.read_text(encoding="utf-8")
    for fragment in ENTAILMENT_SYSTEM_PROMPT_FRAGMENTS:
        assert fragment in source


def test_claim_prompt_importable_and_formattable() -> None:
    from calibrate_judge import CLAIM_PROMPT, ClaimVerdict

    rendered = CLAIM_PROMPT.format(question="Q", evidence="E", claim="C")
    assert "Q" in rendered and "E" in rendered and "C" in rendered
    assert "strict entailment judge" in rendered
    verdict = ClaimVerdict(supported=True, reason="because")
    assert verdict.supported is True


def _toy_verdicts() -> tuple[dict[str, dict], dict[str, dict], dict[str, str]]:
    labels = {
        "s1": "supported",
        "s2": "supported",
        "u1": "unsupported",
        "u2": "unsupported",
    }
    rubric = {
        "s1": {"judge_accepts": True},
        "s2": {"judge_accepts": False},
        "u1": {"judge_accepts": True},
        "u2": {"judge_accepts": False},
    }
    entailment = {
        "s1": {"judge_accepts": True},
        "s2": {"judge_accepts": True},
        "u1": {"judge_accepts": False},
        "u2": {"judge_accepts": False},
    }
    return rubric, entailment, labels


def test_rates_denominators() -> None:
    rubric, _, labels = _toy_verdicts()
    result = rates(rubric, labels)
    assert result["fa_all_claims"]["k"] == 1  # u1
    assert result["fa_all_claims"]["n"] == 4
    assert result["fa_strict_unsupported"]["k"] == 1
    assert result["fa_strict_unsupported"]["n"] == 2
    assert result["false_rejection_supported"]["k"] == 1  # s2
    assert result["false_rejection_supported"]["n"] == 2


def test_agreement_and_confusion() -> None:
    rubric, entailment, labels = _toy_verdicts()
    # s1 both accept (agree), s2 rubric-reject/entail-accept, u1 rubric-accept/
    # entail-reject, u2 both reject (agree) -> 2 of 4 agree.
    assert agreement(rubric, entailment) == {"k": 2, "n": 4, "share": 0.5}
    table = confusion_2x2(rubric, entailment, labels)
    assert table["supported"] == {
        "accept_accept": 1,
        "accept_reject": 0,
        "reject_accept": 1,
        "reject_reject": 0,
    }
    assert table["unsupported"] == {
        "accept_accept": 0,
        "accept_reject": 1,
        "reject_accept": 0,
        "reject_reject": 1,
    }


def test_reconciliation_constants() -> None:
    assert COMMITTED_FA_ALL_CLAIMS_K == 86
    assert RECON_TOLERANCE_CLAIMS == 1


def _require(path: Path, what: str) -> None:
    if not path.exists():
        pytest.skip(f"{what} not present in this checkout")


def test_committed_rubric_cache_pins_recorded_rates() -> None:
    _require(RUBRIC_CACHE, "cascade local_verdicts cache")
    _require(CLAIMS, "calibration claims.jsonl")
    rows = {
        row["id"]: row
        for row in (
            json.loads(line)
            for line in RUBRIC_CACHE.read_text(encoding="utf-8").splitlines()[1:]
            if line.strip()
        )
    }
    labels = {
        row["id"]: row["label"]
        for row in (
            json.loads(line)
            for line in CLAIMS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    result = rates(rows, labels)
    # pinned from collaboration/reviews/20261120-verifier-cascade-dev-report
    assert result["fa_all_claims"]["k"] == 23
    assert result["false_rejection_supported"]["k"] == 12
    header = json.loads(RUBRIC_CACHE.read_text(encoding="utf-8").splitlines()[0])
    assert header["unparseable"] == 0 and header["hosted_calls"] == 0


def test_entailment_cache_matches_committed_metrics_and_digest() -> None:
    _require(ENTAILMENT_CACHE, "reconciliation entailment_verdicts")
    _require(CLAIMS, "calibration claims.jsonl")
    metrics_path = PROJECT_ROOT / "reports" / "verifier_reconciliation" / "metrics.json"
    _require(metrics_path, "reconciliation metrics.json")
    rows = {
        row["id"]: row
        for row in (
            json.loads(line)
            for line in ENTAILMENT_CACHE.read_text(encoding="utf-8").splitlines()[1:]
            if line.strip()
        )
    }
    labels = {
        row["id"]: row["label"]
        for row in (
            json.loads(line)
            for line in CLAIMS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    result = rates(rows, labels)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    # Consistency: recomputation from the committed cache equals the committed
    # metrics, and the decision flag follows the fixed rule. The outcome is
    # whatever the run measured - the test pins consistency, not a verdict.
    assert result == metrics["entailment"]["rates"]
    reproduced = (
        abs(result["fa_all_claims"]["k"] - COMMITTED_FA_ALL_CLAIMS_K) <= RECON_TOLERANCE_CLAIMS
    )
    assert metrics["reconciliation"]["reproduced"] is reproduced
    header = json.loads(ENTAILMENT_CACHE.read_text(encoding="utf-8").splitlines()[0])
    assert header["ollama_digest"].startswith("357c53fb659c")
