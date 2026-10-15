# Agentic AI Workflows

> Status: **working** — multi-step, stateful LLM workflows with typed graphs,
> tool orchestration, human checkpoints, and a deterministic evaluation harness.

- Problem: single-shot agents demo well, but production agentic systems need
  explicit multi-step control flow — planning, tool use, bounded retries, and
  human checkpoints — all of it auditable and measurable.
- Design: [DESIGN.md](DESIGN.md)
- Story: [story.yaml](story.yaml) (served at `/projects/09-agentic-workflows/story`)

## What is here

| Module | What it does |
|---|---|
| `tools.py` | Research-ops toolset (`calculator`, `unit_convert`, `search_handbook`, `note_store`) over a deterministic synthetic corpus, plus a `PrefixedToolset` composition demo (`math_*` tools, zero collisions) |
| `workflow.py` | pydantic-graph `Plan → Execute → Critique → End` workflow with typed state, a bounded repair path on validation failure, and a one-shot critique loop-back |
| `hitl.py` | Human-in-the-loop checkpoint: plan, pause with a typed `ApprovalRequest`, serialize to `data/checkpoint.json`, resume via CLI (approve / reject-with-feedback) |
| `evals.py` | 14-task synthetic suite with exact ground truths, `pydantic-evals` graders (answer success, tool selection, step budget, latency budget), report builder |
| `cli.py` | `prepare` / `run` / `run-all` / `evaluate` / `checkpoint request|approve|reject` |

## Results

See `reports/metrics.json` and `reports/report.html` (written by `evaluate`).
The published real run grades **8 of the 14 suite tasks** (ids
`t01,t03,t05,t07,t09,t10,t12,t13`, spanning all five categories): a full 14-task
run on the local 32B reasoning model exceeded two hours of wall clock, so the
run was bounded with `run-all --ids …` — the suite definition and all graders
cover the full 14, and `run-all` without flags runs everything. Headline
numbers are quoted in [story.yaml](story.yaml); grading is deterministic and
runs fully offline from `data/run_records.json`.

## Reproduce

```bash
# 1. Suite definition (offline)
uv run python -m agentic_workflows.cli prepare

# 2. Live run — needs a provider (ADR-0004): Ollama with qwen3:32b pulled,
#    or LLM_BASE_URL + LLM_API_KEY for an OpenAI-compatible endpoint
ollama pull qwen3:32b
uv run python -m agentic_workflows.cli run-all

# 3. Grading + figures + report (offline)
uv run python -m agentic_workflows.cli evaluate
```

Or via DVC: `dvc repro` (stages `prepare → run → evaluate`).

Single task and human checkpoint demos:

```bash
uv run python -m agentic_workflows.cli run t05
uv run python -m agentic_workflows.cli checkpoint request "Convert 48 km to miles"
uv run python -m agentic_workflows.cli checkpoint approve
uv run python -m agentic_workflows.cli checkpoint reject --feedback "Use fewer steps"
```

## Tests

Offline (scripted `FunctionModel`, no provider needed):

```bash
uv run pytest projects/09-agentic-workflows/tests
```
