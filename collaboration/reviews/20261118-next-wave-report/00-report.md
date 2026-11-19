# Next-wave report — W1, W2, W4, W5, W6, W9

Date: 2026-11-19
Executor: Kimi Code (per `collaboration/designs/20261118-next-wave/01-kimi-next-wave-message.md`)
Owner approved W1, W2, W4, W5, W6, W9 on 2026-11-18. W3, W7, W8, W10, W11, W12
not touched. No git mutations, no deploys, no `.env`/config changes, no hosted
calls.

## Summary

| Item | Status | What changed |
|---|---|---|
| W1 cross-project report fixes | done | Morning-report owner list now states 3 blocked end-to-end + 1 partial block with the OPEN_QUESTIONS paths; commit/deploy/pre-queue items marked done. Comparison.md gains the h19 note: legacy miss was the calculator-guard error (2^500, bounded retries burned, no refusal marker); live run refused h19 correctly. |
| W2 10-uplift "profit" sweep | done | 40+ prose renames across `story.yaml` (body + captions + results tables + roadmap + key concepts), `MODEL_CARD.md`, `portfolio.yaml` ("revenue minus send cost" / "value"); figure ids, metric keys, `DESIGN.md`, `dvc.yaml`, `params.yaml` untouched. Also aligned two leftover "+69%" story spots to +70%. `staticRegistry.ts` regenerated (portfolio.yaml feeds it). short_version unchanged (274 chars). |
| W4 headline-number drift check | done | New `scripts/check_headline_numbers.py` (11 claims, one per project with a clean scalar headline, each derived from its committed metrics file; surfaces = project README + story). `KNOWN_DRIFT` holds the two uncovered projects (01, 04). Tests in `scripts/tests/test_check_headline_numbers.py` (clean pass / stale flag / broken-source / known-filter). First run caught real drift — see below — now `headline-numbers: OK (no unknown drift)`. |
| W5 interval-methods doc | done | New `docs/engineering/statistical-intervals.md` (Wilson, instance/series bootstrap, paired row, block, nearest-rank, seeded no-skill ensembles + the wording rules), registered in `mkdocs.yml` nav under Engineering and linked from `repo-conventions.md` §Metrics storage. |
| W6 03-anomaly runs disclosure | done | Card now states "One fit per series; no-skill = 16 seeded baselines" (272 chars — exactly-at-280 rejected by the validator, trimmed); story results table gains a "champion (1 run/series)" column note + Lyu 2026 citation (single unreplicated source); README states the same next to the no-skill band. Copy surfaces synced. |
| W9 PyVRP table check | done | Paper read directly (arXiv 2403.13795v2). **Resolved:** Table 4 = CVRP (X-n### Uchoa instances); Table 5 = VRPTW (C1_10_*/C2_10_*/R1_10_*/R2_10_*/RC1_10_*/RC2_10_* — Homberger/Gehring 1000-customer names; caption matches). No Solomon table exists. Published headline confirmed: PyVRP mean gap 0.40% / gap-of-mean 0.46% vs HGS-DIMACS 0.32% / DIMACS reference 0.29% (10 seeds, 2 h PassMark-normalized, 27/300 BKS improved). Consequence recorded: the 0.40% is NOT comparable to this repo's Solomon-100 local run; 06 README cites no PyVRP numbers (verified). `table_check` block added to the results JSON; research-deltas §3 updated. No PyVRP numbers changed. |

## W4 first-run findings (fixed, not mass-edited)

1. **03 README/story quoted precision CI [0.231, 0.811]** — true 3-decimal of the
   committed 0.2304618201129829 is **0.230**. Real drift introduced by my
   overnight hand-rounding; corrected to [0.230, 0.811] in both files.
2. **06 story lacked the mean-gap bootstrap CI** — added "(95 % bootstrap CI
   [3.22 %, 5.28 %] over the 56 instances)" to the results prose.
3. **Check bugs found by its own first run**: `×`/`−` unicode formatting (fixed
   via escapes), 10-uplift source moved to `data/dataset_contract.json`
   (n_rows 42,613 — the two-arm frame contract), 11/12 extractors aligned with
   copy's unicode signs.

## Gates (all run, all green)

- `uv run ruff check .` — All checks passed; `ruff format --check` — already formatted.
- `uv run mypy libs projects apps` — Success (233 files).
- Web: `npm test` 746 passed (53 files), `npm run lint` clean, `npm run build` ✓.
- `lint_story_language` 0/0 · `check_docs` OK · `check_short_copy` single-sourced (39 surfaces) · `check_demo_contract` OK · `gen_static_registry --check` current · `gen_story_short --check` current · `gen_route_manifest --check` current · `mkdocs build --strict` OK · `check_headline_numbers.py` OK (11 claims, 0 findings).
- `uv run pytest -q` full suite — **exit 0, 97.69% total coverage**.

## Open questions for the owner

None new. The wave's unapproved items stand where the plan left them: W3
(provenance-stamp `_meta` fix — needs your diff review), W7/W8 (hosted caps),
W10/W11/W12 (decisions).
