"""Verifier challenger harness (Phase 1): MiniCheck-FT5 on the 194-claim set.

Scores the committed claim-calibration labels with one grounding-trained
verifier challenger, using a fixed dev/test split and a pre-registered gate
(see ``collaboration/designs/20261119-rag-verifier-challenger/``). Nothing in
the agent, the verify loop, copy, or headline numbers changes in this round;
the challenger is a measurement, not a production swap.

The challenger checkpoint is ``lytang/MiniCheck-Flan-T5-Large`` (MiniCheck-FT5,
770M, Tang et al., EMNLP 2024, arXiv 2404.10774, MIT license — recorded in
``reports/verifier_challenger/license.md``). The scoring recipe mirrors the
official ``minicheck`` implementation exactly:

- input  = ``"predict: " + eos.join([evidence_chunk, claim])`` tokenized with
  ``max_length=2048, truncation=True``;
- forward with ``decoder_input_ids = zeros((batch, 1))``;
- support probability = softmax over the two trained target logit ids
  ``[NO_ID, YES_ID] = [3, 209]`` (upstream constants — they are the model's
  training targets, not vocabulary words that decode to "no"/"yes"; verified
  behaviorally at load with a fixed probe pair);
- per-claim score = **max** support probability over evidence chunks;
- upstream chunking packs whole sentences up to 500 words per chunk; every
  evidence text in the calibration set is far below that limit, so each claim
  is scored as a single chunk (asserted and counted at run time). Upstream
  sentence splitting uses nltk, which is not a project dependency; because the
  chunker is a provable no-op on this data, a deterministic local sentence
  split is used instead.

Everything here is offline: no model calls beyond the local checkpoint, $0
hosted spend.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger

logger = get_logger(__name__)

CKPT = "lytang/MiniCheck-Flan-T5-Large"
# Pinned at download time (Step 0); recorded in license.md and every metrics file.
PINNED_REVISION = "96eafd01cee2d16cf81aaa2fb226b14f422a37b3"
# Upstream MiniCheck constants (minicheck/inference.py): 3 = no support, 209 = support.
# These are the model's trained target-token ids, not vocabulary words that
# decode to "no"/"yes" (the checkpoint tokenizer renders them as sentencepiece
# pieces) — so load-time verification is behavioral, via a fixed probe pair.
NO_ID = 3
YES_ID = 209
# Fixed sanity probe: (document, supported_claim, unsupported_claim). Scores on
# these are deterministic under the pinned checkpoint/revision; the adapter
# refuses to init if the ordering is wrong (e.g. a swapped or wrong checkpoint).
_PROBE_DOC = (
    "The Eiffel Tower was completed in 1889 and is located in Paris. "
    "It was designed by the engineer Gustave Eiffel."
)
_PROBE_SUPPORTED = "The Eiffel Tower is located in Paris."
_PROBE_UNSUPPORTED = "The Eiffel Tower was completed in 1900."
_PROBE_MIN_MARGIN = 0.5
CHUNK_WORDS = 500
MAX_MODEL_LEN = 2048

_SPLIT_SEED = 42
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

__all__ = [
    "CHUNK_WORDS",
    "CKPT",
    "MAX_MODEL_LEN",
    "PINNED_REVISION",
    "MiniCheckAdapter",
    "build_verifier_split",
    "choose_threshold",
    "chunk_doc",
    "load_claims",
    "load_verifier_split",
    "sha256_file",
    "write_verifier_split",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_claims(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def build_verifier_split(claims: list[dict[str, Any]], seed: int = _SPLIT_SEED) -> dict[str, Any]:
    """Stratified dev/test split by label, fixed before any scoring.

    Per label, ids are shuffled with ``random.Random(seed)``; the first
    ``len // 2`` land in dev, the rest in test. With 97 claims per label this
    gives 48 dev / 49 test per label; the counts are recorded, never adjusted.
    """
    by_label: dict[str, list[str]] = {}
    for row in claims:
        by_label.setdefault(row["label"], []).append(row["id"])
    dev: list[str] = []
    test: list[str] = []
    counts: dict[str, dict[str, int]] = {}
    for label in sorted(by_label):
        ids = sorted(by_label[label])
        random.Random(seed).shuffle(ids)  # noqa: S311 - fixed-seed split, not security
        n_dev = len(ids) // 2
        dev.extend(ids[:n_dev])
        test.extend(ids[n_dev:])
        counts[label] = {"dev": n_dev, "test": len(ids) - n_dev}
    return {"seed": seed, "counts": counts, "dev": sorted(dev), "test": sorted(test)}


def write_verifier_split(
    claims_path: Path, out_path: Path, seed: int = _SPLIT_SEED
) -> dict[str, Any]:
    claims = load_claims(claims_path)
    split = build_verifier_split(claims, seed=seed)
    payload = {
        "seed": seed,
        "source": {
            "file": claims_path.name,
            "sha256": sha256_file(claims_path),
            "n_claims": len(claims),
        },
        "counts": split["counts"],
        "dev": split["dev"],
        "test": split["test"],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def load_verifier_split(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assignments: dict[str, str] = {}
    for split_name in ("dev", "test"):
        for claim_id in payload[split_name]:
            if claim_id in assignments:
                raise ValueError(f"claim {claim_id} appears in more than one split")
            assignments[claim_id] = split_name
    return {"meta": payload, "assignments": assignments}


def choose_threshold(dev_rows: list[tuple[bool, float]]) -> float | None:
    """Threshold on DEV only: maximize accuracy, ties broken by lower threshold.

    ``dev_rows`` is ``(label_supported, score)`` for DEV claims only. Candidates
    are the unique DEV scores under the accept rule ``score >= t``, plus a
    reject-all candidate (returned as ``None``). Iterating candidates in
    ascending order and keeping a strictly better accuracy yields the lowest
    threshold among ties.
    """
    if not dev_rows:
        raise ValueError("no dev rows")
    candidates = sorted({score for _, score in dev_rows})
    best_threshold: float | None = None
    best_accuracy = -1.0
    for threshold in [*candidates, None]:
        correct = sum(
            1
            for label_supported, score in dev_rows
            if ((score >= threshold) if threshold is not None else False) == label_supported
        )
        accuracy = correct / len(dev_rows)
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_threshold = threshold
    return best_threshold


def _sentences(block: str) -> list[str]:
    return [s for s in _SENT_SPLIT.split(block.strip()) if s]


def chunk_doc(text: str, chunk_words: int = CHUNK_WORDS) -> list[str]:
    """Word-count packing of sentences into chunks (upstream flan-t5 path).

    Mirrors ``minicheck.inference``: sentence-tokenize preserving newline
    blocks, then greedily pack sentences until adding another would exceed
    ``chunk_words``. Upstream uses nltk for the sentence split; this project
    keeps nltk out of the lockfile and uses a deterministic regex split — a
    deliberate, documented difference that cannot change any score here because
    every calibration evidence text fits in a single chunk (asserted at run
    time and in tests).
    """
    sentences: list[str] = []
    for block in text.split("\n"):
        sentences.extend(_sentences(block))
        sentences.append("\n")
    if sentences and sentences[-1] == "\n":
        sentences.pop()
    if not sentences:
        sentences = [""]

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        n_words = len(sentence.split())
        if current and current_words + n_words > chunk_words:
            chunks.append(" ".join(current).replace(" \n ", "\n").strip())
            current = [sentence]
            current_words = n_words
        else:
            current.append(sentence)
            current_words += n_words
    if current:
        chunks.append(" ".join(current).replace(" \n ", "\n").strip())
    return [chunk for chunk in chunks if chunk]


class MiniCheckAdapter:
    """``score(claim, evidence) -> float`` in ``[0, 1]``, deterministic on CPU."""

    def __init__(
        self,
        model: Any = None,
        tokenizer: Any = None,
        *,
        revision: str = PINNED_REVISION,
        chunk_words: int = CHUNK_WORDS,
    ) -> None:
        if (model is None) != (tokenizer is None):
            raise ValueError("model and tokenizer must be provided together")
        self._chunk_words = chunk_words
        if model is None:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            model = AutoModelForSeq2SeqLM.from_pretrained(
                CKPT, revision=revision, torch_dtype=torch.float32
            )
            tokenizer = AutoTokenizer.from_pretrained(CKPT, revision=revision)
        self._model = model
        self._tokenizer = tokenizer
        self._model.eval()
        self._sanity_check()

    def _sanity_check(self) -> None:
        supported = self.score(claim=_PROBE_SUPPORTED, evidence=_PROBE_DOC)
        unsupported = self.score(claim=_PROBE_UNSUPPORTED, evidence=_PROBE_DOC)
        if not (supported > 0.5 > unsupported and supported - unsupported > _PROBE_MIN_MARGIN):
            raise ValueError(
                "checkpoint sanity probe failed: supported "
                f"{supported:.4f}, unsupported {unsupported:.4f} — is {CKPT} loaded?"
            )

    def score(self, claim: str, evidence: str) -> float:
        chunks = chunk_doc(evidence, chunk_words=self._chunk_words)
        if not chunks:
            chunks = [""]
        return max(self._support_prob(chunk, claim) for chunk in chunks)

    def _support_prob(self, doc_chunk: str, claim: str) -> float:
        import torch

        text = "predict: " + self._tokenizer.eos_token.join([doc_chunk, claim])
        inputs = self._tokenizer(
            [text], max_length=MAX_MODEL_LEN, truncation=True, return_tensors="pt"
        )
        decoder_input_ids = torch.zeros((1, 1), dtype=torch.long)
        with torch.no_grad():
            logits = self._model(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                decoder_input_ids=decoder_input_ids,
            ).logits
        label_logits = logits[0, -1, torch.tensor([NO_ID, YES_ID])].cpu()
        probs = torch.nn.functional.softmax(label_logits, dim=-1)
        return float(probs[1])
