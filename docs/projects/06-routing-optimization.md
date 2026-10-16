# Routing Optimization (VRPTW)

**Domain:** combinatorial optimization ·
**Data:** CVRPLIB Solomon VRPTW benchmark (all 56 100-customer instances) ·
[Project README](https://github.com/amm-ds/portfolio/tree/main/projects/06-routing-optimization) ·
[DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/06-routing-optimization/DESIGN.md) ·
[Dataset card](https://amm-ds.github.io/portfolio/data-registry/cvrplib-solomon/)

A deterministic, seeded solver ladder for the vehicle routing problem with
time windows — randomized floor, nearest neighbor, Clarke–Wright savings,
HPO-tuned 2-opt/2-opt*, and adaptive large-neighborhood search (ALNS:
random/worst/Shaw destroy + regret-2 repair, segment-adapted operator
weights, SA acceptance) — benchmarked against published best-known
solutions on the full Solomon benchmark. Every solution is machine-validated
(exactly-once service, capacity, time windows) before reporting.

## Key results (real run, seed 42, 56 instances)

| solver | mean gap to best-known | mean runtime |
|---|---|---|
| randomized (feasible floor) | 316.95 % | <10 ms/instance |
| nearest_neighbor | 71.64 % | <10 ms/instance |
| clarke_wright | 18.31 % | <10 ms/instance |
| two_opt_tuned (HPO) | 13.63 % | <10 ms/instance |
| **alns (HPO-tuned)** | **4.23 %** | ~0.8–2.8 s/instance |
| ortools_cp (ALNS-hinted cross-check, 10 s budget) | 4.23 % | 13.6 s/instance |

Two criteria are reported throughout: ALNS wins 56/56 instances on distance
(mean gap 13.63 % → 4.23 %, single digits on every family: C1 4.48 %, C2
6.50 %, R1 4.10 %, R2 3.04 %, RC1 4.75 %, RC2 3.00 %), and under the
benchmark's vehicles-first ranking it wins 43/56 intra-ladder with a mean of
+3.73 vehicles vs best-known (up to +6–8 on R2/RC2). The hinted CP-SAT arm
is an incumbent-improvement probe, not an independent baseline: it ended
UNKNOWN on all 56 within its 10 s budget and returned the ALNS plan
unchanged, while certifying small subproblems to optimality (25-customer
C101 prefix: 191.8 in 2.9 s). Artifacts in
`projects/06-routing-optimization/reports/`:

- `figures/eda_instance_map.html` — C101 customers colored by time-window tightness
- `figures/route_map_C101.html` — best C101 plan (ALNS: 11 vehicles)
- `figures/family_gap.html` — mean gap + vehicle delta per Solomon family per solver
- `figures/solver_profile.html` — the solver ladder per instance
- `figures/convergence_C101.html` / `convergence_RC105.html` — 2-opt descent
- `figures/alns_convergence_C101.html` / `alns_convergence_RC105.html` — ALNS descent
- `figures/gap_pct.html` / `figures/pareto_gap_runtime.html` / `figures/runtime.html`
- `results.md` / `metrics.json` / `report.html` — full tables (per-instance + per-family)

## Roadmap

Delivered (retrospective): ALNS behind the `RoutePlan` contract (13.63 % →
4.23 % mean gap, dual criteria, HPO-tuned); full 56-instance dual-criteria
benchmark; hierarchical-objective (vehicles-first) reporting per the SINTEF
convention; CP-SAT hinted cross-check arm. Deferred (engagement-dependent):
unhinted independent-solver comparison (PyVRP or OR-Tools routing at equal
budget); Gehring–Homberger 200–1000-customer instances; solver-as-a-service
endpoint.

## Reproduce

```bash
uv run python -m routing_optimization.cli all   # from projects/06-routing-optimization
```
