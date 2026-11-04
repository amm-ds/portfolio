# DESIGN — Model API Serving & Docker Deployment

Decisions behind experiment 13, in the order the pipeline makes them.

## 1. Vendor the recipe; never import the sibling

Workspace members are siblings, not dependencies: `13-model-serving` must not
`import tabular_ml_lifecycle`. The champion path (data → features → selection
→ MLP loop) is re-implemented inside this package from experiment 12's
committed params and feature contract, same seed. The payoff is a hard
reproduction gate rather than a hope: same pinned zip (sha256), same recipe,
same seed reproduce 12's committed test MAE **exactly** (25.43163249606178),
and the prepared-frame checksum matches 12's committed dataset contract.

## 2. Two gates before anything serves

- **Reproduction gate** — derived test MAE within `reproduction_tolerance` of
  12's committed value, raised in the train stage.
- **Parity gate** — ONNX Runtime vs native torch on a 512-row seeded probe
  grid, max-abs on the raw network output. The tolerance is absolute (1e-4)
  **plus a relative float32 term** (1e-5 × output scale): kernel-order noise
  scales with output magnitude, so a purely absolute gate misfires on
  ill-scaled models and is needlessly tight on healthy ones. On the champion
  (outputs O(1)) the absolute term dominates; measured deviation 7.2e-07.
  End-to-end deviations scale by `y_std` exactly (both predictions are the
  same linear function of the raw output).

## 3. One service, two backends, paired by construction

A single FastAPI app whose only backend switch is `--backend native|onnx`
(env-driven in the container). The benchmark feeds both backends
**byte-identical request streams** derived from the same seeded probe grid as
the parity gate — latency deltas attribute to the backend, not the load.
Percentiles are nearest-rank; cells report the median of 3 repeats with
warm-up excluded (experiment 08's discipline).

## 4. The harness starts the real service

`benchmark` spawns `python -m model_serving.cli serve` as a subprocess per
backend and gates on `/ready` — no in-process ASGI shortcuts, so the measured
latency includes uvicorn, pydantic validation, and the loader. RSS is probed
from fresh processes via `ps` after warm-up. The price is process-churn time;
the alternative (in-process TestClient) would measure nothing real.

## 5. Docker: repo-root context, venv at its final path, ownership at COPY

- Build context is the repository root because the uv workspace + `uv.lock`
  live there; the root `.dockerignore` excludes `**/data`, so the docker stage
  stages `data/models/` into `image/serving/` and the Dockerfile copies that.
- The venv is created **at its final path** (`/app/.venv`): venv console
  scripts embed absolute shebangs, so build-at-staging + copy breaks them.
- Ownership is set with `COPY --chown`, not a later `chown -R`: the chown
  would duplicate the whole 6.2 GB venv into a new layer and double the image
  (measured: 12.8 GB vs 6.5 GB after the fix — kept as the report's evidence
  for why the directive matters).
- When the daemon is absent the stage records `measured: false` and which
  numbers are missing; it never invents a size.

## 6. Honest cost framing, same as 08

Cost per 1k predictions = measured throughput at the concurrency knee ×
declared 65 W draw × $0.30/kWh. The wattage is an assumption (no wall meter)
and says so next to the number.

## Deliberately not built (skipped parts)

- TLS/auth, multi-worker/multi-replica, GPU serving — out of scope for one
  laptop study.
- A torch-free ONNX-only slim image — the paired harness needs both backends;
  stripping torch (and the unused 3.3 GB CUDA stack) is a production follow-up,
  noted in the story's limits.
- Showcase-API integration — Agent C wave (the project-local service is the
  deliverable here).
