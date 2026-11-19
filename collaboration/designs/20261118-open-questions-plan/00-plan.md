# Plan: cover the open questions from the overnight run

Date: 2026-11-18
Designer: Claude Code
Owner: amm-ds (decides options, commits, deploys)
Executor: Kimi Code (only after owner decisions below are recorded)
Status: DRAFT for owner decision. Nothing here is approved for execution.

Sources read: the four `OPEN_QUESTIONS.md` files (items 3, 4, 5, 7 of the overnight queue), `collaboration/reviews/20261119-overnight-report/00-report.md`, and `collaboration/reviews/20261118-live-confirmation/comparison.md`.

## 0. Correction to the earlier summary

My earlier reply labelled the blocked items "03-NLP" and "04-M5". Those were queue numbers placed on folder names. The correct mapping is:

| Queue item | Design folder | Blocked part | Open-question file |
|---|---|---|---|
| 3 | `20261117-04-nlp-review-fixes` | cascade paired interval | yes |
| 4 | `20261117-02-m5-review-fixes` | M5 reconciled global LightGBM | yes |
| 5 | `20261117-06-routing-review-fixes` | ALNS vs unhinted interval | yes |
| 7 | `20261117-12-tabular-review-fixes` | TabPFN-2.5 run (license) | yes |

Four blocked items, consistent with the four files. The morning report's header ("3 blocked") still needs fixing to four. This is part of the plan below.

## 1. Decisions per open question

### A. NLP cascade paired interval (04)

- **Blocker:** the 22 per-row LLM decisions are not committed. The aggregate fresh macro-F1 (0.9539265) can match several different decision patterns, so the bootstrap is not identifiable.
- **Options:** (1) re-run the cascade on hosted `kimi-for-coding` and persist per-row decisions; (2) accept "no measurable change" wording and document the limitation.
- **Recommendation:** option 2 now. The copy already reads "no measurable change (Δ macro-F1 +0.001)", which matches master-report correction 2. Option 1 is a new paid call with a $5 cap; it is only worth it if you want a positive claim about the cascade.
- **If option 1 is chosen later:** a new handoff must (a) cap spend, (b) persist per-row decisions with their prompt and model version, and (c) keep the paired interval computed offline from those committed records. Re-running will give new decisions, so the old aggregate will not match exactly.

### B. M5 reconciled global LightGBM (02)

- **Blocker:** no reconciliation output exists for the M5 full panel (`m5_full_v1`). Only the UCI hierarchy has one. Computing it means a reconciliation pass over 30,490 series, which is a multi-hour pipeline the overnight limits forbid.
- **Options:** (1) approve a one-off reconciliation evaluation of the committed test-origin global LightGBM forecasts (no retraining); (2) drop the reconciled-baseline row from the headline table.
- **Recommendation:** option 2 now. Keep decision 12 (full M5 rerun) open. Revisit option 1 only as a scoped job with a stated runtime.

### C. Routing ALNS vs unhinted interval (06)

- **Blocker:** the unhinted CP-SAT arm has status and runtime only. It produced no feasible plan on 56/56 instances at the 10 s budget, so there are no distances to compare.
- **Options:** (1) keep the null interval and the honest verdict "no feasible plan on any of the 56" (already in the README ladder, story table and `results.md`); (2) re-run only the unhinted arm with a longer budget or a different configuration.
- **Recommendation:** option 1. The verdict is already accurate. Option 2 is a new solve experiment, not a fix, so it needs its own handoff and a stated budget.

### D. TabPFN-2.5 for bike data (12)

- **Blocker:** `tabpfn==10.2.0` needs a one-time license acceptance on a Prior Labs account and a `TABPFN_TOKEN`. This is tied to your identity, so Kimi and I cannot do it.
- **Options:** (1) you accept the licence, create an API key, and export `TABPFN_TOKEN`; then the run is local; (2) use the older `tabpfn` v2 wheel, but its documented scope is 10,000 samples and the bike train split has 14,523 rows, which contradicts decision 11's stated reason; (3) drop the TabPFN challenger and keep the validation-tie wording.
- **Recommendation:** option 1 if you want the challenger; option 3 otherwise. Do not take option 2 without a documented subsample. Decision 11's reason depends on the 50,000-row support, so it should not be quietly changed.
- **Housekeeping:** the script lives at `/tmp/tabpfn_bike.py`, which may be cleared. Move it into the project (for example under `projects/12-*/scripts/`) in the same change that runs it.

## 2. Other open items (not in the four files)

| Item | Recommendation | Owner action |
|---|---|---|
| Morning report says "3 blocked", table lists four | Edit the header to four blocked items: 04 NLP, 02 M5, 06 routing, 12 TabPFN | Approve the edit; Kimi or I make it |
| Redeploy metrics-guard fix; re-check pages 02, 08, 11 on production | Owner deploys; I verify 11 (not covered in the report) | Deploy |
| 119 uncommitted paths mixing overnight and earlier work | Split into commits per queue item | Commit (owner only) |
| Provenance stamp replaces `_meta` results blocks; project 10 loses CI and CUPED detail its README cites | Separate fix: keep `_meta` on write | Approve as a new handoff |
| Held-out refusal messages are raw exception text (h19: `exponent too large`) | Optional copy fix in tool error mapping; the 6/6 count is correct | Decide if worth doing |
| Hillstrom Qini search file (`20261117-sota-research/13-…`) | I verify its sources online before the file is cited | Nothing from you |
| M5 WRMSSE values, citation | Stay open (you asked to leave them open) | None |

## 3. Proposed order, if you approve the recommendations

1. Owner records decisions A–D (and the other rows in section 2) in `collaboration/reviews/20261117-report-for-kimi/00-master-report.md` section 3.
2. Kimi applies only the recorded options: correct the morning report header, add the held-out refusal caveat to `comparison.md`, and drop the M5 reconciled row from the headline table. Gates as listed in the overnight brief.
3. I write a new handoff for the provenance-stamp fix (no code until approved).
4. If you choose D option 1, you accept the licence; then Kimi runs the TabPFN job under a one-hour compute limit, as the brief requires.
5. I verify the Hillstrom sources online and update the SOTA research file if needed.

## 4. Decisions needed from you

1. A: accept "no measurable change" (recommended), or approve a paid re-run with a $5 cap?
2. B: drop the reconciled M5 row (recommended), or approve a scoped reconciliation?
3. C: keep the null interval (recommended)?
4. D: accept the Prior Labs licence and provide `TABPFN_TOKEN` yourself, or drop the challenger (recommended if you do not want to create an account)?
5. Approve the morning-report header fix and the provenance-stamp handoff?

No hosted calls, no M5 rerun, no git mutations are part of this plan.
