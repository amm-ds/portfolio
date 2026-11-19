# Next round 2 report: merge + items 1–5

Date: 2026-11-19
Handoff: `collaboration/designs/20261119-next-round-2/03-implementation-handoff.md`
Hosted spend: **$0.00** (no hosted calls in this round). No downloads, no new
dependencies, no deploys. Held items (Q3b/Q3c/Q4c/Q4d/Q4h/09 pass^k/W3) not
run. Branch `next-round-2-2026-11-19` (pushed, upstream set) — not merged to
`main`, no deploy; production server untouched.

## Step 0 — merge

`origin/next-round-2026-11-19` verified at `032bf34`; merged into `main`
with merge commit **`3ac47bd`** ("merge: next round 2026-11-19 (Q4a, RAG
copy, DI sample, Q4b)", Co-Authored-By trailer as the last line). Push
result: `23816fe..3ac47bd main -> main` (no force). Branch kept.

## Item rows

| Item | Status | Files | Gates actually run |
|---|---|---|---|
| 1 — DR-learner label + DESIGN row (10) | done | `single_protocol.py` (renamed key/labels), `DESIGN.md` row, regenerated `reports/single_protocol/` via the project CLI (values unchanged) | ruff check/format clean; mypy 15 files clean; check-docs OK; lint 0/0; short-copy 39 surfaces OK; storyShort current; headline-numbers 11 claims/0 findings |
| 2 — agent-chat failure triage | done; all unclassified (evidence limit) | NEW `reports/triage-2026-11-19.md` + one-line `.gitignore` exception (`!reports/triage-*.md`, same pattern as the eval reports) | none specified (read-only analysis); no model calls |
| 3 — rolling-origin MLP vs LightGBM (12) | done; tie holds | NEW `rolling_origin.py` + CLI, `reports/rolling_origin/` | project-12 pytest exit 0; ruff/format clean; mypy 12 files clean; headline-numbers OK |
| 4 — cold-start timings (11) | done | NEW `cold_start.py` + CLI, `reports/cold_start/` | project-11 pytest **46/46** on a quiet machine (first concurrent run flaked one timing-slope assertion; rerun green); ruff/format clean; mypy 15 files clean; headline-numbers OK |
| 5 — open-loop arrival arm (13) | done | NEW `open_loop.py` + CLI, `reports/open_loop/` | project-13 pytest exit 0; ruff/format clean; mypy 17 files clean; headline-numbers OK |

Commits: `e1160d8` (item 1) · `f69e650` (item 2) · `4b11e29` (item 3) ·
`4f5beb0` (item 5) · `2dbdc00` (item 4). Push: new branch with upstream.

## Numbers (each with its source file)

**Item 1** — `projects/10-uplift-experimentation/reports/single_protocol/metrics.json`
(regenerated, identical values): dr_learner −3.5258 [−16.2121, 9.7036],
t_learner/two_model 12.0252 [−0.0135, 24.1773], x_learner 5.9040 [−6.0967,
17.8957]. DESIGN.md now states a library causal forest remains out of scope.

**Item 2** — `apps/agent-chat/reports/triage-2026-11-19.md`: k3.1-pro 9
failed assertions, k3-256k 7; cause groups all **unclassified** (the
committed reports carry empty FAIL notes and no diagnostics section; the
transcripts are not committed). By domain: AnswerKeywords 6 (k3.1-pro) / 5
(k3-256k), RefusalGraceful 3 / 1, CitationsWhenGrounded 0 / 1. Tool-set and
side-effect graders passed on the failed answer-keyword cases in both runs.

**Item 3** — `projects/12-tabular-ml-lifecycle/reports/rolling_origin/metrics.json`:
8 weekly origins × 168 rows on the committed validation window; identity
verified (recomputed full-window validation MAE == committed `train_runs.json`,
MLP 34.217 / LightGBM 34.397). Per-origin diff (MLP − LightGBM) ranges
−6.218 (week 7) to +1.871 (week 6) MAE; pooled **−0.180 [−1.367, +1.854]**
(day-block bootstrap, 24 h blocks) — the committed validation tie holds
across origins. No headline change.

**Item 4** — `projects/11-data-engineering/reports/cold_start/metrics.json`:
15 cold-measurable cells × 5 fresh-process probes on the real-trip bundle.
Cold medians 1.01–1.96× the committed warm medians (e.g.
partitioned_read/sqlite 5.296 s cold vs 5.190 s warm; write_parquet/pandas
0.520 vs 0.500; read_csv/pandas 1.192 vs 1.165). Per-cell spread (max−min
over 5 probes) is small: 0.001–0.121 s.

**Item 5** — `projects/13-model-serving/reports/open_loop/metrics.json`:
constant-arrival arm, 300 requests per cell at 50/100/200 req/s, both
backends, zero errors everywhere. p99 (nearest-rank, with paired bootstrap
95% CI over raw records): native 0.0073 [0.0061, 0.0088] / 0.0022 [0.0020,
0.0022] / 0.0023 [0.0021, 0.0024] s; onnx 0.0032 / 0.0021 / 0.0020 s (CIs in
the file). The service absorbs the full offered range; the r50 native cell
carries the warm-up tail.

## Notes

- Item 2's required output path is under `apps/agent-chat/.gitignore`'s
  `reports/*` rule; added `!reports/triage-*.md` following the file's own
  committed-evidence exception pattern (stated in the commit and here).
- Item 4's first full-suite run flaked `test_scalability_schema` (log-log
  slope −0.54 vs −0.5 floor) because the machine was concurrently running
  this round's benchmarks; the suite passes 46/46 on a quiet machine. Not
  related to the new code (the test never touches it).
- Item 3 note: per-origin intervals rest on 7 non-overlapping day blocks —
  few blocks, wide intervals; read per-origin signs directionally.
- `collaboration/designs/20261119-next-steps/` remains untracked (source
  design; outside the commit scope).
