# Routing Optimization (VRPTW)

**Domain:** combinatorial optimization ·
**Data:** CVRPLIB Solomon VRPTW benchmark (100-customer instances) ·
[Project README](https://github.com/amm-ds/portfolio/tree/main/projects/06-routing-optimization) ·
[DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/06-routing-optimization/DESIGN.md)

Three hand-written, deterministic heuristics for the vehicle routing problem
with time windows — nearest neighbor, Clarke–Wright savings, and a feasibility-
checked 2-opt / 2-opt* improvement pass — benchmarked against published
best-known solutions on a 10-instance subset of the Solomon 100-customer set.
Every solution is machine-validated (exactly-once service, capacity, time
windows) before reporting.

## Key results (real run, seed 42)

| solver | mean gap to best-known | mean runtime |
|---|---|---|
| nearest_neighbor (baseline) | 69.16 % | 2.9 ms/instance |
| clarke_wright | 24.62 % | 2.7 ms/instance |
| **two_opt (wins 10/10 instances)** | **19.55 %** | 3.5 ms/instance |

Best per-instance gaps range from **8.94 %** (RC104) to 30.41 % (C102). The
full solve stage for all 10 instances takes ~0.1 s; artifacts live in
`projects/06-routing-optimization/reports/`:

- `figures/gap_pct.html` — grouped bar, gap-% per instance per solver
- `figures/route_map_C101.html` — route map of the best C101 plan (15 vehicles)
- `figures/runtime.html` — solver runtimes (log scale)
- `results.md` / `metrics.json` / `report.html` — full tables

## Reproduce

```bash
uv run python -m routing_optimization.cli all   # from projects/06-routing-optimization
```

Status: working showcase on the standard platform. Roadmap: metaheuristic
(ALNS/tabu) track with Optuna HPO, hierarchical vehicle-then-distance
objective, real-data track.
