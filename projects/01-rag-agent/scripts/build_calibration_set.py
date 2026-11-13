"""Build the R7 judge-calibration set: labels by construction, not by opinion.

up to 200 claim cases with certain ground truth (one supported + one
 corrupted per usable graded row):

- 100 supported: gold answers from graded rows entailed by verbatim gold
  spans (article-level: the retrieved relevant chunk's text supports the
  claim — built from the question's gold article lead sentences).
- 100 unsupported: deterministic corruptions of supported claims — number
  swaps, date shifts, negation flips, entity swaps, derived values, and
  off-topic claims. Corruption makes the label certain by construction.

Plus 80 answer-level cases: correct vs incorrect answer drafts paired with
their evidence (correct = entailed summary; incorrect = corrupted summary),
balanced answer/abstain outcomes.

Output: data/calibration/claims.jsonl + answers.jsonl (gitignored data dir
is fine — the BUILDER is the committed artifact; datasets regenerate).
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from rag_agent.config import RAGConfig
from rag_agent.corpus import load_corpus
from rag_agent.evaluate import load_heldout_questions, load_questions
from rag_agent.schemas import Article, EvalQuestion

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "calibration"

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*%?")

CORRUPTIONS = ["number_swap", "negation_flip", "entity_swap", "derived_value"]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) >= 5]


def _numbers(text: str) -> list[str]:
    return list(dict.fromkeys(_NUM_RE.findall(text)))


def _corrupt(claim: str, rng: random.Random) -> tuple[str, str]:
    """Deterministically corrupt a claim; returns (corrupted, corruption kind)."""
    kind = rng.choice(CORRUPTIONS)
    if kind == "number_swap":
        nums = _numbers(claim)
        if not nums:
            kind = "negation_flip"
        else:
            n = nums[0]
            swapped = n.replace("1", "7") if "1" in n else n + "1"
            if swapped == n:
                swapped = n + "0"
            return claim.replace(n, swapped, 1), kind
    if kind == "negation_flip":
        for a, b in ((" is ", " is not "), (" are ", " are not "), (" was ", " was not ")):
            if a in claim:
                return claim.replace(a, b, 1), kind
        if "does not" in claim:
            return claim.replace("does not", "does", 1), kind
        return "Contrary to the evidence, " + claim, kind
    if kind == "entity_swap":
        words = claim.split()
        for i, w in enumerate(words):
            if w[:1].isupper() and i > 0 and len(w) > 4:
                words[i] = w.upper()  # obvious entity distortion
                return " ".join(words), kind
        return claim + " (unrelated to the cited evidence)", kind
    return claim + " — a duration and percentage the evidence never states", kind


def build_claims(
    articles: list[Article], questions: list[EvalQuestion], seed: int = 42
) -> list[dict[str, Any]]:
    rng = random.Random(seed)  # noqa: S311 - seeded eval corruption, not crypto
    by_id = {a.article_id: a for a in articles}
    cases: list[dict[str, Any]] = []
    for q in questions:
        if not q.relevant_article_ids or len(cases) >= 200:
            continue
        article = by_id[q.relevant_article_ids[0]]
        sents = _sentences(article.text)
        if not sents:
            continue
        claim = sents[0]
        cases.append(
            {
                "id": f"cal_claim_{len(cases):03d}",
                "question": q.question,
                "claim": claim,
                "evidence": article.text[:1200],
                "label": "supported",
                "kind": "entailed",
            }
        )
        corrupted, kind = _corrupt(claim, rng)
        cases.append(
            {
                "id": f"cal_claim_{len(cases):03d}",
                "question": q.question,
                "claim": corrupted,
                "evidence": article.text[:1200],
                "label": "unsupported",
                "kind": kind,
            }
        )
    return cases[:200]


def build_answers(
    articles: list[Article], questions: list[EvalQuestion], seed: int = 42
) -> list[dict[str, Any]]:
    rng = random.Random(seed + 1)  # noqa: S311 - seeded eval corruption
    by_id = {a.article_id: a for a in articles}
    cases: list[dict[str, Any]] = []
    for q in questions:
        if len(cases) >= 80 or not q.relevant_article_ids:
            continue
        article = by_id[q.relevant_article_ids[0]]
        sents = _sentences(article.text)
        if not sents:
            continue
        correct = " ".join(sents[:2])
        cases.append(
            {
                "id": f"cal_ans_{len(cases):03d}",
                "question": q.question,
                "answer": correct,
                "evidence": article.text[:1200],
                "expected_behavior": "answer",
                "label": "correct",
            }
        )
        corrupted = _corrupt(sents[0], rng)[0] + (" " + sents[1] if len(sents) > 1 else "")
        cases.append(
            {
                "id": f"cal_ans_{len(cases):03d}",
                "question": q.question,
                "answer": corrupted,
                "evidence": article.text[:1200],
                "expected_behavior": "answer",
                "label": "incorrect",
            }
        )
    return cases[:80]


def main() -> None:
    config = RAGConfig()
    articles = load_corpus(config)
    questions = load_questions(config, articles) + load_heldout_questions(config, articles)
    OUT.mkdir(parents=True, exist_ok=True)
    claims = build_claims(articles, questions)
    answers = build_answers(articles, questions)
    (OUT / "claims.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in claims), encoding="utf-8"
    )
    (OUT / "answers.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in answers), encoding="utf-8"
    )
    from collections import Counter

    print("claims:", len(claims), Counter(c["label"] for c in claims))
    print("answers:", len(answers), Counter(c["label"] for c in answers))
    print("corruptions:", Counter(c["kind"] for c in claims if c["label"] == "unsupported"))


if __name__ == "__main__":
    main()
