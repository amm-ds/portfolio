# Message for Kimi — execute grade pass 5

Read `collaboration/reviews/20261126-grades-pass-5-close-to-9/02-execution-plan.md` in full before starting. It supersedes the phase 3–4 wording in `00-plan.md`.

Approved in this round:
- Project 12 MLP rerun (Phase 3), CPU only, in scratch.
- Project 01 hosted judge (Phase 2), cap $2.00.
- Overall hosted cap $5.00 (spent $0.41).

Not yet approved: promoting v2 as the project 12 headline. Stop after Phase 3 and wait for the owner.

Rules:
- Work in the working tree on `wave8-articles-truthfulness-2026-11-25`. No push, deploy, or merge.
- No model co-author trailers.
- Do not touch the gitignored `projects/08-inference-serving/data/bench_run_repeat.json`.
- Do not use the old scratch E12 numbers. They are not valid.
- Stop and report on any failed gate, spread over 0.10 MAE, or spend past the cap.

Order:
1. Phase 1 — read E9's result; commit only if its reproduction gate passed.
2. Phase 2 — project 01 `final_v4` and hosted judge, cap $2.00.
3. Phase 3 — project 12 scratch: gate 1 (v1 reproduces 25.4316 and 25.3732), then three variant MLP runs, spread rule, seasonal naive check (expect 72.98). Write `phase-3-result.md`. Stop.
4. Phase 4 only after the owner approves Phase 3.
5. Phase 5 — copy and figure close-out.
6. Phase 6 — full gate set, record exit codes.
7. Phase 7 — commits and the final 14-project grade table.

Report back after each phase: result file path, commit hashes, gate exit codes, spend, and any number that changed.
