# Wave 6.5B closeout — RAG article depth expansion (`projects/01-rag-agent/story.yaml`)

- Date: 2026-11-24
- Branch: `wave65b-rag-article-2026-11-24` (from `main` @ `3024eafb`)
- Scope: §3 of `collaboration/designs/20261124-wave65-ui-and-rag-article-polish/02-kimi-rag-and-articles-handoff.md` (RAG article prose depth), all §4 gates
- Not done: no commit, no push, no merge (owner/Claude review flow)
- Hosted LLM calls: none

## What changed

Exactly one file: `projects/01-rag-agent/story.yaml` (35 insertions, 32 deletions).
Prose expanded in the six main sections to the §3 word-count targets, grounded
in committed artifacts under `projects/01-rag-agent/reports/` and `DESIGN.md`.
Section flow, all tables, both code excerpts, all diagrams, figure lists,
`roadmap:` (5 neutral cards), and `short_version:` are untouched.

| section | words before → after | Flesch before → after | §3 target |
|---|---|---|---|
| background | 135 → 135 | 59.0 → 59.0 | 130–145 |
| objectives | 246 → 299 | 48.6 → 46.8 | 240–300 |
| data | 204 → 290 | 61.9 → 49.2 | 240–300 |
| eda | 157 → 239 | 67.9 → 55.0 | 190–240 |
| training | 192 → 437 | 67.3 → 55.8 | 430–500 (warn >550) |
| evaluation | 215 → 426 | 55.7 → 46.0 | 420–500 |
| results | 225 → 408 | 54.7 → 50.7 | 400–480 |
| conclusions | 460 → 460 | 36.1 → 36.1 | keep structured sections (not gated) |
| main thread total | 1834 → 2694 | — | soft cap 2600 (warning only) |

Every main section keeps one `**In plain terms:**` card as its final paragraph
and ≤3 figures; every Flesch score is ≥45.

### Content added (all report-backed)

- **objectives:** why-guardrails depth (calibrated refusal as first-class output,
  claim-support `0.6` floor + bounded two-retry repair, `$0.01` answer-path
  ceiling, CPU-only search, local-vs-hosted privacy split, why-not-bigger-model).
- **data:** corpus curation rationale (5 topics spanning vocabularies, anchor
  titles, 12k cap, SHA-256 checksums, 3-way query mix purpose).
- **eda:** dump-order bias, right-censored article lengths, missing flagship
  pages, direct verification instead of assumptions.
- **training:** S1 structure chunking (paragraph/heading boundaries, never
  mid-thought), S2 multi-hop exact-identifier vs paraphrase split, S3
  crowding-out rationale for the per-article cap (2) and 975→195 rerank pool,
  promotion protocol (dev → heldout → sealed ladder, retrieval-only tuning with
  zero LLM calls, measure top-5 vs serve top-3, 443/748 token means),
  tuning-ruled-out evidence (200/40 chunk tie at 0.831 broken on context cost;
  MiniLM 0.808 vs BGE-small 0.805; plain RRF not promoted, 0.533 vs 0.600 n=15),
  code-excerpt note now describes the fused S3 path.
- **evaluation:** judge failure story (44% false acceptance, kappa
  0.546/0.605), judge_v2 construction (147 claims, 72 one-detail same-subject
  negatives, 30/30 reviewer-agent audit, Wilson [0.8865, 1.0], 0.85 acceptance
  gate, owner hand-label pending), mechanical rails (12/16/200k, soft in-tool
  ceiling, 2 verify abstentions, 33 skipped claims, 0 mechanical false
  rejections), single-family judging paragraph.
- **results:** trace transparency intro, sealed-final-split sentence, retrieval
  coverage (88.6% exact gold chunks / 93.5% articles at top-5), 95.8% claim
  retention, verify latency 6.2 s = 31% of answer latency, cached reads 74% of
  agent input, `$0.781` agent + `$0.233` verify cost split, failure-shift
  narrative (1/120 unsupported, 10 unnecessary empties vs 11/92 missed incl.
  1 retrieval miss).

### Truth-in-copy preserved (spot-verified against committed reports)

- `$1.014` / `$0.0084` answer-path and `$1.458` / `$0.0121` total (never `$2.04`).
- `1 of 120` unsupported answers (`2 of 150` judged claims) — matches
  `reports/final_v3_e2e/f1_summary.json`.
- S3 led on `all-articles@5` across dev splits; promoted on the sealed run to
  0.9457 recall@5 — matches `reports/retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json`.
- `10` unnecessary empties vs `11/92` missed (incl. 1 retrieval miss).
- judge_v2: kimi-for-coding generated/verified/judged, cross-judge pending;
  30/30 is the reviewer-agent audit, owner hand-label pending.
- Faithfulness `0.8717 [0.8092, 0.9304]`, F1 `0.9091`, acc `0.8667 [0.7944, 0.9162]`,
  multi-hop 0.8333 vs 0.7917 — all match committed metrics.
- `final_v3` named as the consumed artifact everywhere.

### README/docs alignment

Not needed: no headline numbers changed, so README, docs PNGs, and
`check_headline_numbers.py` claim strings (`0.9091`, `0.946`) remain valid
(12 claims checked, 0 findings).

## §4 gate results (all from repo root unless noted)

| gate | result |
|---|---|
| `uv run python scripts/lint_story_language.py` | 13 stories — **0 errors, 0 warnings** |
| `uv run python scripts/check_headline_numbers.py` | 12 claims checked, 0 findings — OK |
| `uv run python scripts/check_short_copy.py --check` | single-sourced (39 surfaces across 13 stories) — OK |
| `uv run python scripts/check_docs.py` | OK |
| `uv run python scripts/gen_static_registry.py --check` | current — OK |
| `uv run python scripts/gen_story_short.py --check` | current — OK |
| `uv run python scripts/gen_route_manifest.py --check` | current (27 routes) — OK |
| `uv run python scripts/check_demo_contract.py` | OK |
| `uv run mkdocs build --strict` | built clean, 0.43 s |
| `apps/showcase-web`: `npm ci` (arm64 node v24.22.1) + `npm test` | 754 passed (754), exit 0 |
| `apps/showcase-web`: `npm run lint` | exit 0 |
| `apps/showcase-web`: `npm run build` | built in 7.67 s, exit 0 |

Note: `showcase-web` node_modules was stale (missing `@rollup/rollup-darwin-arm64`);
`npm ci` on the arm64 node fixed it. node_modules is not tracked, so the working
tree diff remains exactly `projects/01-rag-agent/story.yaml`.

## State left for review

- Working tree: `M projects/01-rag-agent/story.yaml` only.
- No commit, no push, no merge. Claude reviews, validates, commits, merges.
