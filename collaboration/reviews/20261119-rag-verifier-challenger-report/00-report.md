# RAG verifier challenger Phase 1 report

Date: 2026-11-20
Handoff: `collaboration/designs/20261119-rag-verifier-challenger/03-implementation-handoff.md`
(approved: Phase 1 only, incl. the MiniCheck-FT5 download after its license check)
Branch: `verifier-challenger-2026-11-20` from `apps-rag-pass-2026-11-20` (head
`601bcbf`). No merge to main, no deploy, no hosted calls, no copy or headline
changes. New files only, plus one `.gitignore` whitelist (report dir + split
file) following the repo's R2/R3 committed-evidence pattern.

## Verdict

**Gate: FAIL — on the false-rejection criterion only.** MiniCheck-FT5 at the
DEV-chosen threshold is ~10× stricter than the hosted judge on false
acceptance of unsupported claims, and pays for it with over-abstention on
supported claims — the same trade-off shape R8 measured for stricter LLM
judge prompts. Per the handoff, a fail is a valid outcome and is reported as
the finding; the gate and threshold rule were not touched after results.

## Commits and push

- `ad7d1ea` — `docs(01): verifier challenger checkpoint license record`
- `eebe331` — `feat(01): verifier challenger - fixed dev/test split of the
  calibration claims, before any scoring` (split + adapter + harness + tests;
  the harness landed in this commit so every commit keeps the suite green —
  the tests import the harness module)
- `31eb637` — `feat(01): verifier challenger Phase 1 result (offline, $0 hosted)`
- Pushed: `git push -u origin verifier-challenger-2026-11-20` ✓ (new branch)

## Checkpoint (Step 0)

- Name: MiniCheck-FT5 — `lytang/MiniCheck-Flan-T5-Large` (770M, Tang et al.,
  EMNLP 2024, arXiv 2404.10774).
- License: **MIT**, confirmed at download time from the model card metadata
  (`license:mit` tag + `cardData.license: mit` via `Huggingface_hub.model_info`).
  Allows research/portfolio use; full record in
  `projects/01-rag-agent/reports/verifier_challenger/license.md`.
- Revision pinned: `96eafd01cee2d16cf81aaa2fb226b14f422a37b3`.
- Download: 3,132,807,711 bytes (≈3.13 GB); weights sha256
  `41291881e13c6235ed47149cec903bee9493e45d9d7325587a9fa2e266c526c0`;
  HF cache only, nothing vendored.

## Split (Step 1, committed before any scoring)

- File: `projects/01-rag-agent/data/calibration/verifier_split.json`.
- Seed 42, stratified by label: 48 dev / 49 test per label (194 total).
- claims.jsonl sha256 recorded: `675ac742796a273f47c743148b9e33829e7de26ff4e8d68e170e980e885859bc`
  (claims.jsonl itself is regenerable and stays gitignored, per project
  convention; the recorded hash is a regeneration drift detector, asserted in
  tests — data-dependent tests skip on fresh clones where it is absent).

## Run (Step 3, once)

`uv run python scripts/verifier_challenger.py` — exit 0, runtime 120.49 s,
CPU fp32 batch size 1, 3 full passes over 194 claims (1 scoring + 2 flip).
0 of 194 claims span more than one evidence chunk (single-chunk assertion
held). Not re-run; no threshold or split change after results.

## Results

Threshold: **0.9410**, chosen on DEV only (max accuracy, ties → lower
threshold); DEV accuracy 0.9271 (n=96).

TEST (49 supported / 49 unsupported):

- **FA strict: 2/49 = 0.0408, Wilson 95% [0.0113, 0.1371]**
- **False rejection: 7/49 = 0.1429, Wilson 95% [0.071, 0.2667]**
- Sensitivity excluding the 3 `manual_review` TEST rows: **FA 0/46 = 0.0
  [0.0, 0.0771]** — both false acceptances are the uncertain
  (adjudication-pending) entity-swap labels; FR unchanged.
- Flip rate across two full CPU re-scores: **0/194 = 0.0** (max |Δscore| 0.0 —
  fully deterministic).

Baselines on the same TEST claims (from the committed hosted predictions,
not the non-reconciling aggregate):

- hosted qwen3:4b run 0: FA 16/46 = 0.3478 [0.2268, 0.4923], FR 0/49 = 0.0
- hosted qwen3:4b run 1: FA 21/46 = 0.4565 [0.3215, 0.5982], FR 1/49 = 0.0204
- hosted qwen3:4b pooled: FA 37/92 = 0.4022 [0.3078, 0.5043], FR 1/98 = 0.0102
  (covers 95/98 TEST ids; 3 TEST ids were never judged by the hosted runs)
- local qwen2.5:3b: FA 0.4433 [0.3752, 0.5136] on ALL 194 claims — per-claim
  verdicts are not committed, so it cannot be restricted to TEST.

## Gate (pre-registered), criterion by criterion

| Criterion | Result | Verdict |
|---|---|---|
| TEST FA rate ≤ 0.25 | 0.0408 | PASS |
| TEST FA Wilson UCB < 0.3269 | 0.1371 | PASS |
| TEST FR rate ≤ 0.10 | 0.1429 | **FAIL** |
| Flip rate ≤ 0.05 | 0.0 | PASS |

**Overall: FAIL.** Reading: at the DEV-optimal threshold the challenger
rejects 7 genuinely supported claims (all `entailed`, scores 0.777–0.934)
because the 2 accepted unsupported claims sit at 0.948–0.961 — the supported
and unsupported score distributions overlap (supported 0.777–0.982,
unsupported 0.020–0.961), so no threshold separates them cleanly.

Post-hoc analysis (NOT a gate change, reported for interpretation only):
other thresholds would pass both rate criteria on TEST — e.g. t=0.9271 gives
FA 0.0408 / FR 0.0816 — but selecting the threshold against TEST is exactly
what the fixed split forbids; the DEV rule legitimately chose 0.9410, and the
handoff forbids re-running with a different threshold.

## Gates (actual output)

- `uv run ruff check projects/01-rag-agent` → `All checks passed!`
- `uv run ruff format --check` on the 3 new files → `3 files already formatted`
- `uv run mypy projects/01-rag-agent/src projects/01-rag-agent/scripts` →
  `Success: no issues found in 32 source files` (pyproject emits a pre-existing
  `unused section(s)` config-drift note; not from this change)
- `uv run python scripts/check_headline_numbers.py` →
  `headline-numbers: 11 claims checked, 0 finding(s)` / `OK`
- `uv run python scripts/check_docs.py` → `check-docs: OK`
- `uv run pytest -q projects/01-rag-agent` → **186 tests passed, 0 failed**
  (dots-only run to [100%]); the command **exits 1 on the pre-existing libs
  coverage gate** (`ERROR: Coverage failure: total of 78 is less than
  fail-under=80`; `FAIL Required test coverage of 80.0 not reached. Total
  coverage: 78.19%`).
  This is a subset effect, not from this change: with the new test file
  `--ignore`d the coverage is byte-identical (78.19%, same 101 misses);
  `--cov=libs` needs tests from other projects to reach 80%. The full-suite
  run (`uv run pytest -q`, as CI runs it) is the coverage-relevant gate.

## Notes and open questions

- No hosted calls were made; hosted spend $0 (the one HF checkpoint download
  is the only network action, approved in Step 0). Verified live: the adapter
  init makes only HF-cache reads after download (the run log's HEAD/GET
  requests are `transformers` freshness checks against the pinned revision).
- One recipe nuance discovered while implementing: upstream MiniCheck ids
  3/209 are trained target ids, not vocabulary words that decode to
  "no"/"yes" — the adapter verifies the checkpoint behaviorally with a fixed
  probe pair (documented in the module docstring).
- nltk (upstream MiniCheck's sentence splitter) is not in `uv.lock` and not
  needed: every evidence text is a single chunk under the 500-word packing
  rule (asserted at run time and pinned by a test).
- Decision point for the owner (not started, per approval): Phase 2 is NOT
  approved and this FAIL gives it no support as-is. If the owner wants to
  pursue the challenger direction, the honest next measurements would be a
  DEV-legitimate threshold rule change proposed before any re-run (e.g.
  constrained accuracy: maximize accuracy subject to FR ≤ 0.10 on DEV), or
  a different challenger — both need a new handoff.
