# Brief for a top-level Sonnet investigation: where each experiment can be improved

Date: 2026-11-19
Owner: amm-ds
Agent: Sonnet (top level). Read `collaboration/agents/00-init-senior-reviewer.md` first; its rules apply in full.
Mode: investigation and recommendation. No implementation, no git mutations, no deploys. Hosted model calls: none in this brief.

## Purpose

Find, for each experiment (01–13) and each app (agent-chat, document-intelligence), where the work can be improved or refined. For each one: current state, the gap to the state of the art, the approaches that would close it, and the references that support each approach.

This feeds the third-pass plan (`collaboration/reviews/20261119-third-pass/00-plan-articles-roadmap-cards-rag.md`) and the next handoffs. It does not replace them.

## Method

1. **Read the current state** for each project: `projects/<id>/story.yaml` (headline, sections, roadmap), `reports/metrics.json`, the review file for the project in `collaboration/reviews/20261117-experiment-review/`, and the gap entries in `collaboration/reviews/20261119-gap-analysis/00-gaps-benchmarks-approaches.md`.
2. **Check online** for each gap. Use WebSearch in standard mode first, then extended mode only where standard results are thin, off-target or possibly out of date. Prefer primary sources (papers, official docs, leaderboards, licence files). Record the query and the date.
3. **Label every claim**: source-backed (primary text read), secondary (abstract or snippet), or gap (no source found).
4. **Score each idea** on four things: expected value for the portfolio, cost (compute, hosted calls, engineering days), risk to the existing claim, and whether it can be verified offline.
5. **Do not propose any number change** to existing copy. Propose the experiment that would produce a new number instead.

## Scope, per project

For each of these, answer the four questions in the method's step 4 and list at least two candidate improvements:

- 01 RAG agent (flagship): grounding, judge calibration, retrieval baselines, sealed-set design.
- 02 M5 forecasting: reconciliation, rolling origins, interval methods, probabilistic scoring.
- 03 NAB anomaly detection: TSB-AD and VUS-PR, run-count disclosure, detector families, point-adjust issues.
- 04 AG News classification: selective classification (coverage vs accuracy), cascade evaluation, calibration.
- 05 Churn: cost-sensitive thresholds, calibration, fairness, time-stamped rollout.
- 06 VRPTW routing: Solomon and Homberger benchmark practice, PyVRP and HGS status, ALNS baselines.
- 07 NYC mobility (flagship): probabilistic bands, causal weather, horizon, drift.
- 08 LLM serving: quality measurement beyond saturated smoke checks, tail latency, cost basis.
- 09 Agentic workflows: pass^k reliability, deterministic graders, live-run design.
- 10 Uplift: Qini/AUUC protocols, causal forest vs TOM vs T-learner, policy evaluation, DR/IPW.
- 11 Data engineering: parity methodology, benchmark hygiene (ClickBench, TPC-H practice), scaling claims.
- 12 Tabular lifecycle: foundation-model challengers, horizon and feature practice, tie reporting.
- 13 Model serving: ONNX parity, load-test tooling, hardware-independent reporting.
- apps (agent-chat, document-intelligence): evaluation practice for agent and document-QA apps.

## Required output

One folder: `collaboration/reviews/20261119-sonnet-investigation/`.

- `00-summary.md`: one table across all projects. Columns: project, the top gap, the best approach, expected value (high/medium/low), cost, verifiable offline (yes/no), and the main source.
- `NN-<project>.md` for each project (01 to 13, plus the two apps as `14-agent-chat.md` and `15-document-intelligence.md`). Each file has:
  - current state (with metrics file paths);
  - gaps against the state of the art, each labelled source-backed, secondary or gap;
  - at least two candidate improvements, each with its method, the reference URL, the cost, and the stop condition;
  - a recommendation, ranked;
  - the search queries used and their dates.
- `99-sources.md`: every URL cited, with its label and the claim it supports.

## Constraints

- No hosted calls. Do not run model code. Read committed artifacts only.
- No edits to implementation files or committed records.
- Where two sources conflict (for example the PyVRP table, already known), record both and mark the item unresolved. Do not pick one.
- Mark any claim you could not verify as a gap. Do not fill it from memory.
- Do not cite a leaderboard number from an aggregator as SOTA. Use it only as a pointer to the primary source.

## Done when

- Every project file exists and has at least two candidate improvements.
- Every external claim in the files appears in `99-sources.md` with its label.
- The summary table ranks the improvements by expected value per cost.
- The open conflicts are listed at the end of `00-summary.md`.
