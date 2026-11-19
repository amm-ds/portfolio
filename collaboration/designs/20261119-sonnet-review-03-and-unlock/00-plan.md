# Plan: Sonnet review and fixes for 03 figures and the phone-unlock card

Date: 2026-11-19
Designer: Claude Code
Reviewer: top-level Sonnet or Opus agent, using `collaboration/agents/00-init-senior-reviewer.md`
Executor: Kimi Code (owner runs it)
Owner: amm-ds
Status: DRAFT. Nothing approved for execution.

## 1. Items

| ID | Item | Where | Owner request |
|---|---|---|---|
| A | `eda_signals_overview` (03): signals on very different scales, so the smaller series cannot be read | `projects/03-anomaly-detection/src/anomaly_detection/evaluate.py` line 264 | Fix; review all other images for the same case |
| B | `nab_tune_surface` (03): y-axis labels still run into the plots at the sides on narrow screens | `projects/03-anomaly-detection/src/anomaly_detection/nab_tune.py` (`tune_figure`), converter in `apps/showcase-web/src/lib/plotlyToECharts.ts` | Fix; review all other images for the same case |
| C | Phone unlock card: the privacy note is too long | `apps/showcase-web/src/components/ChannelCards.tsx` lines 152–156 | Reduce considerably |

## 2. What I found (first read, to confirm in the review)

**A. Scale mismatch.** `eda_signals_overview` draws every signal on one shared y-axis (`yaxis_title="value"`). CPU, memory and latency have different units and ranges, so the series with the smallest range is flat. The fix is one panel per signal with its own y-axis and unit label, a shared x-axis, and the anomaly markers drawn on each panel. The figure height must grow with the panel count; keep the 360 px per-row minimum (decision 7).

**B. Side labels.** The H6 change moved `nab_tune_surface` to a 2×2 grid. The y-axis titles of the left and right panels still sit inside the plot area at narrow widths. Likely cause: the margin for the outer axis titles is set for one row, not for a 2×2 grid. Needs a measured check at 375 px before the fix. Kimi's H6 note records the converter bottom-band fix only; the side-label case was not in its acceptance check.

**C. Unlock copy.** The current note has four facts: what is stored, how long, that invalid values are not stored, and how to delete. It also says "This is not a security boundary." The request is to reduce it considerably. Proposed shorter copy (for the owner to choose):
- Option 1: "Shared contacts are kept for 30 days. Request deletion by email."
- Option 2: "Shared contacts are kept 30 days, then deleted. Request deletion by email." 

Keep the 30-day retention and the deletion route. Those are the parts a visitor needs to make a choice. "Not a security boundary" can go from the card; if the owner wants it kept, it needs its own short line. The card test `ChannelCards.test.tsx` checks the copy and must be updated with it.

## 3. Image audit (for the reviewer to complete)

The request is to check the other figures for the same two problems:
1. **Mixed scales on one axis** (a case of A): any figure that plots series of different units or ranges on one y-axis. Start with the `eda_*` and `*_overview` figures in all projects.
2. **Outer axis labels inside the plot** (a case of B): any figure with a y-title on a multi-panel layout, checked at 375 px.

Output: a table with figure id, project, problem, fix or "clean", and the screenshot path.

## 4. Sonnet review task

The reviewer should:
1. Confirm A and B from the code and, where possible, from the figure JSON in `reports/figures/`. Do not rerun models; regenerate figures only through their CLIs.
2. Run the image audit in section 3.
3. Write a review file under `collaboration/reviews/20261119-sonnet-review-03/` with: root cause for each item, the proposed fix, the acceptance check, and the audit table.
4. Write one handoff (`03-implementation-handoff.md`) for Kimi that covers A, B and C, plus any audit findings the owner approves.
5. Check the unlock-copy options with the owner before the handoff is final.

Constraints for the reviewer: no implementation edits; no git mutations; no hosted calls; no change to any headline number; use WebSearch (standard) only if a visualization guidance claim needs a source.

## 5. Handoff to Kimi (after the owner approves the reviewer's handoff)

Gates: `uv run pytest -q` for the 03 figure code; `uv run ruff check . && uv run mypy libs projects apps`; web `npm test`, `npm run lint`, `npm run build`; `uv run python scripts/check_headline_numbers.py`; `gen_static_registry.py --check` if a figure is renamed.

Acceptance:
- A: each signal in `eda_signals_overview` readable at 375 px and 1280 px; anomaly markers on the right panel.
- B: no y-axis label overlaps a plot at 375 px for `nab_tune_surface`; screenshots before and after.
- C: unlock note at most two sentences; retention and deletion route present; `ChannelCards.test.tsx` updated.
- Audit: every flagged figure either fixed or listed as clean with a screenshot.

Stop conditions: a fix would change a headline number; the figure needs a new metric; the 360 px minimum would change.

## 6. Issues from the pasted init report, checked

1. **Init file "missing".** The file is at `collaboration/agents/00-init-senior-reviewer.md` in this tree. The report's worktree may not have it; copy it in before starting the reviewer.
2. **"W3 is undefined".** W3 is defined in `collaboration/designs/20261118-next-wave/00-next-wave-plan.md`: the provenance-stamp fix (committed `_meta` blocks restamped on regeneration). It is not approved.
3. **TabPFN pin is in the repo, and it was not approved.** `projects/12-tabular-ml-lifecycle/pyproject.toml` line 18 has `tabpfn>=10.2.0`, and `uv.lock` pins `tabpfn-10.2.0`. This came from Kimi's overnight `uv add`. The owner had not chosen an option for decision D. **Owner decision needed:** revert the pin, or keep it and accept the licence risk. My recommendation is to revert until the licence reading is settled (research deltas §1).
4. **Init report path.** `collaboration/reviews/20261118-ai-init-report/` does not exist in this tree. If the report was written elsewhere, it is not part of this review.
5. **Provenance stamp and headline check.** The headline check exists (`scripts/check_headline_numbers.py`, 11 claims). Its gap is the two projects it does not cover (01, 04), as recorded in the second-pass review. The report's "nothing checks headline numbers" is out of date.
6. **Apps not reviewed.** Agreed: `agent-chat` and `document-intelligence` were covered only by the UI pass (H1–H8), not by a content review. Add them to the Sonnet review scope if the owner wants them.

## 7. Decisions for the owner

1. Revert or keep the `tabpfn>=10.2.0` pin in project 12 (item 3 above).
2. Pick the unlock copy: option 1 or option 2, or your own text.
3. Approve the Sonnet review task (section 4).
4. Decide whether the apps get a content review in the same pass.
