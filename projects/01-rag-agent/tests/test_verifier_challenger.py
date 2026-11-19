"""Verifier challenger harness tests. Fully offline: no checkpoint downloads."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_judge_calibration_report import wilson_interval  # noqa: E402
from rag_agent.verifier_challenger import (  # noqa: E402
    MiniCheckAdapter,
    build_verifier_split,
    choose_threshold,
    chunk_doc,
    load_claims,
    load_verifier_split,
    sha256_file,
)
from verifier_challenger import build_dev_rows  # noqa: E402

CLAIMS = PROJECT_ROOT / "data" / "calibration" / "claims.jsonl"
SPLIT = PROJECT_ROOT / "data" / "calibration" / "verifier_split.json"


def _require_claims() -> None:
    # claims.jsonl is a regenerable local artifact (scripts/build_calibration_set.py)
    # and stays out of git per the project .gitignore; skip on fresh clones.
    if not CLAIMS.exists():
        pytest.skip("calibration claims.jsonl not present (regenerable, gitignored)")


def test_committed_split_disjoint_and_covers_all_ids() -> None:
    _require_claims()
    loaded = load_verifier_split(SPLIT)
    assignments = loaded["assignments"]
    claims = load_claims(CLAIMS)
    assert len(assignments) == len(claims) == 194
    assert set(assignments) == {row["id"] for row in claims}


def test_committed_split_stratified_counts() -> None:
    _require_claims()
    meta = load_verifier_split(SPLIT)["meta"]
    assert meta["seed"] == 42
    assert meta["source"]["n_claims"] == 194
    for label in ("supported", "unsupported"):
        assert meta["counts"][label]["dev"] + meta["counts"][label]["test"] == 97
    assert len(meta["dev"]) == sum(c["dev"] for c in meta["counts"].values())
    assert len(meta["test"]) == sum(c["test"] for c in meta["counts"].values())


def test_split_rebuild_with_seed_42_reproduces_committed_file() -> None:
    _require_claims()
    claims = load_claims(CLAIMS)
    rebuilt = build_verifier_split(claims, seed=42)
    meta = load_verifier_split(SPLIT)["meta"]
    assert rebuilt["dev"] == meta["dev"]
    assert rebuilt["test"] == meta["test"]
    assert rebuilt["counts"] == meta["counts"]


def test_recorded_claims_sha256_matches_file() -> None:
    _require_claims()
    meta = load_verifier_split(SPLIT)["meta"]
    assert meta["source"]["sha256"] == sha256_file(CLAIMS)


def test_every_evidence_text_is_a_single_chunk() -> None:
    _require_claims()
    # The chunker is a documented no-op on this data; pin that fact so a future
    # label-set change cannot silently change the scoring geometry.
    claims = load_claims(CLAIMS)
    assert all(len(chunk_doc(row["evidence"])) == 1 for row in claims)


def test_chunk_doc_packs_sentences_up_to_word_budget() -> None:
    text = "One sentence here. Two sentence here. Three sentence here. Four sentence."
    chunks = chunk_doc(text, chunk_words=6)
    assert len(chunks) == 2
    assert chunks[0] == "One sentence here. Two sentence here."
    assert chunks[1] == "Three sentence here. Four sentence."
    assert all(len(chunk.split()) <= 6 for chunk in chunks)


def test_chunk_doc_preserves_newline_blocks() -> None:
    text = "First line.\nSecond line here. Third line here."
    chunks = chunk_doc(text, chunk_words=6)
    assert chunks[0] == "First line.\nSecond line here."
    assert chunks[1] == "Third line here."


def test_chunk_doc_empty_text_yields_no_chunks() -> None:
    assert chunk_doc("") == []


def test_wilson_helper_matches_known_cases() -> None:
    assert wilson_interval(0, 10) == pytest.approx((0.0, 0.277533), abs=1e-6)
    assert wilson_interval(1, 10) == pytest.approx((0.017876, 0.404150), abs=1e-6)


def test_choose_threshold_maximizes_dev_accuracy() -> None:
    # scores 0.9 (supported), 0.8 (supported), 0.2 (unsupported), 0.1 (unsupported)
    dev = [(True, 0.9), (True, 0.8), (False, 0.2), (False, 0.1)]
    assert choose_threshold(dev) == 0.8  # accept only >= 0.8 -> 4/4 correct


def test_choose_threshold_tie_breaks_to_lower_threshold() -> None:
    # accepting >= 0.9, >= 0.8, and rejecting all each give 2/3; 0.8 is the
    # lowest maximizing threshold and must win.
    dev = [(False, 0.9), (True, 0.8), (False, 0.7)]
    assert choose_threshold(dev) == 0.8


def test_choose_threshold_can_return_reject_all() -> None:
    # reject-all scores 3/4; every accept-some threshold scores <= 2/4.
    dev = [(False, 0.9), (False, 0.8), (False, 0.7), (True, 0.1)]
    assert choose_threshold(dev) is None


def test_choose_threshold_reads_only_dev_rows() -> None:
    _require_claims()
    meta = load_verifier_split(SPLIT)["meta"]
    claims = load_claims(CLAIMS)
    by_id = {row["id"]: row for row in claims}
    scores = {row["id"]: (hash(row["id"]) % 1000) / 1000 for row in claims}
    rows = build_dev_rows(meta, by_id, scores)
    assert {cid for cid, _, _ in rows} == set(meta["dev"])
    assert len(rows) == len(meta["dev"])
    assert choose_threshold([(label, score) for _, label, score in rows]) == choose_threshold(
        [(label, score) for _, label, score in rows]
    )


def test_choose_threshold_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        choose_threshold([])


class _FakeTokenizer:
    eos_token = "</s>"  # noqa: S105 - the flan-t5 end-of-sequence marker, not a secret

    def decode(self, ids: list[int]) -> str:
        return {3: "no", 209: "yes"}[ids[0]]


class _FakeModel:
    def eval(self) -> _FakeModel:
        return self


def _probe_stub(supported: float, unsupported: float) -> MiniCheckAdapter:
    class _ProbeStub(MiniCheckAdapter):
        def __init__(self) -> None:
            self._queue = [supported, unsupported]
            super().__init__(model=_FakeModel(), tokenizer=_FakeTokenizer())

        def _support_prob(self, doc_chunk: str, claim: str) -> float:
            return self._queue.pop(0) if self._queue else supported

    return _ProbeStub()


def test_adapter_init_runs_behavioral_sanity_probe() -> None:
    adapter = _probe_stub(0.9, 0.1)
    # probe consumed both canned values; further scores fall back to the
    # supported-side value.
    assert adapter.score(claim="c", evidence="One chunk.") == 0.9


def test_adapter_init_rejects_failed_probe() -> None:
    with pytest.raises(ValueError, match="sanity probe"):
        _probe_stub(0.4, 0.4)


def test_adapter_score_is_max_support_prob_over_chunks() -> None:
    class _StubAdapter(MiniCheckAdapter):
        def __init__(self, probs: list[float], chunk_words: int) -> None:
            self._probs = probs
            self._calls = 0
            self._chunk_words = chunk_words

        def _support_prob(self, doc_chunk: str, claim: str) -> float:
            prob = self._probs[self._calls]
            self._calls += 1
            return prob

    doc = "One sentence here. Two sentence here. Three sentence here. Four sentence."
    # 6-word budget forces two chunks (see test_chunk_doc_packs_sentences).
    stub = _StubAdapter([0.2, 0.9], chunk_words=6)
    assert stub.score(claim="a claim", evidence=doc) == pytest.approx(0.9)
    assert stub._calls == 2
    single = _StubAdapter([0.4], chunk_words=500)
    assert single.score(claim="a claim", evidence="Only one chunk here.") == pytest.approx(0.4)
    for prob in (0.0, 1.0):
        assert (
            0.0
            <= _StubAdapter([prob], chunk_words=500).score(claim="c", evidence="One chunk.")
            <= 1.0
        )


def test_adapter_requires_model_and_tokenizer_together() -> None:
    with pytest.raises(ValueError):
        MiniCheckAdapter(model=_FakeModel())
    with pytest.raises(ValueError):
        MiniCheckAdapter(tokenizer=_FakeTokenizer())


def test_split_file_is_valid_json_with_required_fields() -> None:
    payload = json.loads(SPLIT.read_text(encoding="utf-8"))
    for key in ("seed", "source", "counts", "dev", "test"):
        assert key in payload
    assert payload["source"]["file"] == "claims.jsonl"
