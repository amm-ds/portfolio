# 06 — Routing Optimization on Public Benchmark Instances

Combinatorial optimization showcase: three hand-written, deterministic
heuristics for the **Vehicle Routing Problem with Time Windows (VRPTW)**,
benchmarked against published best-known solutions on the Solomon
100-customer instances.

- **Domain:** combinatorial optimization
- **Data:** Solomon VRPTW benchmark (CVRPLIB, 100-customer instances; real
  academic benchmark, subset of 10 instances, ~1 MB)
- **Status:** working showcase on the standard platform (flagships: 01 and 07)
- **Runtime:** the full solve stage takes **~0.1 s** for all 10 instances

## Problem

A fleet of identical vehicles leaves a central depot, must serve every customer
exactly once within its time window `[ready, due]`, respects vehicle capacity,
and returns to the depot. Objective: minimize total travel distance. Solomon's
instances are the canonical VRPTW benchmark; each 100-customer file pins the
coordinates, demand, time window and service time of every customer plus the
fleet capacity, and published best-known solutions provide the reference for
optimality gaps.

This project answers a question every optimization engagement starts with:
*how close do classical construction + improvement heuristics get to the best
known solutions, how fast, and at what code complexity?*

## Design summary

See [DESIGN.md](DESIGN.md) for the full requirements/options/decision record.

- `config.py` — `VRPConfig` (settings, instance list, 2-opt iteration cap).
- `schemas.py` — pydantic `Customer` / `Problem` / `RoutePlan`;
  `RoutePlan.validate_against` hard-gates exactly-once service and capacity.
- `parser.py` — Solomon `.txt` parser (4 header lines + `id x y demand ready
  due service` rows), tolerant of blank lines and split headers.
- `solver.py` — five deterministic solvers, Euclidean distances:
  1. `randomized` — seeded shuffle of customers packed into feasible routes
     with a return-leg repair pass; no local search. The flat feasible
     reference that makes the other solvers' improvement legible.
  2. `nearest_neighbor` — sequential NN with capacity + time-window
     feasibility checks; routes seeded by earliest due time.
  3. `clarke_wright_savings` — parallel savings with capacity and full-route
     time-window feasibility checks on every merge.
  4. `two_opt` — 2-opt on the better construction plan: intra-route segment
     reversals **and** inter-route 2-opt* tail exchanges (acceptance and
     tail-exchange parameterized); every move preserves feasibility.
  5. `alns` — adaptive large-neighborhood search (Ropke–Pisinger): destroy by
     random / worst / Shaw time-window-relatedness removal, repair by greedy
     regret-2 insertion, operator weights adapted per segment, simulated-
     annealing acceptance; starts from the tuned 2-opt plan, iteration-capped
     from config.
- `tuning.py` — seeded random-search HPO, run twice: over the 2-opt stage
  (budget, acceptance, tail exchange, restarts; all instances) and over the
  ALNS knobs (segment length, reaction factor, init weights; 6-instance
  subset); winners persisted to `params.yaml` as `solver_best` / `alns_best`.
- `evaluate.py` — per-instance runs on all 56 Solomon instances, gap vs the
  registry table + project supplement, per-family aggregation, DQ gates,
  markdown + plotly artifacts.
- `cli.py` — typer: `download`, `solve`, `evaluate`, `all`.

## Results (real run, seed 42, all 56 Solomon instances)

Full pipeline: `uv run python -m routing_optimization.cli all` (benchmark +
both HPO searches + ALNS ≈ 90 s).
Artifacts in `reports/` (see `reports/results.md`, `reports/report.html`,
`reports/metrics.json`).

Mean over all 56 instances (`reports/metrics.json`) — the solver ladder:

| solver | mean gap to best-known | mean distance | mean vehicles | mean runtime |
|---|---|---|---|---|
| randomized (feasible floor) | 316.95 % | 3868.55 | 18.3 | 0.6 ms |
| nearest_neighbor | 71.64 % | 1694.18 | 14.0 | 1.1 ms |
| clarke_wright | 18.31 % | 1200.06 | 13.0 | 3.0 ms |
| two_opt (untuned) | 13.75 % | 1158.34 | 13.0 | 4.2 ms |
| two_opt_tuned (HPO) | 13.63 % | 1156.92 | 13.0 | 9.6 ms |
| **alns (HPO-tuned)** | **4.23 %** | **1062.02** | **11.0** | 801 ms |

Per-family mean gap (`reports/metrics.json` → `families`, figure
`family_gap`):

| family | instances | clarke_wright | two_opt_tuned | alns |
|---|---|---|---|---|
| C1 | 9 | 25.76 % | 18.62 % | 4.48 % |
| C2 | 8 | 31.62 % | 21.48 % | 6.50 % |
| R1 | 12 | 18.17 % | 14.95 % | 4.10 % |
| R2 | 11 | 10.29 % | 7.28 % | 3.04 % |
| RC1 | 8 | 16.59 % | 13.29 % | 4.75 % |
| RC2 | 8 | 9.60 % | 7.23 % | 3.00 % |

Key findings:

- **ALNS closes the gap**: 13.63 % → **4.23 %** mean gap (−9.4 points, −69 %
  of the remaining tuned-2-opt distance-to-optimum), winning on **56/56**
  instances, in ~0.8 s/instance. Chosen by the seeded knob search (12 trials
  on a 6-instance subset): segment 100, reaction 0.5, uniform init weights —
  persisted to `params.yaml` as `alns_best`.
- **Constraint-aware construction remains the first big lever** (randomized →
  savings −68 % of baseline distance); the metaheuristic is the second.
- **Single digits on every family**; best on wide-window R2/RC2 (~3 %).
  Honest residuals: C2 6.50 % (wide horizon, few-vehicle optimum — destroy
  size 10 under-diversifies there), C103 11.67 % / C203 19.48 % (tight chains
  that resist q-customer destroy/repair).
- **Negative gaps are real and reported**: ALNS lands *below* the published
  reference on 8 instances (best RC202 −3.85 %, RC105 −2.78 %). The SINTEF
  table mixes conventions (hierarchical vehicle-first objective, double
  precision, some values flagged as rounding artifacts) — our plain-distance,
  full-precision solutions legitimately undercut a few references.
- Earlier honest negatives stand: randomized restarts never pay (two-opt HPO
  chose k=1), and 2-opt budgets saturate (≤ ~20 accepted moves).

Why the improvement happens, in measured deltas:

- **randomized → clarke_wright: −68 % of baseline distance.** Feasible routes
  are easy; savings builds them around shared depot legs and joint time-window
  feasibility instead of a random permutation.
- **clarke_wright → two_opt (−3.7 %) → two_opt_tuned (−0.45 %)** — local
  polish inside one route topology.
- **→ alns: another −69 % of the remaining distance-to-optimum.** 2-opt only
  reorders or swaps pieces of existing routes; it cannot move a customer to a
  different route. ALNS's destroy (random / worst / Shaw time-window
  relatedness removal) + regret-2 repair re-sequences customers *across*
  routes — exactly the neighborhood the gap lived in.

Honest caveats: `nearest_neighbor`, `randomized` and occasionally
`clarke_wright` exceed the stated 25-vehicle fleet on tight R1/RC1 instances
(e.g. CW needs 31 on R101) — reported, not hidden; distance stays valid and
the vehicle count flags where a construction heuristic fragments. The
remaining roadmap item is the hierarchical objective (fewest vehicles first,
then distance).

Figures (`reports/figures/`, HTML + JSON for the showcase API):

- `eda_instance_map` — C101 customer scatter colored by time-window tightness
  (window width = due − ready); the depot is the star marker.
- `gap_pct` — grouped bar, gap-% per instance per solver.
- `family_gap` — mean gap per Solomon family per solver; baselines greyed,
  ALNS promoted.
- `solver_profile` — per-instance grouped distance bars (log scale) with
  baselines greyed.
- `convergence_C101` / `convergence_RC105` — 2-opt descent, tuned vs untuned.
- `route_map_C101` — best C101 plan (ALNS: 11 vehicles, 860.21, gap 3.77 %).
- `runtime` — grouped bar, solver runtime per instance (log scale).

## Reproduce

```bash
cd projects/06-routing-optimization
uv run python -m routing_optimization.cli all       # download + solve + evaluate
# or staged:
dvc repro projects/06-routing-optimization/dvc.yaml
# or individually:
uv run python -m routing_optimization.cli download  # fetch Solomon archive -> data/raw
uv run python -m routing_optimization.cli solve     # -> reports/solutions.json, reports/dq.md
uv run python -m routing_optimization.cli evaluate  # -> reports/{results.md,metrics.json,report.html,figures/}
```

Tests (offline, hypothesis property tests included):

```bash
uv run pytest projects/06-routing-optimization -q
```

## What this demonstrates for a client

- **Feasibility first:** every solution is machine-checked (exactly-once
  service, capacity, time windows) before it is reported — optimization results
  you can ship to dispatch without a manual audit.
- **Honest benchmarking:** gaps are computed against published best-known
  values on standard instances, so quality claims are verifiable and
  comparable to literature.
- **Speed-to-value:** the whole benchmark solves in ~0.1 s; a transparent
  heuristic baseline is available in minutes, not weeks, and marks the
  improvement a metaheuristic must justify.
- **Reproducibility:** pinned data snapshot (sha256 dataset card), DVC stages,
  deterministic seeded solvers, DQ gates that halt the pipeline.

## Roadmap

Delivered this cycle: ALNS behind the same `RoutePlan` contract (mean gap
13.63 % → 4.23 %, single digits on every family) and the full 56-instance
benchmark with per-family reporting. One item remains:

- **Hierarchical objective** (deferred): match the SINTEF convention —
  minimize vehicle count first, distance second — and report the
  two-dimensional comparison. The fleet counts above (e.g. ALNS's 11.0 mean
  vehicles vs the 10-vehicle C1 optima) show where this matters.
