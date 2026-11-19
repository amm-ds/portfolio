# Sonnet investigation: summary

Date: 2026-11-19 (searches run 2026-11-18, standard mode only). Reviewer: Sonnet. Brief: `collaboration/designs/20261119-sonnet-investigation-brief/00-brief.md`.
Scope respected: no hosted calls, no implementation edits, no git mutations, no changes to committed records. No finding changes a headline number or a committed record, so no stop was triggered. Every proposal is a new experiment writing to a new path.

Labels: SB = source-backed (page fetched), SEC = secondary (snippet, abstract, blog), GAP = no source. Details and URLs in `99-sources.md` (7 SB, 58 SEC, 12 gap items).

## Ranked table (expected value per cost; best first)

| Rank | Project | Top gap | Best approach | Expected value | Cost | Verifiable offline | Main source |
|---|---|---|---|---|---|---|---|
| 1 | 10 Uplift | No single-protocol comparison; Qini/AUUC variant undefined | Rerun causal forest, T, X and two-model learners on the committed folds; Qini and AUUC with formula named, plus DR policy value across budgets | high | compute only, about 2 days | yes | S28, S29 (SEC) |
| 2 | 01 RAG agent | Judge not accepted (false acceptance about 0.44-0.45, kappa about 0.54); no warrant check | Offline claim-level checker calibrated on the committed 194-claim label set, then a warrant-strength contrastive set | high | compute only (A); hosted cap for B | yes (A), no (B) | S01 (SB), S52 (SEC) |
| 3 | 06 Routing | Solomon-100 gap not comparable to published tables; objective is vehicles-first | Add PyVRP as an in-repo arm on the same 56 instances; re-tabulate vehicle-first | high | compute only, 1-2 days; new dependency | yes | S02 (SB), S58 (SEC) |
| 4 | 03 NAB | Not on TSB-AD; single fit per series | VUS-PR on a TSB-AD-U subset with run count and seed spread | medium-high | compute only; dataset download | yes after download | S06 (SB) |
| 5 | 04 AG News | No selective-classification evaluation | Risk-coverage curve and AURC/AUGRC for the transformer on the fresh holdout | medium | compute only, under 1 day | yes | S19, S20 (SEC) |
| 6 | 09 Agentic | Single runs; no pass^k | k=3 live run with pass^1 and pass^3 and Wilson intervals | high | hosted, owner cap | no | S03, S05 (SB) |
| 7 | 13 Model serving | Load driver loop type unconfirmed; tails near knee | Open-loop constant-arrival-rate arm and p99 CIs from raw records | medium | compute only, 1-2 days | yes | S46, S47 (SEC) |
| 8 | 12 Tabular | Tie not tested across origins; TabPFN blocked on licence | Rolling-origin MLP vs LightGBM check; TabPFN only after owner licence decision | medium | compute only | yes | S07, S04 (SB) |
| 9 | 02 M5 | One origin, no interval on WRMSSE | Series-block bootstrap CI, then reconcile committed forecasts if stored | medium | compute only | yes (if forecasts on disk) | S11, S14 (SEC) |
| 10 | 15 Document intelligence | Live entity precision 0.524 and 7 synthetic documents; metric vs model unclear | Read-only error taxonomy of false positives, then entailment citation-support check | medium | reading only (A); compute (C) | yes | S05 (SB), S48 (SEC) |
| 11 | 14 agent-chat | 24/33 and 26/33 on two Kimi runs unexplained; no trial repeat | Transcript triage of failed cases, then offline citation-support grader | medium | reading only; compute | yes | S05 (SB), S48 (SEC) |
| 12 | 11 Data engineering | Warm-only headline, no spread or cold column | Cold-start timings and per-cell spread from the existing harness; version disclosure | medium | compute only, 1 day | yes | S36 (SEC) |
| 13 | 07 NYC mobility | Persistence-only baseline; static band | Seasonal-with-weather baseline row; adaptive conformal band by borough | medium | compute only | yes | S25 (SEC) |
| 14 | 08 LLM serving | Saturated quality guardrail | Harder fixed quality set with Wilson intervals; goodput view from raw records | medium | compute (local inference) | yes | S41 (SEC) |
| 15 | 05 Churn | Fairness and rollout blocked on owner data | Static subgroup audit on committed OOF predictions, labelled diagnostic | low-medium | compute only | yes | S27 (SEC) |

Ranking basis: expected value to the public claims divided by cost and by risk to existing claims. Rows 6 and 15 are ranked by cost and the owner-held blockers, not by merit.

## Unresolved conflicts (not decided here)

1. **PyVRP table (06).** Kimi W9 reading (VRPTW: PyVRP 0.40%, HGS-DIMACS 0.32%, DIMACS 0.29%) vs earlier snippet reading (0.27%, 0.28%, 0.16%). My page fetch of arXiv 2403.13795v2 shows the first set in the VRPTW table (Table 2) and the second set as the "gap of mean" column of the CVRP table (Table 1; HGS-2012 0.28%, HGS-CVRP 0.16%, PyVRP 0.27%). That suggests two different tables, not two readings of one. The fetch tool summarises the page and I did not open the PDF, so the owner must close the item; do not cite PyVRP numbers until then.
2. **VUS-PR reliability (03).** TSB-AD names VUS-PR the most reliable measure (SB, repo README). A 2026 preprint (Lyu, search-reported, not opened) says VUS-PR is also gamed on NAB. Unresolved; report VUS-PR beside range-F1.
3. **TabPFN-2.5 licence (12).** Model card: license v1.1, research and limited internal evaluation allowed, no commercial or production use of model, derivatives or outputs, with "competitive benchmarking for procurement" listed as prohibited (SB). A search snippet quoting the paper's section 6 says v1.0 (SEC; section 6 not read). Whether a public portfolio page is covered is the owner's decision.
4. **M5 rolling origins (02).** The 2026-11-19 gap analysis called rolling origins "the M5 standard once verified". I could not verify it (GAP). Do not state it.
5. **TSB-AD algorithm count (03).** 40 algorithms (repo README, SB) vs 48 or 50 baselines in follow-up papers (SEC). Version-dependent; cite the README count with its date.
6. **Qini and AUUC definitions (10).** Implementations differ (SEC). State the formula with any number.
7. **Hybrid retrieval benefit (01).** Blog evidence conflicts (hybrid sometimes below dense-only); no primary table read (GAP).
8. **agent-chat eval denominator (14).** `evals-kimi-for-coding.md` says 108/108 assertions; other reports have 33. Unexplained from committed files.
9. **02 probabilistic scope.** `probabilistic.json` and a toy `reconciliation.json` exist; I could not establish their panel scope, so the earlier statement "no interval exists" refers to the WRMSSE headline only.

## Owner decisions this report touches (none made here)
PyVRP table (item 1); TabPFN licence (item 3); hosted caps for 01B, 04B, 09A, 14A, 15D; new dependencies (PyVRP, causal forest library, TSB-AD); dataset downloads (TSB-AD, additional TLC months).

## Files
`01-rag-agent.md` ... `13-model-serving.md`, `14-agent-chat.md`, `15-document-intelligence.md`, `99-sources.md` in this folder.
