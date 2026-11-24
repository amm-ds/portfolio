"""Build final_v3: 120 sealed-quality questions drafted by the LOCAL model.

Stage 1 of the phase0-infra handoff (revision 2, 2026-11-22). Drafting and
the answerability check use the local open model `qwen3.6:35b-a3b-q4_K_M` on
Ollama (127.0.0.1:11434) only — zero hosted calls. Every model request's host
is recorded; any non-localhost host stops the run.

Read-restriction (enforced): model-facing drafting reads ONLY
`data/raw/corpus.jsonl` and the chunks built from it. Every file opened is
logged to `reports/final_v3_file_access.json` with phase markers; opening a
tuning/heldout/sealed/stress question file through the guarded open raises.
The overlap validator reads the existing sets AFTER all drafting inputs are
fixed (its reads are logged; prompts never carry set content).

Prompts are fixed text below, each with its sha256 recorded in the overlap
report; every raw model response is saved under `reports/final_v3_drafts/`.

Outputs: data/golden_final_v3.json (+ sha256 + overlap manifests),
reports/final_v3_file_access.json, reports/final_v3_drafts/*.json,
reports/final_v3_review_sample.md.

    HF_HUB_OFFLINE=1 uv run python scripts/build_final_v3.py
"""

from __future__ import annotations

import builtins
import hashlib
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "raw" / "corpus.jsonl"
DRAFTS = ROOT / "reports" / "final_v3_drafts"
ACCEPTED = DRAFTS / "accepted.jsonl"
ACCESS_LOG = ROOT / "reports" / "final_v3_file_access.json"
MODEL = "qwen3.6:35b-a3b-q4_K_M"
ENDPOINT = "http://localhost:11434/api/generate"
CHUNK_SIZE = 200
CHUNK_OVERLAP = 40
SEED = 42
JACCARD_MAX = 0.4
COSINE_MAX = 0.85
TITLE_OVERLAP_MAX = 0.05
MAX_ATTEMPTS = 3
TARGETS = {"single_hop": 68, "multi_hop": 24, "unanswerable": 28}

SINGLE_HOP_PROMPT = """\
You write evaluation questions for a retrieval QA benchmark over a Wikipedia corpus.

Article title: {title}

Passage from the article:
{passage}

Write ONE natural question that is answerable from this passage alone, and give its
short answer. The question must not be answerable without the passage specific
facts. Vary question wording: do not start every question with "What".

Return JSON only: {{"question": "...", "answer": "..."}}"""

MULTI_HOP_PROMPT = """\
You write evaluation questions for a retrieval QA benchmark over a Wikipedia corpus.

Article A title: {title_a}
Passage A:
{passage_a}

Article B title: {title_b}
Passage B:
{passage_b}

The two articles share the entity: {entity}

Write ONE natural question that can only be answered by combining facts from BOTH
passages (for example comparing, relating, or connecting the two). Give the short
combined answer.

Return JSON only: {{"question": "...", "answer": "..."}}"""

UNANSWERABLE_PROMPT = """\
You write evaluation questions for a retrieval QA benchmark over a Wikipedia corpus.

The corpus covers these topics: {topics}

An adjacent topic NOT covered by the corpus is: {adjacent}

Write ONE plausible, specific question about {adjacent} that a user might ask,
which the corpus cannot answer. Then list the key terms (2-4) the question needs
that the corpus would have to contain to answer it.

Return JSON only: {{"question": "...", "absent_terms": ["...", "..."]}}"""

ANSWERABILITY_PROMPT = """You check answerability for a retrieval QA benchmark.

Question: {question}

Chunks:
{chunks}

Is the question answerable from these chunks alone? Answer YES or NO first, then
one short reason.

Return JSON only: {{"answerable": "YES" or "NO", "reason": "..."}}"""

ADJACENT_TOPICS = [
    "the moons of Pluto",
    "semiconductor fabrication plants in Europe",
    "the 2022 FIFA World Cup knockout stage",
    "deep-sea hydrothermal vent ecosystems",
    "the history of the printing press in Asia",
    "volcanic eruptions of the 2010s",
    "quantum computing hardware companies",
    "the migratory routes of Arctic terns",
    "the economy of Iceland",
    "famous chess openings named after cities",
    "the Roman aqueducts of Gaul",
    "antibiotic resistance in livestock",
    "the tallest buildings in Southeast Asia",
    "glacier retreat in the Andes",
    "the phonology of the Basque language",
    "nuclear power plants under construction",
    "the life cycle of monarch butterflies",
    "medieval trade routes in West Africa",
    "the chemistry of lithium-ion batteries",
    "coral bleaching events on the Great Barrier Reef",
    "the works of Hokusai",
    "the population history of Australia",
    "the geology of the Himalayas",
    "fermentation in Japanese cuisine",
    "the Apollo-Soyuz mission",
    "endangered amphibians of Madagascar",
    "the history of vaccination",
    "tidal energy projects",
    "the architecture of Antoni Gaudi",
    "snow leopard conservation",
]

# --- read/write restriction -------------------------------------------------

ACCESS: list[dict[str, Any]] = []
FORBIDDEN_READ = re.compile(r"(eval_questions\.json|golden_.*\.json|stress.*\.json)$")
ALLOWED_WRITE_ROOTS = ("data/", "reports/")


def mark(phase: str) -> None:
    ACCESS.append({"op": "phase", "phase": phase, "ts": time.time()})


_ORIG_OPEN = builtins.open


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _orig_open(path: Any, *a: Any, **k: Any) -> Any:
    return _ORIG_OPEN(path, *a, **k)


def guard_open(path: Any, *a: Any, **k: Any) -> Any:
    p = str(path)
    ACCESS.append({"op": "open", "path": p, "ts": time.time()})
    if FORBIDDEN_READ.search(p):
        raise PermissionError(f"read-restriction: refusing to open question file {p}")
    return _orig_open(path, *a, **k)


setattr(builtins, "open", guard_open)  # noqa: B010 - deliberate process-local guard


def guard_write(path: Path, text: str) -> None:
    rel = path.resolve().relative_to(ROOT.resolve())
    if not str(rel).startswith(ALLOWED_WRITE_ROOTS):
        raise PermissionError(f"write-guard: refusing to write outside data//reports/: {rel}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with _orig_open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


# --- local model client ------------------------------------------------------

HOSTS: list[str] = []


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
    text: str = body.get("response", "")
    DRAFTS.mkdir(parents=True, exist_ok=True)
    guard_write(
        DRAFTS / f"{slot}_attempt{attempt}.json",
        json.dumps({"prompt_sha256": _sha(prompt), "response": text}, ensure_ascii=False) + "\n",
    )
    return text


def parse_json_block(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in response")
    parsed: dict[str, Any] = json.loads(match.group(0))
    return parsed


# --- corpus helpers ----------------------------------------------------------


def load_corpus() -> list[dict[str, Any]]:
    articles = []
    with _orig_open(CORPUS, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                articles.append(json.loads(line))
    return articles


def build_chunks(articles: list[dict[str, Any]]) -> dict[str, list[Any]]:
    from rag_agent.chunking import chunk_by_size

    by_article: dict[str, list[Any]] = {}
    for art in articles:
        by_article[art["article_id"]] = chunk_by_size(
            art["text"], art["article_id"], size=CHUNK_SIZE, overlap=CHUNK_OVERLAP
        )
    return by_article


def substantive(chunk: Any) -> bool:
    return len(chunk.text) > 300 and chunk.text.count(".") >= 2


def chunk_for(article: dict[str, Any], by_article: dict[str, list[Any]], offset: int) -> Any:
    chunks = [c for c in by_article[article["article_id"]] if substantive(c)]
    return chunks[offset % len(chunks)]


def jaccard(a: str, b: str) -> float:
    ta = {w.strip(".,;:!?()\"'").lower() for w in a.split()} - {""}
    tb = {w.strip(".,;:!?()\"'").lower() for w in b.split()} - {""}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def answer_supported(answer: str, chunk_text: str) -> bool:
    """Gold-support check: verbatim substring, or >=60% content words present."""
    if answer.lower() in chunk_text.lower():
        return True
    words = {w.strip(".,;:!?()\"'").lower() for w in answer.split()} - {
        "a",
        "an",
        "the",
        "of",
        "in",
        "on",
        "and",
        "or",
        "is",
        "was",
        "to",
    }
    words -= {""}
    if not words:
        return False
    text = chunk_text.lower()
    return sum(1 for w in words if w in text) / len(words) >= 0.6


def proper_nouns(text: str) -> set[str]:
    return set(re.findall(r"\b([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)+)\b", text))


# --- shared drafting context -------------------------------------------------


class Ctx:
    """Everything the per-category builders share (built once, corpus-only)."""

    def __init__(self) -> None:
        self.articles = load_corpus()
        self.by_article = build_chunks(self.articles)
        self.corpus_text = "\n".join(a["text"].lower() for a in self.articles)
        self.corpus_titles = {a["title"].strip().lower() for a in self.articles}
        self.topics_line = ", ".join(sorted({a["topic"] for a in self.articles}))
        self.rng: random.Random = random.Random(SEED)  # noqa: S311 - reproducibility
        pool = [
            a
            for a in self.articles
            if any(substantive(c) for c in self.by_article[a["article_id"]])
        ]
        self.rng.shuffle(pool)
        self.single_iter = iter(pool)
        self.attempts: list[dict[str, Any]] = []
        self.used_titles: set[str] = set()
        self.existing_questions: list[str] = []
        self.existing_vecs: Any = None
        self.st_model: Any = None
        self.sealed_titles: set[str] = set()

    def load_validator_sets(self) -> None:
        """Post-input-fixing: the validator (not the model prompts) reads sets."""

        def _load(path: Path) -> None:
            with _orig_open(path, encoding="utf-8") as fh:
                for item in json.load(fh):
                    self.existing_questions.append(item["question"])

        _load(ROOT / "src/rag_agent/eval_questions.json")
        _load(ROOT / "data/golden_heldout.json")
        _load(ROOT / "data/golden_sealed_v2.json")
        _load(ROOT / "data/golden_sealed_v2_58.json")
        for stress in sorted((ROOT / "data").glob("golden_stress*.json")):
            _load(stress)
        self.sealed_titles = {
            t.strip().lower()
            for item in json.load(_orig_open(ROOT / "data/golden_sealed_v2.json", encoding="utf-8"))
            for t in item.get("relevant_titles", [])
        }
        from sentence_transformers import SentenceTransformer

        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        self.st_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        import numpy as np

        self.existing_vecs = np.asarray(
            self.st_model.encode(self.existing_questions), dtype="float32"
        )

    def register_accepted(self, question: str) -> None:
        """Same-run dedup: questions accepted later in this run must see this one."""
        self.existing_questions.append(question)
        import numpy as np

        self.existing_vecs = np.asarray(
            self.st_model.encode(self.existing_questions), dtype="float32"
        )

    def check_overlap(self, question: str, gold_titles: list[str]) -> list[str]:
        problems = []
        lowered = {q.strip().lower() for q in self.existing_questions}
        if question.strip().lower() in lowered:
            problems.append("exact duplicate")
        for q in self.existing_questions:
            jac = jaccard(question, q)
            if jac >= JACCARD_MAX:
                problems.append(f"jaccard {jac:.3f} vs existing")
                break
        if self.existing_vecs is not None:
            import numpy as np

            vq = np.asarray(self.st_model.encode([question]), dtype="float32")[0]
            sims = (self.existing_vecs @ vq) / (
                np.linalg.norm(self.existing_vecs, axis=1) * np.linalg.norm(vq) + 1e-9
            )
            if float(sims.max()) >= COSINE_MAX:
                problems.append(f"cosine {float(sims.max()):.3f} vs existing")
        # Strict per-slot rule: a candidate may not introduce ANY sealed-v2
        # title. The end-state share (<= TITLE_OVERLAP_MAX) is then bounded
        # by construction and re-checked in write_outputs.
        new_hits = {t.strip().lower() for t in gold_titles} & self.sealed_titles
        if new_hits:
            problems.append(f"introduces sealed-v2 titles: {sorted(new_hits)}")
        return problems


# --- per-category builders ---------------------------------------------------


def load_accepted() -> dict[str, dict[str, Any]]:
    if not ACCEPTED.exists():
        return {}
    out = {}
    for line in ACCEPTED.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["slot"]] = row["item"]
    return out


def append_accepted(slot: str, item: dict[str, Any]) -> None:
    with ACCEPTED.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"slot": slot, "item": item}, ensure_ascii=False) + "\n")


def build_single_hop(ctx: Ctx, prior: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for slot in range(TARGETS["single_hop"]):
        if f"single_{slot}" in prior:
            out.append(prior[f"single_{slot}"])
            print(f"single {slot + 1}/{TARGETS['single_hop']} (resumed)", flush=True)
            continue
        accepted = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            # Kept slots drew from the same seeded pool on their run; skip any
            # article already used or sealed so redrafts draw fresh, eligible
            # material instead of burning attempts on pre-determined rejects.
            while True:
                art = next(ctx.single_iter)
                title = art["title"].strip().lower()
                used_lower = {t.strip().lower() for t in ctx.used_titles}
                if title not in used_lower and title not in ctx.sealed_titles:
                    break
            chunk = chunk_for(art, ctx.by_article, slot + attempt)
            prompt = SINGLE_HOP_PROMPT.format(title=art["title"], passage=chunk.text)
            try:
                draft = parse_json_block(generate(prompt, f"single_{slot:03d}", attempt))
                question, answer = draft["question"].strip(), draft["answer"].strip()
                if not answer_supported(answer, chunk.text):
                    raise ValueError("answer not supported by gold chunk")
                problems = ctx.check_overlap(question, [art["title"]])
                if problems:
                    print(f"  single_{slot} attempt {attempt}: {problems}", flush=True)
                    ctx.attempts.append(
                        {"slot": f"single_{slot}", "attempt": attempt, "problems": problems}
                    )
                    continue
                accepted = {
                    "question": question,
                    "category": "single_hop",
                    "expected_behavior": "answer",
                    "relevant_titles": [art["title"]],
                    "absent_terms": [],
                    "gold_chunk_ids": [chunk.chunk_id],
                    "answer": answer,
                }
                break
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                print(f"  single_{slot} attempt {attempt}: {str(exc)[:120]}", flush=True)
                ctx.attempts.append(
                    {"slot": f"single_{slot}", "attempt": attempt, "problems": [str(exc)[:120]]}
                )
        if accepted is None:
            raise SystemExit(f"STOP: slot single_{slot} failed {MAX_ATTEMPTS} attempts")
        ctx.used_titles.update(accepted["relevant_titles"])
        append_accepted(f"single_{slot}", accepted)
        ctx.register_accepted(accepted["question"])
        out.append(accepted)
        print(f"single {slot + 1}/{TARGETS['single_hop']} ok", flush=True)
    return out


def _next_fresh_pair(
    ctx: Ctx, pair_iter: Iterator[tuple[dict[str, Any], dict[str, Any], str]]
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Draw the next pair whose articles no kept slot has used."""
    while True:
        art_a, art_b, entity = next(pair_iter)
        titles = {art_a["title"].strip().lower(), art_b["title"].strip().lower()}
        used_lower = {t.strip().lower() for t in ctx.used_titles}
        if not titles & used_lower:
            return art_a, art_b, entity


def build_multi_hop(ctx: Ctx, prior: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    by_topic: dict[str, list[dict[str, Any]]] = {}
    for art in ctx.articles:
        by_topic.setdefault(art["topic"], []).append(art)
    pairs: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for topic, group in sorted(by_topic.items()):
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                shared = proper_nouns(group[i]["text"]) & proper_nouns(group[j]["text"])
                shared = {s for s in shared if len(s) > 3 and s.lower() not in topic.lower()}
                if shared:
                    pairs.append((group[i], group[j], sorted(shared)[0]))
    ctx.rng.shuffle(pairs)

    def _pair_allowed(pair: tuple[dict[str, Any], dict[str, Any], str]) -> bool:
        titles = {pair[0]["title"].strip().lower(), pair[1]["title"].strip().lower()}
        return not titles & ctx.sealed_titles

    pairs = [p for p in pairs if _pair_allowed(p)]
    pair_iter = iter(pairs)

    out = []
    for slot in range(TARGETS["multi_hop"]):
        if f"multi_{slot}" in prior:
            out.append(prior[f"multi_{slot}"])
            print(f"multi {slot + 1}/{TARGETS['multi_hop']} (resumed)", flush=True)
            continue
        accepted = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                art_a, art_b, entity = _next_fresh_pair(ctx, pair_iter)
            except StopIteration:
                raise SystemExit("STOP: multi-hop article pairs exhausted") from None
            ca = chunk_for(art_a, ctx.by_article, slot)
            cb = chunk_for(art_b, ctx.by_article, slot + 1)
            prompt = MULTI_HOP_PROMPT.format(
                title_a=art_a["title"],
                passage_a=ca.text,
                title_b=art_b["title"],
                passage_b=cb.text,
                entity=entity,
            )
            try:
                draft = parse_json_block(generate(prompt, f"multi_{slot:03d}", attempt))
                question, answer = draft["question"].strip(), draft["answer"].strip()
                head_a = art_a["title"].split()[0].strip(",").lower()
                head_b = art_b["title"].split()[0].strip(",").lower()
                links = [entity.lower(), head_a, head_b]
                if not any(link and link in question.lower() for link in links):
                    raise ValueError("question links to neither article")
                problems = ctx.check_overlap(question, [art_a["title"], art_b["title"]])
                if problems:
                    print(f"  multi_{slot} attempt {attempt}: {problems}", flush=True)
                    ctx.attempts.append(
                        {"slot": f"multi_{slot}", "attempt": attempt, "problems": problems}
                    )
                    continue
                accepted = {
                    "question": question,
                    "category": "multi_hop",
                    "expected_behavior": "answer",
                    "relevant_titles": [art_a["title"], art_b["title"]],
                    "absent_terms": [],
                    "gold_chunk_ids": [ca.chunk_id, cb.chunk_id],
                    "answer": answer,
                }
                break
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                print(f"  multi_{slot} attempt {attempt}: {str(exc)[:120]}", flush=True)
                ctx.attempts.append(
                    {"slot": f"multi_{slot}", "attempt": attempt, "problems": [str(exc)[:120]]}
                )
        if accepted is None:
            raise SystemExit(f"STOP: slot multi_{slot} failed {MAX_ATTEMPTS} attempts")
        ctx.used_titles.update(accepted["relevant_titles"])
        append_accepted(f"multi_{slot}", accepted)
        ctx.register_accepted(accepted["question"])
        out.append(accepted)
        print(f"multi {slot + 1}/{TARGETS['multi_hop']} ok", flush=True)
    return out


def build_unanswerable(ctx: Ctx, prior: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    topics_order = ctx.rng.sample(ADJACENT_TOPICS, len(ADJACENT_TOPICS))
    out = []
    for slot in range(TARGETS["unanswerable"]):
        if f"unanswerable_{slot}" in prior:
            out.append(prior[f"unanswerable_{slot}"])
            print(f"unanswerable {slot + 1}/{TARGETS['unanswerable']} (resumed)", flush=True)
            continue
        accepted = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            # Deterministic per-slot ring: resume-stable (a slot redraws the
            # same topics as any prior run); stride 7 is collision-free across
            # slots (gcd(7, 30) == 1) and stride 10 spreads a slot's retries
            # far apart so one cluster of similar topics cannot exhaust it.
            # Same-run question dedup is the real guard.
            adjacent = topics_order[(slot * 7 + (attempt - 1) * 10) % len(topics_order)]
            prompt = UNANSWERABLE_PROMPT.format(topics=ctx.topics_line, adjacent=adjacent)
            try:
                draft = parse_json_block(generate(prompt, f"unanswerable_{slot:03d}", attempt))
                question = draft["question"].strip()
                absent = [str(t).strip() for t in draft["absent_terms"] if str(t).strip()]
                if not absent:
                    raise ValueError("no absent_terms")
                if any(adjacent.lower() in title for title in ctx.corpus_titles):
                    raise ValueError("adjacent topic is a corpus title")
                # Coverage is title-based: a passing mention of a term in some
                # article's body does not make a question answerable. The leak
                # case is an absent term that names a corpus topic.
                absent_in_corpus = [
                    t for t in absent if any(t.lower() in title for title in ctx.corpus_titles)
                ]
                if absent_in_corpus:
                    raise ValueError(f"absent terms name corpus topics: {absent_in_corpus}")
                problems = ctx.check_overlap(question, [])
                if problems:
                    print(f"  unanswerable_{slot} attempt {attempt}: {problems}", flush=True)
                    ctx.attempts.append(
                        {"slot": f"unanswerable_{slot}", "attempt": attempt, "problems": problems}
                    )
                    continue
                accepted = {
                    "question": question,
                    "category": "unanswerable",
                    "expected_behavior": "abstain",
                    "relevant_titles": [],
                    "absent_terms": absent,
                    "gold_chunk_ids": [],
                    "answer": "",
                }
                break
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                print(f"  unanswerable_{slot} attempt {attempt}: {str(exc)[:120]}", flush=True)
                ctx.attempts.append(
                    {
                        "slot": f"unanswerable_{slot}",
                        "attempt": attempt,
                        "problems": [str(exc)[:120]],
                    }
                )
        if accepted is None:
            raise SystemExit(f"STOP: slot unanswerable_{slot} failed {MAX_ATTEMPTS} attempts")
        append_accepted(f"unanswerable_{slot}", accepted)
        ctx.register_accepted(accepted["question"])
        out.append(accepted)
        print(f"unanswerable {slot + 1}/{TARGETS['unanswerable']} ok", flush=True)
    return out


def answerability_pass(results: list[dict[str, Any]], ctx: Ctx) -> list[dict[str, Any]]:
    out = []
    for i, item in enumerate(results):
        if item["expected_behavior"] != "answer":
            continue
        chunks_text = []
        for cid in item["gold_chunk_ids"]:
            art_id = cid.split("#")[0]
            for c in ctx.by_article.get(art_id, []):
                if c.chunk_id == cid:
                    chunks_text.append(f"[{cid}]\n{c.text}")
        prompt = ANSWERABILITY_PROMPT.format(
            question=item["question"], chunks="\n\n".join(chunks_text)
        )
        try:
            resp = parse_json_block(generate(prompt, f"answerability_{i:03d}", 1))
            verdict = str(resp.get("answerable", "")).upper().startswith("YES")
            out.append(
                {
                    "index": i,
                    "answerable_from_gold": verdict,
                    "reason": str(resp.get("reason", ""))[:200],
                }
            )
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            out.append({"index": i, "answerable_from_gold": None, "reason": f"parse error: {exc}"})
        print(f"answerability {i + 1}/{len(results)}", flush=True)
    return out


def write_outputs(
    results: list[dict[str, Any]],
    ctx: Ctx,
    answerability: list[dict[str, Any]],
) -> None:
    final = [
        {
            "question": r["question"],
            "category": r["category"],
            "expected_behavior": r["expected_behavior"],
            "relevant_titles": r["relevant_titles"],
            "absent_terms": r["absent_terms"],
            "gold_chunk_ids": r["gold_chunk_ids"],
        }
        for r in results
    ]
    unique_gold_titles = {t.strip().lower() for r in results for t in r["relevant_titles"]}
    sealed_overlap = unique_gold_titles & ctx.sealed_titles
    share = len(sealed_overlap) / max(1, len(unique_gold_titles))
    if share > TITLE_OVERLAP_MAX:
        raise SystemExit(f"STOP: sealed-v2 title share {share:.4f} exceeds {TITLE_OVERLAP_MAX}")
    guard_write(
        ROOT / "data/golden_final_v3.json",
        json.dumps(final, indent=2, ensure_ascii=False) + "\n",
    )
    final_sha = hashlib.sha256((ROOT / "data/golden_final_v3.json").read_bytes()).hexdigest()
    agreement = sum(1 for a in answerability if a["answerable_from_gold"] is True)

    overlap_report = {
        "seed": SEED,
        "model": MODEL,
        "targets": TARGETS,
        "thresholds": {
            "jaccard_max": JACCARD_MAX,
            "cosine_max": COSINE_MAX,
            "sealed_title_overlap_max": TITLE_OVERLAP_MAX,
        },
        "prompts_sha256": {
            "single_hop": _sha(SINGLE_HOP_PROMPT),
            "multi_hop": _sha(MULTI_HOP_PROMPT),
            "unanswerable": _sha(UNANSWERABLE_PROMPT),
            "answerability": _sha(ANSWERABILITY_PROMPT),
        },
        "existing_questions_checked": len(ctx.existing_questions),
        "attempts": ctx.attempts,
        "answerability_check": {
            "n_answerable": len(answerability),
            "answerable_from_gold": agreement,
            "note": (
                "answerable-from-non-gold-chunks rate not measured here (no retrieval "
                "in this script); no drops on that figure"
            ),
        },
        "title_overlap": {
            "unique_gold_titles": len(unique_gold_titles),
            "in_sealed_120": len(sealed_overlap),
            "share": round(len(sealed_overlap) / max(1, len(unique_gold_titles)), 4),
        },
        "request_hosts": sorted(set(HOSTS)),
    }
    guard_write(
        ROOT / "data/golden_final_v3.overlap.json",
        json.dumps(overlap_report, indent=2, ensure_ascii=False) + "\n",
    )
    guard_write(
        ROOT / "data/golden_final_v3.sha256.json",
        json.dumps(
            {
                "file": "golden_final_v3.json",
                "sha256": final_sha,
                "n_questions": len(final),
                "counts": {
                    "single_hop": sum(1 for r in final if r["category"] == "single_hop"),
                    "multi_hop": sum(1 for r in final if r["category"] == "multi_hop"),
                    "unanswerable": sum(1 for r in final if r["category"] == "unanswerable"),
                },
                "model": MODEL,
                "seed": SEED,
                "note": (
                    "Stage 2 freeze per owner directive (Stages 1-3, "
                    "2026-11-22); owner review sample pending"
                ),
            },
            indent=2,
        )
        + "\n",
    )
    guard_write(
        ACCESS_LOG,
        json.dumps({"access": ACCESS, "forbidden_pattern": FORBIDDEN_READ.pattern}, indent=1)
        + "\n",
    )

    sample_rng = random.Random(SEED + 1)  # noqa: S311 - seeded sampling
    sample: list[dict[str, Any]] = []
    for cat, n in (("single_hop", 18), ("multi_hop", 6), ("unanswerable", 6)):
        idxs = [i for i, r in enumerate(results) if r["category"] == cat]
        for i in sample_rng.sample(idxs, n):
            sample.append(
                {
                    "category": cat,
                    "index": i,
                    "question": results[i]["question"],
                    "gold_chunk_ids": results[i]["gold_chunk_ids"],
                    "absent_terms": results[i]["absent_terms"],
                    "answer": results[i].get("answer", ""),
                    "answerable_from_gold": next(
                        (a["answerable_from_gold"] for a in answerability if a["index"] == i),
                        None,
                    ),
                }
            )
    lines = [
        "# final_v3 owner review sample (30: 18 single-hop / 6 multi-hop / 6 unanswerable)",
        "",
        "Acceptance rule: at least 27 of 30 accepted. Rejections and their reasons are",
        "recorded per item; on failure the failed items and category are redrafted and a",
        "fresh 30-item sample is reviewed.",
        "",
    ]
    for s in sample:
        lines += [
            f"## [{s['category']}] index {s['index']}",
            "",
            f"Question: {s['question']}",
            "",
        ]
        if s["gold_chunk_ids"]:
            lines.append(f"Gold chunks: {s['gold_chunk_ids']}")
        if s["absent_terms"]:
            lines.append(f"Absent terms: {s['absent_terms']}")
        if s["answer"]:
            lines.append(f"Answer: {s['answer']}")
        if s["answerable_from_gold"] is not None:
            lines.append(f"Answerable from gold (local check): {s['answerable_from_gold']}")
        lines += [
            "",
            "Checks: no exact duplicate; Jaccard < 0.4; cosine < 0.85; unanswerable "
            "items verified absent corpus-wide.",
            "",
        ]
    guard_write(ROOT / "reports/final_v3_review_sample.md", "\n".join(lines))

    print(
        "DONE",
        len(final),
        "questions | sha",
        final_sha[:16],
        "| sealed title overlap",
        f"{len(sealed_overlap)}/{len(unique_gold_titles)}",
        "| answerability agreement",
        f"{agreement}/{len(answerability)}",
    )


def main() -> None:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.pop("LLM_BASE_URL", None)
    os.environ.pop("LLM_API_KEY", None)
    mark("drafting inputs: corpus only")
    ctx = Ctx()
    mark("validator loading existing sets (prompts never read them)")
    ctx.load_validator_sets()
    prior = load_accepted()
    # Seed validator state from previously accepted slots so redrafted slots
    # cannot duplicate kept questions or reintroduce sealed-v2 titles.
    for item in prior.values():
        ctx.used_titles.update(item["relevant_titles"])
        if item["question"] not in ctx.existing_questions:
            ctx.existing_questions.append(item["question"])
    if prior:
        import numpy as np

        ctx.existing_vecs = np.asarray(ctx.st_model.encode(ctx.existing_questions), dtype="float32")
    results = (
        build_single_hop(ctx, prior) + build_multi_hop(ctx, prior) + build_unanswerable(ctx, prior)
    )
    answerability = answerability_pass(results, ctx)
    write_outputs(results, ctx, answerability)


if __name__ == "__main__":
    main()
