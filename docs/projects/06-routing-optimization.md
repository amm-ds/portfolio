# Routing Optimization (VRPTW)

**Domain:** combinatorial optimization ·
**Data:** CVRPLIB Solomon VRPTW benchmark (all 56 100-customer instances) ·
[Project README](https://github.com/amm-ds/portfolio/tree/main/projects/06-routing-optimization) ·
[DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/06-routing-optimization/DESIGN.md)

A deterministic, seeded solver ladder for the vehicle routing problem with time
windows — randomized floor, nearest neighbor, Clarke–Wright savings, HPO-tuned
2-opt/2-opt*, and adaptive large-neighborhood search (ALNS: random/worst/Shaw
destroy + regret-2 repair, segment-adapted operator weights, SA acceptance) —
benchmarked against published best-known solutions on the full Solomon
benchmark. Every solution is machine-validated (exactly-once service, capacity,
time windows) before reporting.

## Key results (real run, seed 42, 56 instances)

| solver | mean gap to best-known | mean runtime |
|---|---|---|
| randomized (feasible floor) | 316.95 % | 0.6 ms/instance |
| nearest_neighbor | 71.64 % | 1.1 ms/instance |
| clarke_wright | 18.31 % | 3.0 ms/instance |
| two_opt_tuned (HPO) | 13.63 % | 9.6 ms/instance |
| **alns (HPO-tuned)** | **4.23 %** | 801 ms/instance |

ALNS wins 56/56 and reaches single-digit gaps on every family (C1 4.48 %, C2
6.50 %, R1 4.10 %, R2 3.04 %, RC1 4.75 %, RC2 3.00 %), with negative gaps on 8
instances where full-precision solutions undercut convention-mixed published
references. Remaining roadmap item: the SINTEF hierarchical objective (fewest
vehicles first). Artifacts in `projects/06-routing-optimization/reports/`:

- `figures/eda_instance_map.html` — C101 customers colored by time-window tightness
- `figures/route_map_C101.html` — best C101 plan (ALNS: 11 vehicles, 860.21)
- `figures/family_gap.html` — mean gap per Solomon family per solver
- `figures/solver_profile.html` — the solver ladder per instance
- `figures/convergence_C101.html` / `convergence_RC105.html` — 2-opt descent
- `results.md` / `metrics.json` / `report.html` — full tables (per-instance + per-family)

## Reproduce

```bash
uv run python -m routing_optimization.cli all   # from projects/06-routing-optimization
```
