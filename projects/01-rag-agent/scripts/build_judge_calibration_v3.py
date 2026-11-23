"""Build judge_v2 claims, Revision 4 (owner, 2026-11-23) — one-detail negatives.

Keeps the 75 supported claims from the archived v2a set
(``reports/judge_calibration_v2/superseded_v2a/judge_v2_claims.json``,
moved there before this script runs) and REPLACES the 75 unsupported claims:
for each supported claim's chunk, the LOCAL model (Ollama
qwen3.6:35b-a3b-q4_K_M, 127.0.0.1 only) drafts one negative on the same
subject that changes exactly one detail (date, quantity, relation,
comparison or attribute), so it is plausible but not stated or implied by
the chunk.

Code checks on every negative, per Revision 4:
- the changed term is absent from the chunk (case-insensitive) and is 4+
  characters or a number, and appears in the negative itself;
- the negative shares at least 3 content words with its chunk;
- no duplicate negatives;
- no shared 8-token sequence with any other claim (supported or accepted
  negative).

A failing negative is redrafted up to 3 times, then dropped (count
reported). The shared-content-word overlap distribution is reported in the
manifest and the experiment log.

Output: ``data/judge_v2_claims.json`` + ``data/judge_v2_claims.sha256.json``
(supersedes the archived v2a manifest). Raw drafts:
``reports/judge_calibration_v2/drafts/neg_<i>_attempt<a>.json``.

    HF_HUB_OFFLINE=1 uv run python scripts/build_judge_calibration_v3.py
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger

logger = get_logger(__name__)
ROOT = Path(__file__).resolve().parents[1]

SEED = 42
MODEL = "qwen3.6:35b-a3b-q4_K_M"
ENDPOINT = "http://localhost:11434/api/generate"
DRAFTS = ROOT / "reports" / "judge_calibration_v2" / "drafts"
ARCHIVE = ROOT / "reports" / "judge_calibration_v2" / "superseded_v2a"
CLAIMS_OUT = ROOT / "data" / "judge_v2_claims.json"
HOSTS: list[str] = []

NEGATIVE_PROMPT = """You are building calibration data for a claim-verification judge.

Below is a passage from an encyclopedia article and a TRUE claim supported by
the passage. Write ONE FALSE claim about the SAME subject that changes
EXACTLY ONE detail — a date, a quantity, a relation, a comparison or an
attribute — so it sounds plausible but is NOT stated or implied by the
passage. Keep every other fact identical to the true claim. Do not use
outside knowledge. At most 25 words, a single sentence.

Title: {title}

Passage:
{passage}

True claim: {claim}

Respond with a JSON object only:
{{"claim": "...", "changed": "the exact changed term in the false claim"}}"""

STOPWORDS = {"a", "an", "the", "of", "in", "on", "and", "or", "is", "was", "to"}
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def content_words(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS}


def token8(text: str) -> set[tuple[str, ...]]:
    toks = _TOKEN_RE.findall(text.lower())
    return {tuple(toks[i : i + 8]) for i in range(len(toks) - 7)}


def shared_with_chunk(claim: str, chunk_text: str) -> int:
    return len(content_words(claim) & content_words(chunk_text))


def changed_term_ok(changed: str, claim: str, chunk_text: str) -> str | None:
    """Return a failure reason, or None when the changed term passes."""
    term = changed.strip().strip("\"'.,;:!?()")
    if not term:
        return "empty changed term"
    low = term.lower()
    body = chunk_text.lower()
    # Word-boundary match for alphanumeric-bounded terms so "complete" does
    # not false-match "incomplete"; plain substring otherwise (e.g. "25%").
    if re.match(r"^\w", term) and re.search(r"\w$", term):
        present = re.search(rf"\b{re.escape(low)}\b", body) is not None
    else:
        present = low in body
    if present:
        return f"changed term {term!r} appears in the chunk"
    if len(term) < 4 and not re.search(r"\d", term):
        return f"changed term {term!r} is under 4 characters and has no digit"
    if low not in claim.lower():
        return f"changed term {term!r} not present in the negative claim"
    return None


def parse_json_block(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in response")
    parsed: dict[str, Any] = json.loads(match.group(0))
    return parsed


def generate(
    prompt: str, slot: str, attempt: int, temperature: float = 0.0, seed: int = SEED
) -> str:
    prompt_sha = hashlib.sha256(prompt.encode()).hexdigest()
    cached = DRAFTS / f"{slot}_attempt{attempt}.json"
    if cached.exists():
        data = json.loads(cached.read_text("utf-8"))
        if data.get("prompt_sha256") == prompt_sha and data.get("response"):
            HOSTS.append("localhost")  # cache hit: no Ollama call
            return str(data["response"])
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "seed": seed},
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
    (DRAFTS / f"{slot}_attempt{attempt}.json").write_text(
        json.dumps({"prompt_sha256": prompt_sha, "response": body.get("response", "")}) + "\n",
        encoding="utf-8",
    )
    return str(body.get("response", ""))


def ollama_digest(model: str) -> str:
    with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=30) as resp:
        data = json.load(resp)
    for entry in data.get("models", []):
        if entry.get("name") == model:
            return str(entry.get("digest", ""))
    raise SystemExit(f"model {model} not found in ollama list")


RETRY_NOTE = (
    "\n\nNote: previous attempt failed validation ({last_reason}). Change a DIFFERENT "
    "single detail (date, number, comparison, or attribute) using a word or number "
    "that does NOT appear anywhere in the passage."
)


def draft_negative_once(
    claim: str,
    chunk_text: str,
    title: str,
    slot: str,
    attempt: int,
    last_reason: str | None = None,
) -> dict[str, str]:
    """One drafting attempt; raises on parse/validation problems."""
    prompt = NEGATIVE_PROMPT.format(title=title, passage=chunk_text, claim=claim)
    temperature = 0.0
    seed = SEED
    if attempt > 1 and last_reason:
        prompt += RETRY_NOTE.format(last_reason=last_reason)
        temperature = round(0.25 * (attempt - 1), 2)
        seed = SEED + attempt
    parsed = parse_json_block(generate(prompt, slot, attempt, temperature=temperature, seed=seed))
    negative = str(parsed["claim"]).strip()
    changed = str(parsed["changed"]).strip()
    if not negative:
        raise ValueError("empty claim")
    return {"claim": negative, "changed": changed}


def main() -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    archived = json.loads((ARCHIVE / "judge_v2_claims.json").read_text("utf-8"))
    supported_items = [it for it in archived if it["kind"] == "supported"]
    if len(supported_items) != 75:
        raise SystemExit(f"expected 75 supported in the archive, got {len(supported_items)}")

    # Article titles for the drafting prompt, resolved from the corpus via the
    # chunk_id's article part (chunks are the production 200/40 layout).
    from rag_agent.cli import load_config
    from rag_agent.corpus import load_corpus

    articles = load_corpus(load_config())
    title_by_article = {a.article_id: a.title for a in articles}

    def title_for(chunk_id: str) -> str:
        return title_by_article.get(chunk_id.split("#")[0], "Article")

    # 8-gram scope (Revision 5): a negative is checked against OTHER claims —
    # supported claims with different text, and accepted negatives — but never
    # against its own source claim (one-detail negatives legitimately share
    # long runs with the sentence they mutate).
    other_supported_grams: set[tuple[str, ...]] = set()
    for it in supported_items:
        grams = token8(it["claim"])
        overlap = grams & other_supported_grams
        if overlap:
            logger.warning("supported claim shares an 8-gram (kept anyway): %r", it["claim"][:60])
        other_supported_grams |= grams
    sup_grams_by_claim = {it["claim"]: token8(it["claim"]) for it in supported_items}
    accepted_neg_grams: set[tuple[str, ...]] = set()

    seen_negatives: set[str] = set()
    negatives: list[dict[str, str]] = []
    dropped = 0
    overlaps: list[int] = []
    rng = random.Random(SEED)  # noqa: S311 - seeded reproducibility, not security

    for i, item in enumerate(supported_items):
        slot = f"neg_{i:03d}"
        src_claim = item["claim"]
        src_grams = token8(src_claim)
        others_grams = set().union(
            *(grams for claim_text, grams in sup_grams_by_claim.items() if claim_text != src_claim)
        )
        accepted_item: dict[str, str] | None = None
        last_reason: str | None = None
        for attempt in range(1, 4):
            try:
                draft = draft_negative_once(
                    src_claim,
                    item["chunk_text"],
                    title_for(item["chunk_id"]),
                    slot,
                    attempt,
                    last_reason,
                )
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                last_reason = str(exc)[:120]
                logger.info("%s attempt %d: %s", slot, attempt, last_reason)
                continue
            negative, changed = draft["claim"], draft["changed"]
            reason = changed_term_ok(changed, negative, item["chunk_text"])
            shared = shared_with_chunk(negative, item["chunk_text"])
            novel_grams = token8(negative) - src_grams
            if reason is None and shared < 3:
                reason = f"only {shared} shared content words with the chunk"
            if reason is None and negative.lower() in seen_negatives:
                reason = "duplicate negative"
            if reason is None and novel_grams & (others_grams | accepted_neg_grams):
                reason = "shares an 8-token sequence with another claim"
            if reason is None:
                accepted_item = {
                    "claim": negative,
                    "chunk_id": item["chunk_id"],
                    "chunk_text": item["chunk_text"],
                    "kind": "unsupported",
                }
                accepted_neg_grams |= novel_grams
                break
            last_reason = reason
            logger.info("%s attempt %d: %s", slot, attempt, reason)
        if accepted_item is None:
            dropped += 1
            logger.warning("%s dropped after 3 attempts", slot)
            continue
        seen_negatives.add(accepted_item["claim"].lower())
        negatives.append(accepted_item)
        overlaps.append(shared_with_chunk(accepted_item["claim"], item["chunk_text"]))
        if (i + 1) % 15 == 0:
            logger.info("negatives %d/%d (dropped %d)", i + 1, len(supported_items), dropped)

    items = list(supported_items) + negatives
    rng.shuffle(items)
    CLAIMS_OUT.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    file_sha = hashlib.sha256(CLAIMS_OUT.read_bytes()).hexdigest()
    overlap_dist = dict(sorted(Counter(overlaps).items()))
    manifest: dict[str, Any] = {
        "file": "judge_v2_claims.json",
        "sha256": file_sha,
        "revision": "4 (owner, 2026-11-23): one-detail same-subject negatives",
        "supersedes": "reports/judge_calibration_v2/superseded_v2a/judge_v2_claims.sha256.json",
        "n": len(items),
        "kind_counts": {
            "supported": sum(1 for it in items if it["kind"] == "supported"),
            "unsupported": sum(1 for it in items if it["kind"] == "unsupported"),
        },
        "construction": {
            "supported": "kept unchanged from the archived v2a set (75)",
            "unsupported": "one negative per supported claim's chunk, drafted by the "
            "local model: same subject, exactly one changed detail (date, quantity, "
            "relation, comparison or attribute); changed term absent from the chunk "
            "(case-insensitive, 4+ chars or a number), >= 3 shared content words, "
            "no duplicates, no shared 8-token sequence with any other claim; "
            "3 redrafts then dropped",
        },
        "negatives_dropped": dropped,
        "overlap_distribution_shared_content_words": overlap_dist,
        "seed": SEED,
        "drafting_model": MODEL,
        "drafting_model_digest": ollama_digest(MODEL),
        "sources": "supported claims from the archived v2a set (tuning-65/dev_v1 gold "
        "chunks only); no final_v3 or sealed-120 content",
        "request_hosts": sorted(set(HOSTS)),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    (ROOT / "data" / "judge_v2_claims.sha256.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    log_row = {
        "ts": manifest["generated_at"],
        "step": "judge-calibration-v2",
        "change": "claims-revision-4",
        "split": "n/a",
        "decision": "built",
        "reason": f"150 claims (75 supported kept + {len(negatives)} negatives, "
        f"{dropped} dropped); overlap distribution {overlap_dist}; sha {file_sha[:16]}",
    }
    log_path = ROOT / "reports" / "experiment_log.json"
    rows = json.loads(log_path.read_text("utf-8")) if log_path.exists() else []
    rows.append(log_row)
    log_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    logger.info(
        "wrote %d claims (supported %d / unsupported %d, dropped %d) sha %s",
        len(items),
        manifest["kind_counts"]["supported"],
        manifest["kind_counts"]["unsupported"],
        dropped,
        file_sha[:16],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
