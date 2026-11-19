# 03 NAB anomaly detection: investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- NAB, 9 series: IsolationForest touches 16/17 incidents with 1,609 raw alerts; one fit per series; no-skill = 16 seeded baselines; like-for-like the rank-average ensemble halves 66 budgeted pages to 35 at recall 0.604, range-F1 0.533; NAB score not reported (decision 2). Source: `projects/03-anomaly-detection/story.yaml`.
- Metrics file `projects/03-anomaly-detection/reports/metrics.json` holds per-detector blocks; IsolationForest shows pr_auc 0.1239, roc_auc 0.9158.
- Roadmap "next": re-run on TSB-AD with VUS-PR; report run count and fit variance.

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | The current benchmark for the task is TSB-AD: 1,070 series from 40 datasets, 40 algorithms (statistical, neural, foundation), VUS-PR named as the most reliable measure; Apache-2.0 code; leaderboard accepts pull requests (announced 2026-04-01). | SB (repo README read) | S06 |
| G2 | TSB-AD NeurIPS 2024 paper (Liu and Paparrizos). Fetch returned raw PDF; I did not read the text. Follow-ups cite 48-50 baselines depending on version. | SEC | S15 |
| G3 | Point adjustment inflates scores; a random score can look state of the art (Kim et al., AAAI 2022). We do not use PA; confirm in copy. | SEC (abstract) | S16 |
| G4 | VUS family definition (Boniol et al.). | SEC | S17 |
| G5 | A 2026 preprint (Lyu, arXiv 2607.11969 per search result) reports VUS-ROC gamed on 119 series where VUS-PR is not, and "even VUS-PR is gamed on NAB". This sits against TSB-AD's recommendation of VUS-PR. UNRESOLVED; I did not open the paper. | SEC | S18 |
| G6 | No current NAB leaderboard found for 2025-2026. | GAP | none |

## Candidate improvements
**A. Run VUS-PR (and VUS-ROC, range-F1) on a TSB-AD-U subset with the same detector families.**
- Method: install TSB-AD, run IsolationForest, LOF, OCSVM and the rank-average ensemble on a seeded subset of TSB-AD-U (for example 50 series), report VUS-PR with a bootstrap CI over series, plus run count. Output to a new path (for example `reports/tsbad_vuspr.json`).
- Reference: https://github.com/TheDatumOrg/TSB-AD (S06).
- Cost: compute only; datasets must be downloaded (owner OK; per-dataset licences differ, per README).
- Stop condition: any dataset licence blocks redistribution of results; or ensemble does not beat the best single detector, which is reported as is.

**B. Report run count and fit variance on the champion.**
- Method: refit IsolationForest and the ensemble over 20 seeds per NAB series; report spread of alerts, recall and range-F1. Closes the "single fit per series" disclosure.
- Reference: S18 (disclosure motive; SEC).
- Cost: compute only, under 1 day.
- Stop condition: spread larger than the ensemble-vs-single gap; then say the gap is not established.

**C. Add a one-liner/simple-baseline floor and explicit no-PA statement.**
- Method: add a rolling z-score or diff-threshold floor (Wu and Keogh one-liner idea, cited inside S16) alongside the seeded random floor.
- Reference: https://arxiv.org/abs/2109.05257 (S16).
- Cost: compute only, under 1 day.
- Stop condition: the simple floor matches the ensemble; report it.

**D. Cross-check VUS-PR against a second metric on NAB because of the Lyu conflict.**
- Method: report VUS-PR and range-F1 side by side and flag disagreement; do not rank by VUS-PR alone.
- Reference: S18 vs S06 (conflict).
- Cost: part of A.
- Stop condition: not applicable; it is a reporting rule.

## Ranked recommendation
1. A (TSB-AD VUS-PR subset) with D folded in.
2. B (run count and variance).
3. C (simple floor).

## Queries used (standard, 2026-11-18)
- "TSB-AD benchmark time series anomaly detection VUS-PR NeurIPS 2024 arXiv"
- "point adjustment anomaly detection evaluation flaw \"Towards a Rigorous Evaluation of Time-series Anomaly Detection\""
- "Lyu 2026 VUS-ROC inflation time series anomaly detection evaluation preprint"
- Fetched: github.com/TheDatumOrg/TSB-AD; proceedings.neurips.cc PDF (binary, unreadable here).
