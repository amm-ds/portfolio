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
- `solver.py` — four deterministic solvers, Euclidean distances:
  1. `randomized` — seeded shuffle of customers packed into feasible routes
     with a return-leg repair pass; no local search. The flat feasible
     reference that makes the other solvers' improvement legible.
  2. `nearest_neighbor` — sequential NN with capacity + time-window
     feasibility checks; routes seeded by earliest due time.
  3. `clarke_wright_savings` — parallel savings with capacity and full-route
     time-window feasibility checks on every merge.
  4. `two_opt` — first-improvement 2-opt on the better construction plan:
     intra-route segment reversals **and** inter-route 2-opt* tail exchanges;
     every move preserves capacity and time-window feasibility.
- `tuning.py` — seeded random-search HPO over the improvement stage (move
  budget, acceptance rule, tail-exchange on/off, best-of-k randomized-restart
  portfolio); the winner is persisted to `params.yaml` as `solver_best` and
  reported as the `two_opt_tuned` run.
- `evaluate.py` — per-instance runs, gap vs `docs/data-registry/best_known/
  solomon100.csv` (name normalization `C1_01 → C101`), DQ gates, markdown +
  plotly artifacts.
- `cli.py` — typer: `download`, `solve`, `evaluate`, `all`.

## Results (real run, seed 42)

Full pipeline: `uv run python -m routing_optimization.cli all`.
Artifacts in `reports/` (see `reports/results.md`, `reports/report.html`,
`reports/metrics.json`).

Mean over the 10-instance subset (`reports/metrics.json`) — the solver ladder:

| solver | mean gap to best-known | mean distance | mean vehicles | mean runtime |
|---|---|---|---|---|
| randomized (feasible floor) | 302.86 % | 4055.76 | 24.6 | 0.9 ms |
| nearest_neighbor | 69.16 % | 1805.55 | 18.2 | 1.4 ms |
| clarke_wright | 24.62 % | 1339.13 | 15.7 | 3.7 ms |
| two_opt (untuned) | 19.55 % | 1289.91 | 15.7 | 5.9 ms |
| **two_opt_tuned (HPO)** | **19.08 %** | **1284.15** | 15.7 | 12.9 ms |

Key findings:

- **Constraint-aware construction is the big lever**: randomized → savings is
  −2765.85 mean distance (−68.2 %); everything after is refinement.
- **2-opt\* tail exchanges matter most within the improvement stage**: trials
  without them plateau at ≈ 1328 mean distance vs 1289.9 with them (−3 %).
- **Seeded HPO** (24 seeded random-search trials over move budget 50–500,
  first- vs best-improvement acceptance, tail-exchange on/off, best-of-k
  randomized-restart portfolio k=1..8; objective = mean distance across the 10
  instances) chose: **budget 50, best-improvement, 2-opt + 2-opt\*, restarts
  best-of-1** — written to `params.yaml` as `solver_best`. Tuned vs untuned:
  −5.76 mean distance (−0.45 % gap points), winning on 5/10 instances (up to
  −19.10 on RC105); vs the randomized floor: −2771.61 (−68.3 %).
- **Two honest negatives**: randomized restarts never help (randomized starts
  are ~3× worse than savings starts, so 2-opt from them never catches up —
  the search itself chose k=1), and the move budget saturates fast (local
  optimum in ≤ ~20 accepted moves, so 200 was already generous).
- `two_opt_tuned` wins on **10/10 instances** (ties included where curves
  coincide). Convergence curves (`convergence_C101`, `convergence_RC105`)
  show the construction start, and on RC105 the tuned run escaping the
  untuned local optimum (1984.8 → 1901.2 vs untuned 1920.3).

Per-instance best over all five solvers (distance / gap / vehicles):

| instance | best known | distance | gap % | vehicles |
|---|---|---|---|---|
| C101 | 828.94 | 1046.53 | 26.25 | 15 |
| C102 | 828.94 | 1071.35 | 29.24 | 15 |
| C103 | 828.06 | 994.25 | 20.07 | 14 |
| C104 | 824.78 | 963.30 | 16.79 | 13 |
| C105 | 828.94 | 1047.54 | 26.37 | 15 |
| RC102 | 1554.75 | 1831.04 | 17.77 | 21 |
| RC103 | 1261.67 | 1480.20 | 17.32 | 15 |
| RC104 | 1135.48 | 1236.99 | 8.94 | 13 |
| RC105 | 1629.44 | 1901.18 | 16.69 | 23 |
| RC108 | 1139.82 | 1269.10 | 11.34 | 13 |

Why the improvement happens, in measured deltas:

- **randomized → clarke_wright: −2765.85 mean distance (−68.2 %), −278 gap
  points.** Merely *finding* feasible routes is easy; the savings heuristic
  wins because it constructs routes around shared depot legs and joint
  time-window feasibility (`s(i,j) = d(0,i) + d(0,j) − d(i,j)` merges), instead
  of a random permutation that zig-zags across the map and burns ~25 of the 25
  vehicles. Constraint-aware construction is where the value is.
- **clarke_wright → two_opt: −49.22 mean distance (−3.7 %), −5.07 gap points**
  (e.g. C101 36.02 % → 26.25 %, RC108 12.26 % → 11.72 %). Only
  feasibility-preserving 2-opt / 2-opt* moves are accepted, so the gain is
  pure: no re-validation debt, no broken windows.
- **two_opt → two_opt_tuned (seeded HPO): −5.76 mean distance (−0.45 %)** —
  small but real, and bought for milliseconds of search. The search's most
  useful output is arguably the two negatives above (restarts don't pay,
  budget saturates), which is what a client should demand from any HPO:
  evidence about what *not* to spend complexity on.

Honest caveats: `nearest_neighbor` and `randomized` are deliberately naive
baselines — on RC105 both exceed the stated 25-vehicle fleet (26 and 30
vehicles respectively) because greedy feasible packing fragments on that
instance's tight windows; this is reported, not hidden. These are hand-written
heuristics in ~330 lines, not a metaheuristic; the published best-known values
come from tuned ALNS / tabu / hybrid genetic search.

Figures (`reports/figures/`, HTML + JSON for the showcase API):

- `eda_instance_map` — C101 customer scatter colored by time-window tightness
  (window width = due − ready); the depot is the star marker. Complements the
  route map with the raw instance structure.
- `gap_pct` — grouped bar, gap-% per instance per solver; the `randomized`
  bar is the flat feasible reference that makes the construction/improvement
  delta legible.
- `solver_profile` — per-instance grouped distance bars (log scale) with
  baselines greyed and `two_opt_tuned` promoted — the solver ladder in one
  glance, with a takeaway subtitle.
- `convergence_C101` / `convergence_RC105` — best-found distance vs accepted
  moves; construction start starred, tuned vs untuned overlaid. C101 shows
  coincident local optima; RC105 shows the tuned run escaping the untuned
  one (−19.1).
- `route_map_C101` — depot + customer scatter with route polylines colored per
  vehicle for the best C101 plan (15 vehicles, 1046.53).
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

Planned deepening, in rough priority order:

- **Metaheuristic track:** ALNS or tabu search behind the same `RoutePlan`
  contract to close the gap from ~19 % toward single digits — the remaining
  gap lives in time-window-aware sequencing (insertion/relocation moves and
  escape mechanisms), which 2-opt neighborhoods cannot express. The wave-3
  HPO framework (`tuning.py`) carries over directly for operator-weight
  tuning.
- **Real-data track:** re-target the pipeline at a client-style delivery
  dataset (open mobility data) with the same contracts.
- **Hierarchical objective:** match the SINTEF convention (minimize vehicles
  first, then distance) and report the two-dimensional comparison.
