# Experiment review index: technical and engineering review of 01–13

Date: 2026-11-17
Reviewer: Claude Code
Implementation: none changed. This is a review pass; each file lists what Kimi should refine.
Status: changes requested (per experiment; see each file)

## How to read this

Each experiment file has the same sections:

1. **Verdict**: one line.
2. **Architecture**: design soundness, boundaries, reproducibility.
3. **Results vs benchmarks and SOTA**: what the number is compared to, and what a serious reader would compare it to.
4. **Metrics and statistics**: rigour, intervals, leakage, selection.
5. **Code and tests**: coverage of the claims.
6. **Visuals**: whether each figure supports the claim.
7. **Copy and articles**: truth-in-copy, rounding, consistency across short, README, and story.
8. **Kimi refinement tasks**: concrete, ordered, with severity.

External SOTA references are from memory and are marked **(verify)** where the number needs a citation before publication.

## Severity scale

- **blocker**: a public claim is wrong or cannot be traced to a committed artifact.
- **major**: a method or comparison weakens a headline claim.
- **minor**: a wording, rounding, or visual issue.

## Summary table

| # | Experiment | Verdict | Blockers | Majors |
|---|---|---|---|---|
| 01 | RAG agent | Sound harness, honest on failures; generation grounding is the weak point | 0 | 2 |
| 02 | Demand forecasting (M5) | Strong protocol; the prod page is broken (metrics guard) | 1 (prod) | 2 |
| 03 | Anomaly detection (NAB) | Honest no-skill framing; metric definitions need a single source | 0 | 2 |
| 04 | NLP classification | Useful routing study; cascade gain is within noise | 1 (cascade claim) | 2 |
| 05 | Churn pipeline | Best statistical hygiene in the set; copy is accurate | 0 | 1 |
| 06 | VRPTW routing | Solid engineering; the CP-SAT "cross-check" is not independent; no SOTA comparator | 0 | 3 |
| 07 | NYC taxi mobility | Good holdout discipline; rounding and band coverage wording | 0 | 1 |
| 08 | LLM serving | Honest harness; quality guardrail too weak to claim anything | 0 | 2 |
| 09 | Agentic workflows | Deterministic grading; live confirmation still pending | 0 | 2 |
| 10 | Uplift | Good analysis; short copy says 64,000 customers, analysis uses 42,613; "profit" is revenue | 1 (copy) | 2 |
| 11 | Data engineering | Clear parity contract; note the sqlite row | 0 | 1 |
| 12 | Tabular ML lifecycle | Clean floor and ablation; champion vs LightGBM gap is inside noise | 0 | 2 |
| 13 | Model serving | Paired harness; report p99 and a real load tool | 0 | 2 |

## Cross-cutting findings (apply to all)

1. **Numbers with too many digits in copy.** 04 short_version has `0.9529432`. Round for people; keep full precision in tables (repo convention).
2. **Electricity and cost figures** (08, 13) rest on declared assumptions. Keep the assumption next to the number in the card, not only in the README.
3. **Mixed statistical language.** Some files use "significant", others "real". Define the interval method once in `docs/engineering/` and link it.
4. **No experiment states a published SOTA on the same split.** That is acceptable if the card says "no public leaderboard on this split" rather than implying parity.
5. **Duplicated headline numbers** across `short_version`, README, and `story.yaml` drift easily. Add a check that greps each headline number against its committed metrics file.
