# Wave 6.5C closeout — RAG 01 article, figures, diagrams & honest provenance polish

- Date: 2026-11-24
- Branch: `wave65c-rag-polish-2026-11-24` (created from `main` @ `060c475a`)
- Handoff: `collaboration/designs/20261124-rag-article-and-figures-polish/03-implementation-handoff.md`
- Not done: no commit, no push, no merge (owner/Claude review flow)
- Hosted LLM calls / paid APIs: none
- `roadmap:` (5 neutral cards) and `RoadmapBlock.tsx`: untouched

## Step 1 — Judge provenance across public copy

`owner_sample.json` / `owner_sample_validated.json` carry the owner's 30 labels
(blind to the model's labels; 7 passage-level corrections reviewed and accepted
during the reviewer audit). Updated wording on every copy surface:

- `story.yaml`: `short_version` ("Judge sample: 30/30 owner-labelled.", 227 chars ≤ 280),
  `evaluation` judge-audit bullet (blind labelling + 7-item re-check), judge
  table audit column, `conclusions` same-family-judging limit, In-plain-terms card.
- `README.md`, `docs/projects/01-rag-agent.md`, root `README.md` projects row,
  `docs/projects/index.md` row, `apps/showcase-web/src/lib/cardCopy.ts`,
  `collaboration/ITERATION_TRACKER.md`: all synced; regenerated `storyShort.ts`.
- Stale "owner hand-label pending" remains only in the roadmap card detail
  (`story.yaml` roadmap, out of scope by handoff §2) — left byte-identical on purpose.

## Step 2 — Figures & diagrams

- `figures.py` / `build_final_figures.py`:
  - `retrieval_ladder`: fixed colour per arm (R0 slate / S1 sky / S2 violet / S3 teal)
    identical in both panels so the palette can never shift when a cell is absent;
    value-label font reduced to stop ceiling overlap; takeaway now states the metric
    definitions (recall@5 chunk-exact on final_v3 vs article-level on dev splits).
  - `final_outcome`: title "Final pass (final_v3)" (no "sealed"), FP bar labelled
    "budget stop (no answer)", takeaway notes all 4 FPs are budget stops.
  - `failure_taxonomy`: value labels on every bar, title carries `n = 120`,
    y-range headroom for labels.
  - `verify_funnel`: kept stage renamed, kept-bar labelled "95.8% of drafted kept",
    takeaway leads with the kept share.
  - Scope string "final_v3 sealed pass" → "final_v3 final pass".
- Regenerated all four JSON+HTML via `build_final_figures.py` (fails loudly on
  drift — all cross-checks passed), re-exported PNGs via
  `scripts/export_readme_figures.py` for the four figures + RAG README hero;
  unrelated projects' PNG re-renders were reverted (kept the diff scoped).
- Diagrams: `ragPipeline.ts` redrawn to the shipped S3 system (title-anchored
  chunks, dense FAISS + BM25 RRF k=60 pool 50, rerank top 6×k, per-article cap 2,
  recall@5 0.946, p50 16.5 s, faithfulness 0.872, refusal 24/28, verifier worded
  as boolean claim verdicts with ≥ 60% survive-or-abstain). `auto-1` gate nodes
  reworded (agent search + ≥ 60% survive), `auto-2` ev node "65 tuning, 55 gate,
  120 final_v3", `auto-3` nodes reflect judge_v2 30/30 owner audit + final_v3
  120 questions read 4×, `auto-4` title "Final pass results" + s15 node updated.
  Auto specs hand-edited (converter is idempotent over committed specs; the
  mermaidToFlow round-trip test still expects "generated 0 spec(s)" — passes).
- Removed stranded figures: `latency_histogram`, `kimi_generation_comparison`,
  `fusion_arm_comparison` from `evaluation:`, `retrieval_funnel` from
  `conclusions:` (files stay on disk as tuning artifacts); their four orphaned
  `figure_captions` entries removed (story-schema validation requirement);
  `conclusions` re-attached `final_outcome` (a final-pass figure its summary
  actually recounts) to keep the no-visual lint rule green.
- Fixed `eda_corpus_composition` caption unit clash (words counted, chars capped).

## Step 3 — 8-rule narrative refinement (`story.yaml`)

- Definitions at first use: F1 glossed in Background; `recall@5` defined as a hit
  rate with the chunk-exact (final_v3) vs article-level (dev) distinction in
  Objectives; `all-articles@5` defined in plain words in Training; "mechanical
  checks" defined (verbatim substring, numbers, dates/months, negation polarity)
  in Evaluation before any counts.
- Worked trace (rule 5): the LM Wind Power question quoted end to end — search
  `top_rank 1`, single claim accepted unchanged, "GE Renewable Energy" with one
  citation; every detail verified against `question_traces_heldout.json`,
  `data/golden_final_v3.json`, and the gold chunk text.
- Schema-refusal story added to Conclusions lessons (citation mandate made refusal
  unrepresentable, ~33M-token tool loops, fix resolved 6/6 stress rows — verified
  against README/DESIGN history).
- Objectives Target table gained the "Unsupported answers: none stated → 1 / 120" row.
- Stress C in Conclusions now names the cause (verifier crash on an empty judge
  batch, 27 verifier failures in `detail.stress_c.claim_accounting`) — it measures
  that bug, not the model.
- Truth fixes: S1 "1.000 on three splits" overclaim corrected (lift on dev_65;
  dev_v1/dev_40 already tied); R0-era MRR 0.718→0.808 / 975→195 moved from the S3
  bullet into "what tuning ruled out" with the rank-not-recall interpretation;
  rerank scope corrected (top 6×k, not the whole pool); untraced "MiniLM (80 MB)"
  dropped; Qwen3 arms tie at the n = 16 ceiling added; "A wrong-but-plausible
  answer is gone" overclaim softened; repeated "every rule exists because…" frame
  cut (kept the Training one); "every" occurrences varied; +4.2-point retrieval
  lift re-attached to the retrieval metric instead of the answer count.
- No `[Next: ...]` links inside In-plain-terms cards (none remain on this branch).

Final linter-measured state (all Flesch ≥ 45 on main sections, all < 540 words,
background 140 ≤ 145): background 140/55.1, objectives 326/48.0, data 288/47.9,
eda 249/50.8, training 500/57.9, evaluation 452/47.2, results 498/49.6,
conclusions 586/32.3 (not gated).

## Step 4 — README / docs / DESIGN alignment

- `README.md`: top short-copy synced; judge provenance paragraph rewritten
  (blind owner labels + 7-item audit, hosted calibration fixed to 39.7% of
  unsupported claims 69/174); "Finalized sealed pass" → "Final pass"; judge table
  row reworded; R6–R8.1 dense history compressed into a 6-row table (G8) with the
  schema-defect note kept as the closing paragraph; Limits rewritten to mirror the
  story (consumed set, same-family judging, over-abstention).
- `docs/projects/01-rag-agent.md`: "Key results" heading de-parenthesized;
  evaluation set description "65 graded questions" → "120 final_v3 + prior 65/55";
  "Held-out confirmation" → "Earlier gate set"; "Current grounding-hardened
  configuration" → "Superseded grounding configuration"; reviewer-agent wording
  → owner-labelled blind; chunk_size_sweep alt text no longer contradicts the tie;
  T3 denominator fix; "sealed" dropped from the ladder alt text.
- `DESIGN.md`: rerank "5 × top_k" → "6 × top_k"; §2 architecture mermaid + new
  prose summary now show BM25 + RRF + per-article cap + verify loop; stale
  "README.md §Wave 14/16" pointer fixed; 2026-11-23 changelog entry updated
  (consumed-set wording, owner-labelled audit). ($2.0392 was already removed
  from main by `060c475a`.)

## §4 gate results

| gate | result |
|---|---|
| `gen_static_registry.py` (+ `--check`) | current |
| `gen_story_short.py` (+ `--check`) | current |
| `gen_route_manifest.py` (+ `--check`) | current (27 routes) |
| `lint_story_language.py` | **0 errors, 0 warnings** |
| `check_headline_numbers.py` | 12 claims, 0 findings |
| `check_short_copy.py --check` | OK (39 surfaces) |
| `check_docs.py` | OK |
| `check_figure_budget.py` | OK (1 pre-existing warn: 03 telemetry_flags 594 KiB) |
| `check_figure_axes.py` | OK (2 pre-existing warns on retrieval_ladder windows, identical on base commit) |
| `check_demo_contract.py` | OK |
| `mkdocs build --strict` | clean, 0.41 s |
| `ruff check .` + `ruff format --check .` | all checks passed, 897 files formatted |
| `pytest` (`projects/01-rag-agent`) | 185 tests passed; from project dir exit 0. **Note:** from the repo root the coverage gate reports 78.30% (< 80) — verified pre-existing: the unmodified base commit produces the identical failure and percentage. Not caused by this wave; worth a separate look at the root vs project-dir coverage config. |
| `showcase-web` `npm test` | 754 passed (one assertion updated for the renamed verifier node label) |
| `showcase-web` `npm run lint` / `npm run build` | exit 0 / built in 7.66 s |

## State left for review

- Working tree: 32 changed files — story.yaml, README.md, DESIGN.md,
  figures.py + build_final_figures.py, 4 figure JSON/HTML pairs, 5 PNGs,
  5 diagram specs, cardCopy/storyShort/staticRegistry, FlowDiagram test,
  docs page + index, root README, ITERATION_TRACKER, route manifest, plus the
  owner's own uncommitted `owner_sample*.json` / `ITERATION_TRACKER.md` label
  work that rode along from `main`'s working tree (not mine, not committed).
- No commit, no push, no merge. Claude reviews, validates, commits, merges.
