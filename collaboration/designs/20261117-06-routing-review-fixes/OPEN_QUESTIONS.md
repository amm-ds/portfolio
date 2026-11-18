# OPEN QUESTIONS — 06 routing ALNS-vs-unhinted interval

Date: 2026-11-19 (overnight queue, item 5)
Executor: Kimi Code

## Blocked part

Handoff step 3 (second half): "a bootstrap over the 56 instances for … the
ALNS vs unhinted difference."

## Finding

`reports/metrics.json:unhinted_cp_sat` is committed with **status + runtime
only for all 56 instances — zero distances** (`UNKNOWN` on 56/56; CP-SAT
produced no feasible plan at the equal 10 s budget). A distance-difference
interval is not computable from committed artifacts, and the handoff forbids
filling gaps / re-solving ("Do not change how it is computed").

The interval is recorded as null with the reason in
`metrics.json:intervals.alns_vs_unhinted_cp_sat`, and the unhinted arm's
honest verdict (no feasible plan on any of the 56) is already promoted in the
README ladder, the story table, and `results.md`.

## Owner option

Re-run only the unhinted arm with a longer budget (or warm-start disabled
HGS) if an independent-arm distance comparison is wanted; that is a new solve
decision, not part of this handoff.
