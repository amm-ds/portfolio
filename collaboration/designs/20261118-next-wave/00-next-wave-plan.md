# Next wave: current state, open questions, refinements

Date: 2026-11-18
Designer: Claude Code
Owner: amm-ds (approves, commits, deploys, runs Kimi)
Executor: Kimi Code (only after the owner approves each wave item)
Status: items W1, W2, W4, W5, W6, W9 APPROVED by owner for Kimi execution (2026-11-18). W3, W7, W8, W10, W11, W12 NOT approved.
Inputs: experiment review index (`collaboration/reviews/20261117-experiment-review/00-index.md`), overnight report (`collaboration/reviews/20261119-overnight-report/00-report.md`), open-questions plan (`collaboration/designs/20261118-open-questions-plan/00-plan.md`), research deltas (`collaboration/reviews/20261117-sota-research/14-research-deltas-2026-11-18.md`).

## 1. Current state by project

Status key: **clean** (queue done, no open item), **open** (an item needs owner or Kimi work), **blocked** (waiting on a decision).

| # | Project | Current result (as committed) | Status | What is still open |
|---|---|---|---|---|
| 01 | RAG agent | Stress set 5 of 30 failing (was 11 of 30); judge model and ragas version committed | open | Generation grounding is the weak point; no warrant-strength check (research delta 6) |
| 02 | M5 demand forecasting | Pooled LightGBM 0.6161 vs seasonal-naive 0.8929 (−31.0%), one scored test origin, no bootstrap interval | blocked | Reconciled LightGBM row (no committed output); WRMSSE values unverified (research delta 2) |
| 03 | NAB anomaly | Split raw and budgeted results; "NAB official score not reported"; precision CI [0.231, 0.811] | open | Number of runs not in the card (research delta 4) |
| 04 | NLP AG News | Cascade reported as "no measurable change (Δ macro-F1 +0.001)"; int8 table split | blocked | Paired interval needs per-row LLM decisions, not committed |
| 05 | Churn | Cost weights (fp 1.0 / fn 5.0) confirmed in config; holdout-isolation test added | clean | none |
| 06 | Routing VRPTW | Mean gap CI [3.22, 5.28]% (ALNS-hinted); PyVRP mean gap −3.71% vs committed refs; unhinted arm has no feasible plan | blocked | ALNS-vs-unhinted interval null; PyVRP table instance mismatch to check (research delta 3) |
| 07 | NYC mobility | Rounding confirmed (−28.3%); coverage outliers in headline | clean | none |
| 08 | LLM serving | Quality table labelled "saturated smoke check"; cost $0.12 traced | clean | Electricity assumptions stay on the card (cross-cutting 2) |
| 09 | Agentic workflows | Live held-out run: 13/13 answers, 6/6 refusals (h19 is the calculator guard error), 19/19 budgets vs legacy 5/6, 18/19, 12/19; spend $0.094112 of $5 | open | Reliability wording: single run per task; pass^k not measured (research delta 5) |
| 10 | Uplift | 42,613 of 64,000 analysed; "revenue minus send cost" in headline | open | "profit" still in story body, captions, MODEL_CARD, portfolio.yaml (out of handoff scope) |
| 11 | Data engineering | Spread from recorded repeats; negative parity test | clean | none |
| 12 | Tabular | Validation tie −0.18 [−1.71, +1.21]; champion label removed | blocked | TabPFN-2.5 run: licence and token; licence type needs owner reading (research delta 1) |
| 13 | Model serving | p95 2.0 ms, p99 2.2 ms, n = 300 per cell; 6.5 GB image | clean | none |

Cross-project open items:
- Morning report says "3 blocked"; the table lists four (NLP, M5, routing, TabPFN). Fix the header.
- Provenance stamp replaces `_meta` results blocks on commit (project 10 metrics lost CI and CUPED detail its README cites). Not fixed.
- Metrics-guard fix is not on production. Owner deploys; page 11 is not in the browser check list.
- 119 uncommitted paths. Owner commits, split by queue item.
- Cross-cutting from the index: headline numbers drift across short copy, README and story (finding 5); interval-method definition not yet in `docs/engineering/` (finding 3).

## 2. Proposed next-wave items

Ordered by risk. Items 1–4 need no hosted calls and no paid budget.

| Wave item | Projects | Type | Why now | Stop condition |
|---|---|---|---|---|
| W1 | cross-project | copy/report fix | Morning report says 3 blocked, table says 4; held-out comparison should note h19 is a guard error | none |
| W2 | 10 | copy fix | "profit" left in story body, captions, MODEL_CARD, portfolio.yaml; truth-in-copy rule | any remaining claim that cannot be traced |
| W3 | cross-project | code fix (needs handoff) | Provenance stamp drops `_meta` results blocks; committed numbers lose their CI and CUPED detail | fix changes any headline number |
| W4 | cross-project | check + test | Headline numbers drift; add a grep check that each headline number matches its committed metrics file | check flags more than the known drift |
| W5 | cross-project | docs | Define the interval method once in `docs/engineering/` and link from cards | none |
| W6 | 03 | copy + card | Add number of runs and single-run disclosure to the card (research delta 4) | none |
| W7 | 01 | eval, needs cap | Add a warrant-strength check and a judge calibration set (research delta 6). Hosted judge calls: owner-approved cap, $5 suggested | spend reaches $4 |
| W8 | 09 | eval, needs cap | Multi-trial run for pass^k (k≥3) on the held-out set, or state single-run wording. Hosted calls: owner-approved cap, $5 suggested | spend reaches $4 |
| W9 | 06 | check | Read the 2403.13795 benchmark table and resolve the instance-name mismatch before any PyVRP number is cited | table mismatch confirmed |
| W10 | 12 | decision | Licence reading for TabPFN weights and the 10.2.0 version check (research delta 1). Owner decides before any run | owner decision needed |
| W11 | 02 | decision | Approve or drop the reconciled M5 row (open-questions plan, B) | owner decision needed |
| W12 | 04 | decision | Accept "no measurable change" (recommended) or approve a paid re-run | owner decision needed |

Not in the wave: M5 full panel rerun (decision 12, stays open), NAB official score (decision 2), HGS on routing (decision 1 scope), redeploy (owner).

## 3. Decisions the owner needs to make

1. W10: which TabPFN licence reading applies to a public portfolio? Read the Prior Labs licence text first. If commercial use is restricted, drop the challenger.
2. W11, W12: approve the recommended options from the open-questions plan.
3. W7, W8: approve a hosted budget (suggested $5 cap each, on `kimi-for-coding`), or drop the item.
4. W3: approve the provenance-fix handoff. It changes committed results files, so the owner reviews the diff before commit.
5. Deploy the metrics fix and check page 11 on production.

## 4. How the next wave runs

1. Owner approves wave items (section 3).
2. Kimi takes approved items in the order above, each with its own gates from the overnight brief.
3. Each item writes a morning-style report row. Blocked items get an `OPEN_QUESTIONS.md`.
4. Claude reviews the results and updates the experiment cards' status here.

Paste-ready message for Kimi is in `01-kimi-next-wave-message.md` (drafted, not sent).
