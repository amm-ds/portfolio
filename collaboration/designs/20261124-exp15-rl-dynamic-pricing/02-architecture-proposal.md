# Project 15 Architecture Proposal — `projects/15-rl-dynamic-pricing`

Date: 2026-11-24
Author: Claude Code (Architect)
Design Brief: [01-design-brief.md](file:///Users/alejandro/work/portfolio/collaboration/designs/20261124-exp15-rl-dynamic-pricing/01-design-brief.md)

---

## 1. Repository & Workspace Integration

### Package Metadata (`projects/15-rl-dynamic-pricing/pyproject.toml`)
```toml
[project]
name = "15-rl-dynamic-pricing"
version = "0.1.0"
description = "Causal elasticity estimation and RL dynamic pricing with Gymnasium and Stable-Baselines3"
requires-python = ">=3.12"
dependencies = [
    "gymnasium>=1.0",
    "lightgbm>=4.0",
    "numpy>=2.1",
    "pandas>=2.0",
    "plotly>=5.24",
    "pydantic>=2.9",
    "pyyaml>=6.0",
    "scikit-learn>=1.5",
    "stable-baselines3>=2.4",
    "torch>=2.4",
    "typer>=0.12",
    "portfolio-core",
    "portfolio-eval",
]

[project.scripts]
rl-dynamic-pricing = "rl_dynamic_pricing.cli:app"

[tool.uv.sources]
portfolio-core = { workspace = true }
portfolio-eval = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/rl_dynamic_pricing"]
```

### Root `pyproject.toml` Wiring
- Auto-discovered via `members = ["libs/*", "projects/*", "apps/showcase-api"]`.
- Add `"rl_dynamic_pricing"` to:
  - `[tool.importlinter] root_packages`
  - `"projects are independent of each other"` contract `modules`
  - `"shared libs import nothing first-party"` contract `forbidden_modules`
  - `[[tool.mypy.overrides]]` with `strict = true`
  - `ignore_missing_imports = true` for `gymnasium.*`, `stable_baselines3.*`, `lightgbm.*`.

---

## 2. Module Layout (`src/rl_dynamic_pricing/`)

```text
projects/15-rl-dynamic-pricing/
├── portfolio.yaml
├── story.yaml
├── params.yaml
├── dvc.yaml
├── pyproject.toml
├── README.md
├── DESIGN.md
├── src/rl_dynamic_pricing/
│   ├── __init__.py
│   ├── cli.py              # Typer CLI: prepare, eda, elasticity, train, evaluate, report
│   ├── data.py             # Checksum-verified UCI Online Retail II loader, cleaning, SKU-day panel, temporal split
│   ├── elasticity.py       # Naive OLS vs cross-fitted Double ML (LightGBM nuisance models) + bootstrap SEs
│   ├── env.py              # RetailDynamicPricingEnv(gymnasium.Env) with inventory, holding, jump, stockout reward
│   ├── baselines.py        # Seeded random ensemble (16 seeds), static historical, cost-plus, myopic elasticity
│   ├── agents.py           # SB3 PPO & DQN trainers + deterministic rollout evaluator
│   ├── evaluate.py         # Out-of-time 200-episode eval, paired episode bootstrap (2000, seed 42), ±25% stress test
│   └── plots.py            # 4 Plotly figures (OLS vs DML elasticity, profit lift CI, inventory-price trajectory, stress test)
├── reports/
│   ├── metrics.json        # Committed metrics with _meta provenance + 95% CIs
│   ├── dq_report.md
│   ├── results.md
│   ├── report.html
│   └── figures/*.json
└── tests/
    ├── test_data_cleaning_and_split.py
    ├── test_double_ml_recovery.py
    ├── test_gym_env_contract.py
    ├── test_baselines_and_bootstrap.py
    └── test_cli_smoke.py
```

---

## 3. DVC Pipeline (`dvc.yaml`)

Six deterministic stages matching `projects/12-tabular-ml-lifecycle/dvc.yaml`:
1. `prepare` — Download/verify UCI Online Retail II (SHA-256 gate against `registry/uci-online-retail-ii.dvc`), clean cancellations/negatives, build top-SKU daily panel, enforce strict temporal splits (`train` / `val` / `test`), emit `data/dataset_contract.json` + `reports/dq_report.md`.
2. `eda` — Price dispersion per SKU, demand seasonality, cancellation rates, historical markup distribution.
3. `elasticity` — Fit Naive OLS and Cross-Fitted Double ML (`K=5` folds) on `train` panel, validate demand-prediction calibration on `val`, export per-SKU elasticity table + confounding gap.
4. `train` — Instantiate `RetailDynamicPricingEnv` calibrated from `train`+`val` demand parameters; tune reward penalties ($\lambda_{\text{hold}}, \lambda_{\text{jump}}, \lambda_{\text{stockout}}$) on `val` episodes; train `DQN` and `PPO` (`stable-baselines3`) with fixed seeds and save best checkpoints.
5. `evaluate` — Run all baselines (16-seed random ensemble, static historical, cost-plus, myopic elasticity) + `DQN` + `PPO` on `N = 200` locked `test` (`2011-05`–`2011-12`) episodes; run $\pm 25\%$ elasticity misspecification + COGS sensitivity sweeps; compute paired episode bootstrap 95% CIs (2,000 resamples, seed 42); write `reports/metrics.json` (stamped via `scripts/stamp_metrics_meta.py`).
6. `report` — Render 4 Plotly JSON figures (`reports/figures/*.json`), `reports/results.md`, and `reports/report.html`.

---

## 4. Environment & Policy Guardrails

- **Gymnasium Compliance:** `stable_baselines3.common.env_checker.check_env(env, warn=True)` MUST pass in CI tests.
- **No Reward Hacking:**
  - Demand is capped by remaining inventory (`units_sold = min(inventory, simulated_demand)`).
  - Price multipliers are bounded to `[-15%, +15%]` around the SKU's empirical reference price.
  - Price-jump penalty (`lambda_jump * |P_t - P_{t-1}|`) prevents ping-ponging between min/max prices every day.
  - Episode profit comparisons report **both** *Raw Gross Profit* (revenue minus COGS) and *Net Risk-Adjusted Profit* (including holding, volatility, and stockout penalties) so the reader sees whether PPO actually earns more real money, not just higher shaped reward!

---

## 5. Portfolio & Guardrail Integration

- **`story.yaml`:** 8-section contract + `short_version` (`<= 280` chars) + 5-card `roadmap` (`Data -> Training -> Evaluation -> Production -> Next`, 4 `shipped` + 1 `next`).
- **Showcase API & Web:** Register Project 15 in `apps/showcase-web/src/lib/cardCopy.ts`, regenerate `staticRegistry.ts`, `storyShort.ts`, `routeManifest.json`.
- **Headline Guard:** Add `_m15()` to `scripts/check_headline_numbers.py` verifying winning Net Profit Lift (%), Gross Profit Lift (%), Stockout Reduction (%), and DML negative-elasticity share across `README.md` and `story.yaml`.
- **Docs:** Add `docs/projects/15-rl-dynamic-pricing.md`, `docs/data-registry/uci-online-retail-ii.md`, and `registry/uci-online-retail-ii.dvc`; verify `uv run mkdocs build --strict`.
