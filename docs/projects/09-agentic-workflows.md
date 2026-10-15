# Agentic AI Workflows

**Working showcase.** The platform's dedicated agentic-AI-workflows project:
multi-step, stateful LLM workflows as explicit typed graphs — planning, tool
orchestration, bounded retries, self-critique, and human-in-the-loop
checkpoints — graded by a deterministic evaluation harness with per-run cost
and latency budgets.

## Key results (real run, local `qwen3:32b` via Ollama)

Bounded run of **8 of the 14 suite tasks** (`run-all --ids …`, spanning all five
categories — a full 14-task run exceeded two hours on the reasoning model):

| metric | value |
|---|---|
| answer success | **6/8 (75%)** |
| tool-selection accuracy | **3/8 (37.5%)** — exact-set match; extra unprompted `note_store` calls miss |
| step budget | 8/8 |
| latency | median 474 s, p95 871 s per task (180 s budget held 1/8) |
| tokens / cost | ≈ 4.5k in + 1.6k out per task; ≈ $0.0017 at reference rate ($0 local) |
| failures | t07, t09 died at the plan node to reasoning-model empty-turn flakiness (`workflow_error`) |

| suite | 14 synthetic tasks, 5 categories (lookup, calculation, conversion, multi-step, note-keeping) |
|---|---|
| graders | answer success (exact keywords), tool selection (exact tool set), step budget, latency budget |
| judge | none — all graders are deterministic `pydantic-evals` evaluators |
| model | `qwen3:32b` on local Ollama (ADR-0004); env-provider override supported |

## Architecture

- **Tools & toolsets** — a "research ops" domain (fictional Atlas Valley field
  station): `calculator` (locked-down AST evaluator), `unit_convert`,
  `search_handbook` (deterministic 12-doc corpus), `note_store` (per-run
  notebook). A second math toolset is composed via `PrefixedToolset`
  (`math_percent_change`, `math_round_to`) — two toolsets, one agent, zero name
  collisions, unit-tested.
- **Workflow graph** — pydantic-graph `Plan → Execute → Critique → End` over a
  typed `WorkflowState`. Execute repairs on validation failure (bounded);
  Critique can loop back once; the graph ends with a structured
  `WorkflowResult` (answer, steps, tools used, calibrated confidence, tokens).
- **Human-in-the-loop** — a checkpoint node plans, then pauses: the typed
  `ApprovalRequest` + full state serialize to `data/checkpoint.json`; the CLI
  resumes with approve (continue at Execute) or reject-with-feedback (re-plan,
  then Execute). State on disk is the single source of truth.
- **Evaluation** — `pydantic-evals` dataset + custom evaluators; run stage
  (live LLM) and evaluate stage (offline grading) are separate DVC stages.

## Where things live

- Code + design: [projects/09-agentic-workflows](https://github.com/amm-ds/portfolio/tree/main/projects/09-agentic-workflows) —
  CLI `prepare | run | run-all | evaluate | checkpoint request|approve|reject`, DVC stages in `dvc.yaml`
- Options & rationale: [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/09-agentic-workflows/DESIGN.md)

## Reproduce

```bash
cd projects/09-agentic-workflows
ollama pull qwen3:32b
uv run python -m agentic_workflows.cli prepare
uv run python -m agentic_workflows.cli run-all     # live run (minutes)
uv run python -m agentic_workflows.cli evaluate    # offline grading → reports/
```

Tests are fully offline (scripted `FunctionModel`):
`uv run pytest projects/09-agentic-workflows/tests`
