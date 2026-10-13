# Routing Optimization (VRPTW)

**Domain:** combinatorial optimization ·
**Data:** CVRPLIB Solomon VRPTW benchmark (100-customer instances) ·
[Project README](https://github.com/amm-ds/portfolio/tree/main/projects/06-routing-optimization) ·
[DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/06-routing-optimization/DESIGN.md)

Three hand-written, deterministic construction/improvement heuristics for the
vehicle routing problem with time windows — nearest neighbor, Clarke–Wright
savings, and a feasibility-checked 2-opt / 2-opt* improvement pass — plus a
seeded 24-trial HPO of the improvement stage (budget, acceptance, tail
exchange, randomized restarts), benchmarked against published best-known
solutions on a 10-instance subset of the Solomon 100-customer set. Every
solution is machine-validated (exactly-once service, capacity, time windows)
before reporting.

## Key results (real run, seed 42)

| solver | mean gap to best-known | mean runtime |
|---|---|---|
| randomized (feasible floor) | 302.86 % | 0.9 ms/instance |
| nearest_neighbor | 69.16 % | 1.4 ms/instance |
| clarke_wright | 24.62 % | 3.7 ms/instance |
| two_opt (untuned) | 19.55 % | 5.9 ms/instance |
| **two_opt_tuned (HPO winner)** | **19.08 %** | 12.9 ms/instance |

Constraint-aware construction is worth −68.2 % distance vs merely-feasible
random routing; the HPO-chosen tuned config (budget 50, best-improvement,
2-opt + 2-opt\*, restarts best-of-1) closes a further −0.45 gap points,
winning on 5/10 instances. Best tuned gap 8.94 % (RC104). The full benchmark
including HPO finishes in ≈ 3 s. Artifacts in
`projects/06-routing-optimization/reports/`:

- `figures/eda_instance_map.html` — C101 customers colored by time-window tightness
- `figures/route_map_C101.html` — route map of the best C101 plan (15 vehicles)
- `figures/solver_profile.html` — the solver ladder per instance
- `figures/convergence_C101.html` / `convergence_RC105.html` — 2-opt descent, tuned vs untuned
- `results.md` / `metrics.json` / `report.html` — full tables

## Reproduce

```bash
uv run python -m routing_optimization.cli all   # from projects/06-routing-optimization
```

Status: working showcase on the standard platform. Roadmap: metaheuristic
(ALNS/tabu) track with Optuna HPO, hierarchical vehicle-then-distance
objective, real-data track.
