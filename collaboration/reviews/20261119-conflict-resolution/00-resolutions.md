# Conflict resolution: seven open items from the Sonnet investigation

Date: 2026-11-18 (session date; filed under the 20261119 series). Reviewer: Sonnet, top-level. Mode: standard web search and page fetch only; no hosted model calls, no implementation edits, no git mutations, no committed record changed, no number changed.
Labels: SB = source-backed (page fetched and read; the fetch tool summarises long pages), SEC = secondary, GAP = no source. Sources and queries: `99-sources.md`.

| # | Item | Verdict |
|---|---|---|
| 1 | PyVRP table (06) | Resolved |
| 2 | VUS-PR on NAB (03) | Partly resolved |
| 3 | TabPFN-2 licence (12) | Partly resolved (correction to earlier reading) |
| 4 | M5 rolling origins (02) | Unresolved |
| 5 | Agent-chat denominator (14) | Resolved |
| 6 | TSB-AD algorithm count (03) | Partly resolved |
| 7 | Qini / AUUC variants (10) | Resolved (literature part SEC) |

## 1. PyVRP table (06): resolved

There is no conflict between readings; the numbers belong to two different tables in arXiv 2403.13795v2 (SB, page fetched 2026-11-18, https://arxiv.org/html/2403.13795v2).

| Table | Caption | Family | PyVRP | HGS | Other | Column |
|---|---|---|---|---|---|---|
| Table 1 (summary) and Table 4 (per instance) | "Benchmark results for CVRP on X instances of Uchoa et al. (2017)" | CVRP, X instances | 0.22% mean gap; 0.27% gap of mean | HGS-2012 0.21% / 0.28%; HGS-CVRP 0.11% / 0.16% | BKS 63106.7 mean cost | "gap of mean" = 0.27, 0.28, 0.16 |
| Table 2 (summary) and Table 5 (per instance) | "Benchmark results for VRPTW on 1000 customer instances of Homberger and Gehring (1999)" | VRPTW, Gehring-Homberger 1000 customers (60 instances) | 0.40% mean gap; 0.46% gap of mean | HGS-DIMACS 0.32% / 0.37% | DIMACS reference 0.29% / 0.31% | "mean gap" = 0.40, 0.32, 0.29 |

So: 0.40 / 0.32 / 0.29 is the 1000-customer VRPTW table (mean gap column). 0.27 / 0.28 / 0.16 is the CVRP X-instance table, in the "gap of mean" column; the same table's mean-gap column is 0.22 / 0.21 / 0.11. The paper has no Solomon 100-customer table. This agrees with the committed `table_check` block in `collaboration/designs/20261117-06-routing-review-fixes/pyvrp-solomon-results.json` (dated 2026-11-19, independently reaching the same reading from instance names).

Local citations of PyVRP numbers (checked by grep): `projects/06-routing-optimization/README.md`, `story.yaml`, `DESIGN.md`, `reports/`, `apps/showcase-web/src`, `docs/projects`: no PyVRP result and no 0.40 / 0.27 figure is cited. The only PyVRP mentions are roadmap and audit text (`docs/audits/2026-10-15-external-audit-response.md`, `docs/audits/2026-11-12-portfolio-website-evaluation.md`). The JSON itself holds a local run (PyVRP 0.14.1, 15 s per instance, seed 42, 56 Solomon instances, mean_gap_pct -3.7145, mean_n_vehicles 8.62), which is a record and is not cited anywhere public. Note the JSON's own validation says per-route extraction is advisory and its `consequence` field says the local run is not comparable to the paper headline.

Caveats: the paper's "mean gap" for 1000-customer VRPTW uses a 2-hour-per-instance, 10-seed protocol (per the JSON `table_check`, SEC for that detail); our Solomon-100 setup differs in size, time and objective (the repo gap is distance gap to best-known, with a separate vehicle delta). A negative local gap (-3.71%) against a distance-only best-known reference reflects the vehicles-first versus distance-only mismatch and must not be quoted as "better than best-known".

Owner decision still needed: whether any PyVRP number may be cited at all. If yes, cite the right table with its benchmark family, and never next to the Solomon ladder as a comparison. The investigation's "do not cite until resolved" gate can be lifted for the identification; the citation gate itself remains the owner's.

## 2. VUS-PR on NAB (03): partly resolved

Preprint located: Zongye Lyu, "Did We Actually Fix It? An Independent Adversarial Stress-Test of Post-Point-Adjustment Evaluation Metrics for Time-Series Anomaly Detection", arXiv:2607.11969 (v2, 19 Jul 2026), https://arxiv.org/abs/2607.11969 (SEC: abstract page read through the fetch tool's summary; full text not read).

Main claim: replacement metrics for point-adjustment are tested against no-skill (random or adversarial score) generators on UCR (primary) plus SMD, SMAP, MSL, NAB, PSM. Under a single honest run, none is gamed on the six benchmarks. Under best-of-N reporting, affiliation-F1 and ROC-based metrics inflate sharply; PR-based metrics (VUS-PR) and PA%K stay roughly flat near anomaly prevalence, with "the lone exception NAB at large N". The recommendation is to report single-run scores or disclose N and to prefer PR-based metrics.

Correction to the investigation's wording: the earlier text ("VUS-PR is gamed on NAB") came from search-engine mirrors of an earlier version and overstates it. The v2 abstract reads as: VUS-PR resists nearly everywhere; on NAB it inflates only under large-N best-of-N selection. The two readings differ on version and exact series counts (119 in the mirror, 131 in the v2 summary); I did not resolve those counts.

Applicability: the six benchmarks do not include TSB-AD. The finding is about NAB (and metrics in general under best-of-N). It applies to our TSB-AD-based plan only through the reporting rule: disclose how many runs, seeds or configurations were tried before the number was kept. It does not show that VUS-PR is unreliable on TSB-AD (SEC; TSB-AD absent from the test set per the abstract summary).

Owner decision still needed: (a) the repo's NAB decision 2 (official score not reported) is unaffected; (b) whether to adopt "report VUS-PR with N disclosed and range-F1 beside it" in the TSB-AD plan; (c) someone should open the PDF to settle the version and count discrepancy if the preprint is to be cited publicly.

## 3. TabPFN licence version (12): partly resolved, with a correction

Findings (SB, fetched 2026-11-18):
- TabPFN-v2-clf model card tag `priorlabs-1-1`; description: "Prior Labs License (Apache 2.0 with additional attribution requirement)" (https://huggingface.co/Prior-Labs/TabPFN-v2-clf). TabPFN-v2-reg card carries the same tag `priorlabs-1-1` (https://huggingface.co/Prior-Labs/TabPFN-v2-reg).
- `LICENSE.txt` for v2-clf (https://huggingface.co/Prior-Labs/TabPFN-v2-clf/blob/main/LICENSE.txt): "Prior Labs License", version 1.1, May 2025; Apache 2.0 plus Section 10 attribution ("Built with PriorLabs-TabPFN" on distribution of the work, weights or a product containing them; derived distributed models must be named starting with "TabPFN"). Commercial use is not restricted. Internal testing does not trigger the attribution duty. The LICENSE.txt of v2-reg was not opened separately (the model card tag is identical); the raw `/LICENSE` path I first tried returned 404.
- Scope limits on samples: neither card states a maximum number of samples or features; both say "not designed for very large datasets" and describe the model as suited to small tabular data (SB for the cards; the 50,000-sample and 2,000-feature figures in the investigation belong to TabPFN-2.5, S07, not to TabPFN-2).

Correction: the earlier "v1.1" reading was right for the version label but conflated two different licences. The TabPFN-2 weights are under Prior Labs License v1.1 (Apache-based, commercial use allowed, attribution required). The TabPFN-2.5 weights (S04) are under a separate document named "tabpfn-2.5-license-v1.1" that, per the investigation's fetch, restricts commercial and production use. Same version number, different terms. The blocker in the investigation applies to 2.5, not to TabPFN-2. I did not re-read the 2.5 licence here, so that half stays SEC from the earlier fetch. The "v1.0 in paper section 6" snippet is unresolved and probably describes the 2.5 paper or an earlier TabPFN-2 licence; not checked.

Owner decision still needed: choose TabPFN-2 (attribution only) or TabPFN-2.5 (restrictive); record the licence file hash or retrieval date in the project; if TabPFN-2 is used on a public page, the "Built with PriorLabs-TabPFN" attribution applies to distribution, so the owner should decide whether the public page counts. The licence text is not legal advice.

## 4. M5 rolling origins (02): unresolved

I could not read the paper. The IJF paper (Makridakis, Spiliotis, Assimakopoulos, DOI 10.1016/j.ijforecast.2021.11.013) was only reachable as an abstract and listing (SEC), and the preprint PDF fetched from a Columbia-hosted copy was a compressed PDF the tool could not extract (the file is saved at `/Users/alejandro/.claude/projects/-Users-alejandro-work-portfolio/48d46ef9-c310-450a-accb-449e4a02945b/tool-results/webfetch-1795033886549-5n3j53.pdf` for the owner or a PDF-capable tool). Searches returned nothing on a rolling-origin protocol. From the abstract and listing only: 42,840 series, 5,507 accuracy teams, point forecasts. Status of the claim "rolling origin is the M5 standard": GAP, do not state it. My recollection is that M5 used a fixed 28-day validation window and a fixed 28-day evaluation window rather than rolling origins; this is unverified recollection, not a sourced claim.

Owner decision still needed: whether to read the paper (or the Kaggle M5 guidelines) and settle this, or keep the article's wording to "single origin, as a limitation" without asserting a standard. Decision 12 (no full M5 panel rerun) is unaffected.

## 5. Agent-chat evaluation denominator (14): resolved

Counts from the committed reports (local files, source-backed):

| Report | Model | Data rows | pass | FAIL | Footer |
|---|---|---|---|---|---|
| `apps/agent-chat/reports/evals-kimi-for-coding.md` | kimi:kimi-for-coding | 108 | 108 | 0 | "Passed 108/108 grader assertions." |
| `apps/agent-chat/reports/evals-kimi-k3-256k.md` | kimi:k3-256k | 33 | 26 | 7 | "Passed 26/33" |
| `apps/agent-chat/reports/evals-kimi-k3.1-pro.md` | kimi:k3.1-pro | 33 | 24 | 9 | "Passed 24/33" |

(The 109 raw row counts include the header; 108 and 33 are data rows.) The kimi-for-coding report has 16 distinct cases, each run 3 times (`[n/3]` suffix) = 48 executions, 108 grader assertions. `apps/showcase-web/src/lib/agentChatEvalSummary.ts` agrees: cases 16, repetitions 3, executions 48, totalAssertions 108, passed 108; by kind answer 63, refuse 18, tool_choice 27. The two K3 reports are single-repetition runs of 16 cases with 33 grader assertions each (no `[n/3]` suffix).

Reconciliation: 33 and 108 are different units, not a conflict. 33 = assertions in one pass over 16 cases; 108 = assertions across three repetitions of a (slightly different) grader set for kimi-for-coding. Per-case grader counts are not identical across reports (kimi-for-coding gives calc-percent two graders, K3 reports give three; compare per-case rows before putting them in one table). 33 x 3 = 99, not 108, so the 108 cannot be the 33-assertion suite tripled; the grader sets differ. I did not explain why the kimi-for-coding run has a different grader set (possible suite version change, not checked).

Which to state: the article already states it correctly (`apps/showcase-web/src/pages/AgentChatArticle.tsx` lines ~117, 369, 386: "108/108 assertions ... 16-case suite repeated three times ... not 108 independent tasks"). Keep that. When the K3 runs are mentioned, state them as 26/33 and 24/33 grader assertions, single repetition, and say explicitly that they are a different model, a different repetition count and a different grader set from the 108.

Owner decision still needed: whether to mention the K3 failures in the article (they show non-trivial failures that the 108/108 hides), and whether the grader-set difference needs a committed explanation.

## 6. TSB-AD algorithm count (03): partly resolved

- NeurIPS 2024 D&B abstract (https://nips.cc/virtual/2024/poster/97690): "40 detection algorithms" (SEC: poster page, abstract text only; PDF not read). Repo README (https://github.com/TheDatumOrg/TSB-AD): overview says 40 algorithms and 1070 series from 40 datasets; the README tables list 35 methods (18 statistical, 12 neural, 5 foundation-model), so even the README does not reconcile 40 vs 35 (SB for the tables; the fetch tool counted them, so recount before use). The README does not say which paper version its tables match.
- The investigation's "48 or 50" came from follow-up papers (SEC) and is not a TSB-AD count; it is probably the TSB-AD leaderboard after community submissions opened (changelog: leaderboard opened to community submissions 2026-04-01) or other papers' own method counts. Not verified.

For the version we would use: pin a git commit or PyPI release of TSB-AD and count the detectors that code actually exposes. Until then state "the TSB-AD paper reports 40 algorithms" and do not state a repo count.

Owner decision still needed: which TSB-AD version (paper release vs current repo commit) to pin; which subset of detectors we run (our plan runs a subset in any case, so the count belongs in the benchmark description, not in our results).

## 7. Qini and AUUC variants (10): resolved

Literature (SEC; search results and documentation snippets, Radcliffe's 2007 paper not read, GAP):
- Qini curve: incremental conversions at targeted fraction f, `n_t(f) * (rate_treated(f) - rate_control(f))`, with the random baseline as the straight line to the full-population point.
- Qini coefficient (Radcliffe style): area between the Qini curve and the random line; often normalised by the area between random and optimal curves, so the maximum is 1.
- AUUC: raw area under the uplift curve, normally unnormalised. The uplift curve is a rescaled Qini curve (factor (N_t + N_c) / N_t in scikit-uplift terms). scikit-uplift changed what `qini_auc_score` returns between versions (raw area in v0.1.1, normalised in later docs), so naming alone does not fix the formula. UpliftBench (arXiv 2608.00915) reports cases where Qini and AUUC rank models differently.

Project code (local, source-backed): `projects/10-uplift-experimentation/src/uplift_experimentation/qini.py`. `qini_points` builds inc(f) = n_t(f)*(rate_t - rate_c) over rank-sorted slices, with the empty-slice convention documented in the docstring. `qini_coefficient` = trapezoid area under the model curve minus `inc_all/2`, the area under the random line. This is an unnormalised Qini coefficient (area between curve and random line, units conversions x fraction), not Radcliffe's normalised variant and not an area-under-curve-only AUUC. `projects/10-uplift-experimentation/DESIGN.md` line 22 states the same decision ("Unnormalized Qini/AUUC ... per-arm summary labels this AUUC"), and `MODEL_CARD.md` line 53 uses "Qini/AUUC contrasts". So the repo's "AUUC" label for per-arm values is the same quantity as the Qini coefficient, not scikit-uplift's AUUC (area under the raw curve without subtracting the random line). Any outside comparison must therefore say "unnormalised Qini coefficient (area above the random line), conversions x fraction", and cannot be compared to normalised literature values (for example Qini 0.0346 or 0.3759 in S28, S30) without recomputation.

Owner decision still needed: keep the unnormalised definition and the AUUC label (document it beside each number), or add a normalised Qini column as a new output (new path, not an edit to a record). I recommend naming the formula in the copy; no number changes.

## Owner decisions, consolidated
1. PyVRP: may any PyVRP number be cited, and where (item 1).
2. VUS-PR: adopt "report N" rule; open the PDF for the version and count discrepancy before citing publicly (item 2).
3. TabPFN: TabPFN-2 vs 2.5; attribution handling (item 3).
4. M5: read the paper or leave the claim out (item 4).
5. agent-chat: whether to mention the K3 runs and explain the grader-set difference (item 5).
6. TSB-AD: version pin (item 6).
7. Qini: keep the unnormalised definition and state it beside the number (item 7).
