# 06 · Routing Optimization (VRPTW)

**Domain:** combinatorial optimization ·
**Data:** CVRPLIB Solomon VRPTW benchmark (all 56 100-customer instances) ·
**Status:** working showcase —
[Project README](https://github.com/amm-ds/portfolio/tree/main/projects/06-routing-optimization) ·
[DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/06-routing-optimization/DESIGN.md) ·
[Dataset card](https://amm-ds.github.io/portfolio/data-registry/cvrplib-solomon/)

> **TL;DR:** fleet operators running last-mile and field-service routes, where
> every percent of distance is fuel, driver hours and CO₂, every day.
> The solver ladder lands **4.23%** from published best-known optima on all 56
> Solomon instances, in auditable seeded code.
>
> [Case study source and interactive figures on GitHub →](https://github.com/amm-ds/portfolio/tree/main/projects/06-routing-optimization)

![ALNS plans feasible, capacity- and time-window-valid routes for all 100 C101 customers on the clustered family, within 3.77% of best-known distance.](../assets/projects/06-routing-optimization/route_map_C101.png){ width="100%" }

Fleet operators routing last-mile and field-service vehicles leave fuel,
driver hours and CO₂ on the table every day. This project answers with a
deterministic, seeded solver ladder that lands within 4.23% of published
best-known optima on the full Solomon benchmark — and states exactly what the
remaining gap costs:

A seeded solver ladder for the vehicle routing problem with time windows —
randomized floor, nearest neighbor, Clarke–Wright savings,
hyperparameter-tuned (HPO) 2-opt/2-opt*,
and adaptive large-neighborhood search (ALNS: random/worst/Shaw destroy +
regret-2 repair, segment-adapted operator weights, SA acceptance) — benchmarked
against published best-known solutions. Every solution is machine-validated
(exactly-once service, capacity, time windows) before reporting.

## Key results (real run, seed 42, 56 instances)

Mean gap to published best-known distance, lower is better; the benchmark's
vehicles-first ranking is reported alongside the gap (see the story results).
Δ gap is the change in mean gap vs `nearest_neighbor` (the construction
incumbent), in percentage points; the bold row is the ladder's best. The
4.23% mean carries a one-sample test against a zero gap — 95% CI 3.1–5.3 pp,
t(55) = 7.63, p ≈ 2×10⁻¹⁰ — read narrowly: per-instance gaps cluster by
family and are deterministic given the seed, so the CI describes spread
across instances, not sampling uncertainty about a population mean (and
best-known references are not proven optima).

| solver | mean gap to best-known | Δ gap vs nn | mean runtime |
|---|---|---|---|
| randomized (feasible floor) | 316.95 % | +245.31 pp | <10 ms/instance |
| nearest_neighbor | 71.64 % | — | <10 ms/instance |
| clarke_wright | 18.31 % | −53.33 pp | <10 ms/instance |
| two_opt_tuned (HPO) | 13.63 % | −58.01 pp | <10 ms/instance |
| **alns (HPO-tuned) ← best** | **4.23 %** | **−67.41 pp** | **~1.1 s/instance (committed run 2.8 s under load)** |
| alns_fleet (vehicles-first) | 4.30 % | −67.34 pp | ~1.1 s/instance |
| ortools_cp (ALNS-hinted probe, 10 s budget) | 4.23 % | −67.41 pp | 12.0 s/instance |
| ortools_cp_unhinted (equal 10 s budget) | no feasible plan on any of the 56 | — | 13.1 s/instance |

Two criteria throughout: ALNS wins 52/56 instances on distance intra-ladder
(the fleet-first variant `alns_fleet` wins the other 4 — the hierarchical
search path occasionally lands in a better-distance optimum), and under the
vehicles-first ranking ALNS wins 38/56 with `alns_fleet` winning 5/56 (the
naive solvers take the rest on fleet size at far worse distance); mean +3.73
vehicles vs best-known (up to +6–8 on R2/RC2). ALNS also undercuts 8
published references (best RC202 −3.85%). The hinted CP-SAT arm is an
incumbent-improvement probe, not an independent baseline: it ended UNKNOWN on
all 56 within its 10 s budget and returned the ALNS plan unchanged at ~10× the
ALNS runtime, while certifying small subproblems to optimality (25-customer
C101 prefix: 191.8 in 2.9 s). The unhinted arm at the equal 10 s budget
produced no feasible plan on any instance — from scratch, the exact model
yields nothing at this scale and budget. All artifacts live in
`projects/06-routing-optimization/reports/`: interactive figures (instance
maps, per-family gaps, convergence descents, runtime-vs-gap Pareto) with
`results.md` / `metrics.json` / `report.html` for the full per-instance and
per-family tables — interactive versions in the
[case study on GitHub](https://github.com/amm-ds/portfolio/tree/main/projects/06-routing-optimization).

![Before/after of the improvement heuristic on Solomon C101 — left: HPO-tuned 2-opt on the Clarke–Wright plan (15 routes, 1046.53 total distance); right: ALNS on the same instance (11 routes, 860.21). The metaheuristic consolidates the construction plan's overlapping short routes into fewer, longer ones, cutting distance 17.8% (1046.5 → 860.2, matching `alns_convergence_C101`); the after-plan sits 3.77% above the best-known 828.94. Routes reproduced from the committed solution artifact; both plans verified capacity- and time-window-feasible by the project validator.](../assets/projects/06-routing-optimization/route_map_C101_before_after.svg){ width="100%" }

![HPO-tuned ALNS closes the gap to best-known optima into single digits on every Solomon family (C1 4.48%, C2 6.50%, R1 4.10%, R2 3.04%, RC1 4.75%, RC2 3.00%).](../assets/projects/06-routing-optimization/family_gap.png){ width="100%" }

## Roadmap

Delivered (retrospective): ALNS behind the `RoutePlan` contract (13.63 % →
4.23 % mean gap, dual criteria, HPO-tuned); full 56-instance dual-criteria
benchmark (intra-ladder: ALNS 52/56 on distance, 38/56 vehicles-first; the
fleet-first twin takes 4 and 5); hierarchical fleet-first objective landed as
`alns_fleet` (−0.07 mean vehicles at +0.07 pp gap); CP-SAT arms — the hinted
incumbent-improvement probe (UNKNOWN on all 56 at 100 customers, incumbents
unchanged at ~10× runtime, small subproblems certified optimal in seconds) and
the equal-budget unhinted comparison (no feasible plan on any instance).

## Reproduce

```bash
uv run python -m routing_optimization.cli all   # from projects/06-routing-optimization
```
