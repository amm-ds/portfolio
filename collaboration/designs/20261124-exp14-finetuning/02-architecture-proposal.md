# Project 14 Architecture Proposal — `projects/14-llm-finetuning`

Date: 2026-11-24
Author: Claude Code (Architect)
Design Brief: [01-design-brief.md](file:///Users/alejandro/work/portfolio/collaboration/designs/20261124-exp14-finetuning/01-design-brief.md)

---

## 1. Repository & Workspace Integration

### Package Metadata (`projects/14-llm-finetuning/pyproject.toml`)
```toml
[project]
name = "14-llm-finetuning"
version = "0.1.0"
description = "LoRA fine-tuning of Gemma and Qwen SLMs for structured intent classification"
requires-python = ">=3.12"
dependencies = [
    "numpy>=2.1",
    "pandas>=2.0",
    "plotly>=5.24",
    "pydantic>=2.9",
    "pyyaml>=6.0",
    "scikit-learn>=1.5",
    "typer>=0.12",
    "portfolio-core",
    "portfolio-eval",
]

[project.optional-dependencies]
mlx = [
    "mlx>=0.20; sys_platform == 'darwin' and platform_machine == 'arm64'",
    "mlx-lm>=0.20; sys_platform == 'darwin' and platform_machine == 'arm64'",
]
hf = [
    "datasets>=3.0",
    "peft>=0.13",
    "torch>=2.4",
    "transformers>=4.46",
    "trl>=0.12",
]

[project.scripts]
llm-finetuning = "llm_finetuning.cli:app"

[tool.uv.sources]
portfolio-core = { workspace = true }
portfolio-eval = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/llm_finetuning"]
```

### Root `pyproject.toml` Wiring
- Auto-discovered via `members = ["libs/*", "projects/*", "apps/showcase-api"]`.
- Add `"llm_finetuning"` to:
  - `[tool.importlinter] root_packages`
  - `"projects are independent of each other"` contract `modules`
  - `"shared libs import nothing first-party"` contract `forbidden_modules`
  - `[[tool.mypy.overrides]]` with `strict = true`
  - `ignore_missing_imports = true` for `mlx.*`, `mlx_lm.*`, `peft.*`, `trl.*` if imported under `TYPE_CHECKING` or lazy-imported.

---

## 2. Module Layout (`src/llm_finetuning/`)

```text
projects/14-llm-finetuning/
├── portfolio.yaml
├── story.yaml
├── params.yaml
├── dvc.yaml
├── pyproject.toml
├── README.md
├── DESIGN.md
├── src/llm_finetuning/
│   ├── __init__.py
│   ├── cli.py              # Typer CLI: prepare, eda, baseline, train, evaluate, report
│   ├── taxonomy.py         # Canonical 77 intents -> 8 coarse routing groups + Pydantic schema
│   ├── data.py             # Checksum-verified Banking77 loader, deterministic split, ChatML/JSONL formatter
│   ├── baselines.py        # TF-IDF+LogReg + Zero-Shot / 5-Shot evaluator
│   ├── trainer_mlx.py      # Lazy-imported mlx_lm.lora + mlx_lm.fuse wrapper (logs peak mem & tok/s)
│   ├── trainer_hf.py       # Portable trl.SFTTrainer + peft.LoraConfig config/runner builder
│   ├── evaluate.py         # Strict JSON parser, Macro-F1, Top-1 Acc, Wilson CI, Paired Row Bootstrap (2000, seed 42)
│   └── plots.py            # 4 interactive Plotly figures (lift ladder, scaling curve, confusion pairs, latency vs accuracy)
├── reports/
│   ├── metrics.json        # Committed metrics with _meta provenance + 95% CIs
│   ├── dq_report.md
│   ├── results.md
│   ├── report.html
│   └── figures/*.json
└── tests/
    ├── test_taxonomy_and_schema.py
    ├── test_data_split_leakage.py
    ├── test_eval_bootstrap_and_ci.py
    └── test_cli_offline_pipeline.py
```

---

## 3. DVC Pipeline (`dvc.yaml`)

Six deterministic stages matching `projects/12-tabular-ml-lifecycle/dvc.yaml`:
1. `prepare` — Download/verify `banking77` (SHA-256 gate against `registry/banking77.dvc`), build 8,500/1,503/3,080 splits + 300-row hard slice, emit `data/dataset_contract.json`, `reports/dq_report.md`, and ChatML `train.jsonl` / `valid.jsonl` / `test.jsonl`.
2. `eda` — Class distribution, query token-length quantiles, top overlapping intent clusters.
3. `baseline` — Train/evaluate TF-IDF + LogReg, Qwen zero-shot/5-shot, Gemma zero-shot/5-shot on `test` + `golden_hard`.
4. `train` — Run LoRA fine-tuning (`mlx_lm.lora`) for Qwen2.5-3B-Instruct and Gemma-3-4B-it across ablations (`r=8` vs `r=16`, data fractions `0.1/0.25/0.5/1.0`), fuse best adapters via `mlx_lm.fuse`, save adapter size + peak memory + throughput stats.
5. `evaluate` — Run locked `test` (3,080) and `golden_hard` (300) inference on winning Qwen + Gemma adapters, compute Wilson 95% CIs, paired row bootstrap (2,000 resamples, seed 42), nearest-rank p50/p95 latency, write `reports/metrics.json` (stamped with `scripts/stamp_metrics_meta.py`).
6. `report` — Render Plotly JSON figures (`reports/figures/*.json`), `reports/results.md`, and `reports/report.html`.

---

## 4. Strict Evaluation & Schema Contract

- **Zero Fallback Recovery:** Output parser runs `json.loads(raw_text)` and validates against a strict Pydantic v2 model (`IntentPrediction(intent: Literal[...77...], domain_group: Literal[...8...])`). If the model emits markdown fences, trailing commentary, or an unknown intent, the row is recorded as `schema_invalid = True` (never silently regex-repaired before scoring).
- **Paired Bootstrap Contract:** Both base and fine-tuned models run on identical row indices (`0..3079`). Bootstrap resamples row indices with replacement `2,000` times (`np.random.default_rng(42)`) to compute exact 2.5/97.5 percentile bounds on `Delta Macro-F1`, `Delta Accuracy`, and `Delta Schema Compliance`.

---

## 5. Portfolio & Guardrail Integration

- **`story.yaml`:** 8-section contract + `short_version` (`<= 280` chars) + 5-card `roadmap` (`Data -> Training -> Evaluation -> Production -> Next`, 4 `shipped` + 1 `next`).
- **Showcase API & Web:** Register Project 14 in `apps/showcase-web/src/lib/cardCopy.ts` (`CARD_DOES`, `CARD_ACHIEVES`, `CARD_TAGS`), regenerate `staticRegistry.ts`, `storyShort.ts`, `routeManifest.json`.
- **Headline Guard:** Add `_m14()` to `scripts/check_headline_numbers.py` verifying winning Macro-F1, Top-1 Accuracy, Zero-Shot-to-LoRA Lift, and Schema Compliance across `README.md` and `story.yaml`.
- **Docs:** Add `docs/projects/14-llm-finetuning.md`, `docs/data-registry/banking77.md`, and `registry/banking77.dvc`; verify `uv run mkdocs build --strict`.
