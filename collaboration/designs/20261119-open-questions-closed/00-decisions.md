# Decisions closing the open questions (recommendations adopted)

Date: 2026-11-19
Decided by: owner (amm-ds), who asked for recommendations to be adopted
Recorded by: Claude Code
Status: decided. Items marked **Q1** go into the approved Q1 copy handoff. Items marked **Figure** need a regeneration through the project's own CLI.

Spend rule (new): any hosted judge or model run under this plan is capped at **$3** in total, on the cheapest approved model (`kimi-for-coding`, the model the owner approved on 2026-11-18). Stop at $2.50 and report.

## Earlier open questions (from the overnight run)

| Item | Decision | Why |
|---|---|---|
| 04 NLP cascade paired interval | Accept "no measurable change" wording. No re-run. | Per-row decisions were never committed; a re-run would not reproduce them. |
| 02 M5 reconciled global LightGBM row | Drop the reconciled row from the headline table. Keep decision 12 (no full M5 rerun). | No committed reconciliation output for the M5 panel. |
| 06 ALNS vs unhinted interval | Keep the null interval and the verdict "no feasible plan on any of the 56 instances". | The unhinted arm has no distances. A longer-budget run is a separate experiment, not a fix. |
| 12 TabPFN-2.5 challenger | Superseded: the TabPFN-2 route is approved under the Prior Labs License v1.1 (attribution required). Handoff in `collaboration/designs/20261119-tabpfn2-challenger/`. TabPFN-2.5 and later are not used. | Licence text reviewed: no commercial-use restriction in v1.1. |
| Provenance stamp (W3) | Not closed here. Stays a separate handoff, to be written after Q1. | It changes committed results files, so it needs its own diff review. |

## P2 open questions (8 items)

1. **03 `threshold_sweep` numbers.** Decision: use the committed figure values, "17 of 120 flags hit real incidents, 14.2% precision". Remove "115 flags" and "14.8%". **Q1** (story caption and Conclusions body).
2. **06 "8 published references".** Decision: count from the committed table. ALNS has negative gaps on 5 instances in `reports/results.md` (6 counting `alns_fleet`). Rewrite every "8 references" to "5 instances" and name the table. Keep the 8-solver ladder claim, which is a different count. **Q1**.
3. **09 `short_version` live claims.** Decision: rewrite to what the committed comparison shows. "Live held-out run (2026-11-19): 13/13 answers; 6/6 refusals counted under the live grader, with h19 a calculator-guard error; 19/19 budgets." Link `collaboration/reviews/20261118-live-confirmation/comparison.md` from the card. The project's `reports/kimi-for-coding/metrics.json` 5/6 figure stays as the legacy recorded run. **Q1**.
4. **09 "8 unplanned calls".** Decision: remove the sentence. No committed artifact supports it. **Q1**.
5. **13 three unverifiable numbers.**
   - "up to 15%" ONNX lead: change to 13.8% at the c64 throughput cell, and say p50 medians differ by ≤4%. **Q1**.
   - "3.3 GB CUDA stack" and "12.8 GB earlier build": remove. **Q1**.
   - "~20%" noise threshold on the slope caption: remove. **Q1**.
6. **10 figure annotation and +69% vs +70%.**
   - `reports/figures/profit_frontier.html` shows $6,698; committed metrics and story show $6,838. Decision: regenerate the figure through `evaluate.py` so the annotation reads $6,838. **Figure**.
   - Use "+70%" everywhere (2,812 / 4,026 = 69.9%, which rounds to 70%). **Q1**.
7. **12 mandated-text deviations.**
   - Card 3 title is 8 words. Decision: shorten to "Gap to the floor holds under resampling." **Q1**.
   - Card 2 restates 25.4 vs 83.2. Decision: keep (owner mandated the wording).
   - "See research deltas" pointer dangles inside the public project. Decision: replace with "TabPFN-2 challenger pending; see the project's README." **Q1**.
8. **Numbers traced only to design docs.**
   - 02 spike-capture (0.845/0.839, 0.621/0.601): remove from story and cards; keep in `DESIGN.md`. **Q1**.
   - 04 ECE pair 0.0360 → 0.0227 and "37% cut": remove from the roadmap card and story body; keep in `DESIGN.md`. **Q1**. The card "Cut calibration error with one temperature" becomes "Calibrated probabilities with one temperature" with no number.
   - 11 "tracing made pandas's group-by 4x slower": remove. **Q1**.

## Consequences for Q1

Q1 now includes these copy and figure changes in addition to the milestone rewrites. The rule stays: no headline number changes except where a committed artifact contradicts the copy, and every such change is listed with its file path.

## Gates after Q1

- `uv run python scripts/lint_story_language.py`, `scripts/check_docs.py`, `scripts/check_short_copy.py --check`, `scripts/gen_story_short.py --check`, `scripts/check_headline_numbers.py`.
- Web gates after any change to `storyShort.ts` or roadmap rendering.
- Figure regeneration for 10 through its CLI, then the headline check again.
- Full `uv run pytest -q`, re-run from scratch, and the coverage figure recorded once.
