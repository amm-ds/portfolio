"""Build judge_v2: 150 calibration claims from tuning-65 / dev_v1 gold chunks.

Step 1 of the 20261122-rag-execution-plan handoff (Revision 3, 2026-11-23).
Claims are drafted by the LOCAL model (Ollama qwen3.6:35b-a3b-q4_K_M, temp 0)
and verified mechanically; kimi-for-coding is used for LABELLING ONLY, by
``scripts/label_judge_calibration_v2.py``.

Sources: ``src/rag_agent/eval_questions.json`` (tuning-65; dev_v1 is a subset)
— gold chunks are the production-layout chunks (200 / overlap 40, size mode)
of the answerable questions' relevant_titles. final_v3 and sealed-120 files
are NEVER read; this script does not reference their paths.

Kinds:
- ``supported`` (75): a short claim drafted from a gold chunk and verified
  against it (content-word coverage >= 0.6, the build_final_v3 criterion).
- ``unsupported`` (75): 40 cross-chunk claims (a supported claim paired with a
  different article's chunk as evidence; coverage < 0.2 against the evidence)
  + 35 mutated claims (number / year / entity edit of a supported claim; the
  changed token must not appear in the evidence chunk, so support is broken
  even though the content words still match).

Output: ``data/judge_v2_claims.json`` (items {claim, chunk_id, chunk_text,
kind}) + ``data/judge_v2_claims.sha256.json`` manifest. Raw drafts are kept
under ``reports/judge_calibration_v2/drafts/``.

    HF_HUB_OFFLINE=1 uv run python scripts/build_judge_calibration_v2.py
"""

from __future__ import annotations

import json
import os
import random
import re
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger
from rag_agent.cli import load_config
from rag_agent.corpus import load_corpus
from rag_agent.index import chunk_articles

logger = get_logger(__name__)
ROOT = Path(__file__).resolve().parents[1]

SEED = 42
TARGETS = {"supported": 75, "unsupported_cross": 40, "unsupported_mutated": 35}
MODEL = "qwen3.6:35b-a3b-q4_K_M"
ENDPOINT = "http://localhost:11434/api/generate"
DRAFTS = ROOT / "reports" / "judge_calibration_v2" / "drafts"
HOSTS: list[str] = []

SUPPORTED_PROMPT = """You are building calibration data for a claim-verification judge.

Below is a passage from an encyclopedia article. Write ONE short, self-contained
factual claim (a single sentence, at most 25 words) that is fully supported by
the passage. Use only facts stated in the passage. Do not ask a question; state
a fact. Numbers and dates must match the passage exactly.

Title: {title}

Passage:
{passage}

Respond with a JSON object only: {{"claim": "..."}}"""

STOPWORDS = {"a", "an", "the", "of", "in", "on", "and", "or", "is", "was", "to"}


def coverage(claim: str, text: str) -> float:
    """Fraction of the claim's content words present in ``text`` (lowercased)."""
    words = {w.strip(".,;:!?()\"'").lower() for w in claim.split()} - STOPWORDS - {""}
    if not words:
        return 0.0
    body = text.lower()
    return sum(1 for w in words if w in body) / len(words)


def supported(claim: str, chunk_text: str) -> bool:
    if claim.lower() in chunk_text.lower():
        return True
    return coverage(claim, chunk_text) >= 0.6


def parse_json_block(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in response")
    parsed: dict[str, Any] = json.loads(match.group(0))
    return parsed


def generate(prompt: str, slot: str, attempt: int) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "seed": SEED},
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310 - localhost
        body = json.load(resp)
    host = urllib.parse.urlparse(ENDPOINT).hostname
    HOSTS.append(str(host))
    if host not in ("127.0.0.1", "localhost"):
        raise SystemExit(f"NON-LOCALHOST REQUEST: {ENDPOINT}")
    DRAFTS.mkdir(parents=True, exist_ok=True)
    raw = DRAFTS / f"{slot}_attempt{attempt}.json"
    raw.write_text(
        json.dumps({"prompt_sha256": sha256_text(prompt), "response": body.get("response", "")})
        + "\n",
        encoding="utf-8",
    )
    return str(body.get("response", ""))


def sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ollama_digest(model: str) -> str:
    with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=30) as resp:
        data = json.load(resp)
    for entry in data.get("models", []):
        if entry.get("name") == model:
            return str(entry.get("digest", ""))
    raise SystemExit(f"model {model} not found in ollama list")


def draft_supported(title: str, passage: str, slot: str) -> str:
    """Draft a claim entailed by ``passage``; 3 attempts then stop."""
    prompt = SUPPORTED_PROMPT.format(title=title, passage=passage)
    for attempt in range(1, 4):
        try:
            claim = str(parse_json_block(generate(prompt, slot, attempt))["claim"]).strip()
            if not claim:
                raise ValueError("empty claim")
            if supported(claim, passage):
                return claim
            logger.info("%s attempt %d: claim not supported by passage", slot, attempt)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            logger.info("%s attempt %d: %s", slot, attempt, exc)
    raise SystemExit(f"STOP: {slot} failed 3 attempts")


_NUMBER_RE = re.compile(r"\d+")
_YEAR_RE = re.compile(r"\b(19|20)(\d{2})\b")
_ENTITY_RE = re.compile(r"\b([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)+)\b")


def mutate(claim: str, titles: list[str], rng: random.Random) -> tuple[str, str] | None:
    """Deterministic near-miss edit; returns (variant, changed_token) or None.

    ``changed_token`` is the inserted number/year/entity — the caller verifies
    it does not appear in the evidence chunk, which breaks support even when
    the claim's content words still match (digits are not content words).
    """
    number = _NUMBER_RE.search(claim)
    if number:
        value = int(number.group(0))
        delta = rng.choice([1, 2, 3, -1, -2])
        if value + delta > 0:
            variant = claim[: number.start()] + str(value + delta) + claim[number.end() :]
            return variant, str(value + delta)
    year = _YEAR_RE.search(claim)
    if year:
        value = int(year.group(0))
        delta = rng.choice([1, 2, 3, 4, -1, -2, -3])
        variant = claim[: year.start()] + str(value + delta) + claim[year.end() :]
        return variant, str(value + delta)
    entity = _ENTITY_RE.search(claim)
    if entity and titles:
        for _ in range(5):
            other = rng.choice(titles)
            head = other.split("(")[0].strip()
            if head and head.lower() not in entity.group(0).lower():
                variant = claim[: entity.start()] + head + claim[entity.end() :]
                return variant, head
    return None


def build_pool(
    tuning: list[dict[str, Any]], chunks: list[Any], title_to_id: dict[str, str]
) -> list[tuple[int, str]]:
    """(question index, gold chunk id) pairs for answerable tuning/dev questions."""
    pool: list[tuple[int, str]] = []
    for qi, q in enumerate(tuning):
        if q.get("expected_behavior", "answer") != "answer":
            continue
        for t in q.get("relevant_titles") or []:
            article_id = title_to_id.get(t)
            if not article_id:
                continue
            pool.extend((qi, c.chunk_id) for c in chunks if c.article_id == article_id)
    return pool


def draft_supported_claims(
    picks: list[tuple[int, str]], by_id: dict[str, Any]
) -> tuple[list[dict[str, str]], list[tuple[str, str]]]:
    """Draft and verify the supported claims; returns items and (claim, chunk_id)."""
    items: list[dict[str, str]] = []
    accepted: list[tuple[str, str]] = []
    for i, (_qi, chunk_id) in enumerate(picks):
        chunk = by_id[chunk_id]
        claim = draft_supported(chunk.title, chunk.text, f"sup_{i:03d}")
        accepted.append((claim, chunk_id))
        items.append(
            {"claim": claim, "chunk_id": chunk_id, "chunk_text": chunk.text, "kind": "supported"}
        )
        if (i + 1) % 15 == 0:
            logger.info("supported %d/%d", i + 1, len(picks))
    return items, accepted


def build_unsupported_claims(
    rng: random.Random,
    accepted: list[tuple[str, str]],
    chunks: list[Any],
    by_id: dict[str, Any],
    titles: list[str],
) -> list[dict[str, str]]:
    """Unsupported claims: cross-chunk pairings + mutated near-misses."""
    items: list[dict[str, str]] = []

    # Cross-chunk: a supported claim paired with a different article's chunk.
    made = 0
    tries = 0
    while made < TARGETS["unsupported_cross"] and tries < 400:
        tries += 1
        claim, gold_chunk_id = accepted[rng.randrange(len(accepted))]
        other = chunks[rng.randrange(len(chunks))]
        if other.article_id == by_id[gold_chunk_id].article_id:
            continue  # same article: the claim may well be supported
        if coverage(claim, other.text) >= 0.2:
            continue
        items.append(
            {
                "claim": claim,
                "chunk_id": other.chunk_id,
                "chunk_text": other.text,
                "kind": "unsupported",
            }
        )
        made += 1
    if made < TARGETS["unsupported_cross"]:
        raise SystemExit(f"cross-chunk: made {made}/{TARGETS['unsupported_cross']}")

    # Mutated near-miss of a supported claim. Support is broken by
    # construction: the changed token must not appear in the evidence chunk.
    made = 0
    tries = 0
    while made < TARGETS["unsupported_mutated"] and tries < 400:
        tries += 1
        claim, chunk_id = accepted[rng.randrange(len(accepted))]
        result = mutate(claim, titles, rng)
        if result is None:
            continue
        variant, changed = result
        chunk_text = by_id[chunk_id].text
        if variant == claim or changed.lower() in chunk_text.lower():
            continue  # mutation re-states a fact the chunk actually contains
        items.append(
            {
                "claim": variant,
                "chunk_id": chunk_id,
                "chunk_text": chunk_text,
                "kind": "unsupported",
            }
        )
        made += 1
    if made < TARGETS["unsupported_mutated"]:
        raise SystemExit(f"mutated: made {made}/{TARGETS['unsupported_mutated']}")
    return items


def main() -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    config = load_config()
    articles = load_corpus(config)
    chunks = chunk_articles(articles, size=200, overlap=40)
    by_id = {c.chunk_id: c for c in chunks}
    title_to_id = {a.title: a.article_id for a in articles}
    titles = [a.title for a in articles]

    tuning_raw: list[dict[str, Any]] = json.loads(
        (ROOT / "src" / "rag_agent" / "eval_questions.json").read_text("utf-8")
    )
    pool = build_pool(tuning_raw, chunks, title_to_id)
    if len(pool) < TARGETS["supported"]:
        raise SystemExit(f"gold pool too small: {len(pool)}")
    logger.info("gold pool: %d (question, chunk) pairs", len(pool))

    rng = random.Random(SEED)  # noqa: S311 - seeded reproducibility, not security
    picks = rng.sample(pool, TARGETS["supported"])
    items, accepted = draft_supported_claims(picks, by_id)
    items.extend(build_unsupported_claims(rng, accepted, chunks, by_id, titles))
    rng.shuffle(items)
    out = ROOT / "data" / "judge_v2_claims.json"
    out.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    import hashlib

    file_sha = hashlib.sha256(out.read_bytes()).hexdigest()
    manifest: dict[str, Any] = {
        "file": "judge_v2_claims.json",
        "sha256": file_sha,
        "n": len(items),
        "kind_counts": {
            "supported": sum(1 for it in items if it["kind"] == "supported"),
            "unsupported": sum(1 for it in items if it["kind"] == "unsupported"),
        },
        "construction": {
            "supported": "drafted by local model, coverage >= 0.6 vs its gold chunk",
            "unsupported_cross": "claim paired with a different article's chunk, coverage < 0.2",
            "unsupported_mutated": "number/year/entity edit; the changed token is absent "
            "from the evidence chunk",
        },
        "seed": SEED,
        "drafting_model": MODEL,
        "drafting_model_digest": ollama_digest(MODEL),
        "sources": "src/rag_agent/eval_questions.json (tuning-65, incl. dev_v1) gold chunks only; "
        "no final_v3 or sealed-120 content",
        "request_hosts": sorted(set(HOSTS)),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    (ROOT / "data" / "judge_v2_claims.sha256.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    logger.info(
        "wrote %d claims (supported %d / unsupported %d) sha %s",
        len(items),
        manifest["kind_counts"]["supported"],
        manifest["kind_counts"]["unsupported"],
        file_sha[:16],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
