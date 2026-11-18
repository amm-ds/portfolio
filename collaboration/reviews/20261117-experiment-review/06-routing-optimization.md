# 06 · Routing optimization (VRPTW, Solomon): technical review

## Verdict
Solid, deterministic engineering with a clear benchmark protocol. Two methodological weaknesses weaken the headline: the CP-SAT "cross-check" is seeded from ALNS and so is not independent, and the comparison omits the state-of-the-art heuristic family for this benchmark.

## Architecture
- Three hand-written heuristics (Clarke-Wright, 2-opt, ALNS) plus a randomized floor and nearest-neighbour baseline; OR-Tools CP-SAT as an exact-leaning arm; registry best-known solutions as the reference. The ladder is well-chosen.
- Vehicles-first, distance-second hierarchy matches the Solomon convention. Correct and explicitly stated.

## Results vs benchmarks and SOTA
- ALNS mean distance gap 4.23% and mean vehicle delta +3.73 across 56 instances.
- **Major.** The state of the art on Solomon-style VRPTW is hybrid genetic search (HGS, Vidal et al. 2013 line of work) and its successors, which report distance gaps well under 1% (**verify** the exact figures and instance set before citing). A 4.2% ALNS gap is a useful floor, but readers will read the gap as the quality ceiling unless the card names HGS as the reference.
- **Major.** The vehicle delta (+3.7) is large relative to published best-known solutions that minimize vehicles first. This suggests the ALNS objective weighting, not only search depth, needs review.
- The `ortools_cp` row has the same mean gap (4.2322) and vehicle delta (3.73) as `alns`. This is consistent with CP-SAT simply returning the ALNS hint, so it adds no independent evidence. The card must say so, or the arm should run unhinted for the comparison.

## Metrics and statistics
- Mean over 56 instances with no interval. Add a bootstrap or paired interval over instances for the gap, since instances vary widely.
- Win counts (`by_distance`: ALNS wins 52 of 56 on distance) are a clearer story than the mean. Lead with them.
- `randomized` mean gap 316.9% makes the family figure unreadable (see the figure-review handoff). Use the median for the distance panel or cap the axis.

## Code and tests
- 11 test files. Confirm the best-known loader is tested against one instance by hand.
- The unhinted CP-SAT run exists in metrics (`unhinted_cp_sat`). Promote it to the headline comparison if it is complete.

## Visuals
- `family_gap`: bottom empty band and randomized-dominated scale (see figure-review handoff).
- `route_map_C101_before_after`: good, keep.

## Copy and articles
- "within 4.2% of best-known routes in ~1 second each" is accurate for ALNS (mean runtime 1.15 s). Name the solver in the sentence.
- The 15-minute full runtime is disclosed. Keep it.

## Kimi refinement tasks
1. (major) Label the CP-SAT hinted arm as non-independent on the card and figure, and report the unhinted arm beside it.
2. (major) Add HGS (or an equivalent published reference) as a SOTA comparator on the same instances, or state on the card that none is included and why.
3. (major) Investigate the +3.7 vehicle delta: check ALNS objective weighting against the hierarchical objective.
4. (minor) Add instance-level bootstrap intervals to the mean gap.
5. (minor) Fix the family figure per the figure-review handoff.
