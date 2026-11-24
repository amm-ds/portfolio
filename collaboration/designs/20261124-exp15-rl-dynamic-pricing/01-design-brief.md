# Project 15 Design Brief — Dynamic Pricing with Reinforcement Learning & Causal Elasticity

Date: 2026-11-24
Author: Claude Code (Architect)
Status: Design Brief (awaiting owner approval before implementation handoff)
Target Package: `projects/15-rl-dynamic-pricing` (`rl_dynamic_pricing`)

---

## 1. Why This Project Exists (Portfolio Gap)

All 13 existing portfolio experiments cover supervised learning, forecasting, clustering, RAG, or serving. **None cover Sequential Decision-Making / Reinforcement Learning (RL) or Causal Econometrics.**

Dynamic pricing is a flagship sequential decision problem where myopic greedy optimization fails: raising prices aggressively today harvests short-term margin but causes stockouts before high-margin seasonal peaks or drives customer price-shock churn; conversely, underpricing depletes finite inventory early.

---

## 2. The Core Methodological Trap & Our Two-Stage Solution

Real observational retail logs only record *factual* demand at the historical price that was charged — they lack counterfactuals and suffer from **price confounding** (retailers raise prices during peak holiday demand, making naive regressions estimate *positive* price elasticity).

To solve this rigorously rather than inventing toy demand curves:
1. **Stage 1 — Causal Price Elasticity Estimation (Double Machine Learning):** Fit an orthogonalized Double ML model (`LightGBM` nuisance estimators for `E[log Q | X]` and `E[log P | X]`) on real historical retail panel data to recover **unbiased SKU-level price elasticity** ($\hat{\epsilon}_i < 0$), explicitly comparing **Naive OLS** vs **Double ML** to expose confounding bias.
2. **Stage 2 — Constrained Sequential Pricing Policy (Gymnasium + Stable-Baselines3 + Offline CQL):** Embed the calibrated empirical demand simulator + inventory dynamics into a `gymnasium.Env` (`RetailDynamicPricingEnv`) and train RL agents (**PPO** and **DQN**) with a **custom risk-adjusted pricing policy** (penalizing excessive price volatility and premature stockouts), benchmarked against static, cost-plus, myopic elasticity, and seeded random baselines.

---

## 3. Real Public Dataset & Temporal Split Discipline

### Primary Dataset: **UCI Online Retail II**
- **Source:** [UCI Machine Learning Repository — Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) (CC-BY-4.0), **~1.06M transaction rows** (2009-12-01 to 2011-12-09) from a UK online non-store giftware retailer (`InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, `Country`) (source-backed: [UCI ML Repository](https://archive.ics.uci.edu/dataset/502/online+retail+ii)).
- **Cleaning & SKU Selection Rules (Zero Leakage):**
  1. Remove cancellations (`InvoiceNo` starting with `'C'`), `Quantity <= 0`, `UnitPrice <= 0`, and non-product codes (`POST`, `DOT`, `M`, `BANK CHARGES`).
  2. Aggregate to **SKU-day panel** (`StockCode`, `date`, `units_sold`, `vwap_price`, `day_of_week`, `month`, `is_uk`).
  3. Select the top **20–30 high-velocity SKUs** that exhibit genuine historical price variation ($\ge 3$ distinct price points and $\ge 150$ active selling days) so elasticity estimation is statistically identifiable.
- **Strict Temporal Split:**
  | Split | Window | Purpose |
  |---|---|---|
  | `train` | `2009-12-01` to `2010-11-30` | Fit Double ML demand/elasticity model + RL simulator training |
  | `val` | `2010-12-01` to `2011-04-30` | Tune RL hyperparameters (`PPO`/`DQN`), reward penalty weights ($\lambda_{\text{jump}}, \lambda_{\text{stockout}}$) |
  | `test` | `2011-05-01` to `2011-12-09` | **Locked out-of-time evaluation** (`N = 200` SKU-30-day episodes) |

### Data Registry Contract (`registry/`)
- Register `registry/uci-online-retail-ii.dvc` (`dvc import-url --no-exec`) and `docs/data-registry/uci-online-retail-ii.md` per `registry/README.md`.
- `prepare` stage verifies SHA-256 checksum, logs row attrition (`raw -> cleaned -> top-SKU panel`), and emits `data/dataset_contract.json` + `reports/dq_report.md`.

---

## 4. Custom RL Environment & Policy Formulation

- **Environment (`RetailDynamicPricingEnv(gymnasium.Env)`):** 30-day (`T = 30`) replenishment-constrained SKU pricing horizon.
- **State Space ($s_t \in \mathbb{R}^7$):** `[norm_inventory, remaining_horizon_frac, lagged_demand_z, sin_dow, cos_dow, prev_price_ratio, estimated_elasticity_norm]`.
- **Action Space:** Discrete 7-tier relative price multipliers around historical anchor price `P_ref`: `[-15%, -10%, -5%, 0%, +5%, +10%, +15%]` (prevents unrealistic extreme pricing).
- **Custom Policy Reward ($R_t$):**
  $$R_t = \underbrace{(P_t - c_i) \cdot Q_t^{\text{sold}}}_{\text{Gross Profit}} - \underbrace{\lambda_{\text{hold}} \cdot I_t}_{\text{Holding Cost}} - \underbrace{\lambda_{\text{jump}} \cdot |P_t - P_{t-1}|}_{\text{Price-Volatility Penalty}} - \underbrace{\lambda_{\text{stockout}} \cdot \mathbb{I}(I_t = 0 \land t < T)}_{\text{Premature Stockout Penalty}}$$
  where unit cost $c_i$ is parameterized transparently (`0.55 * P_ref`, sensitivity-tested across `0.45..0.65`).

---

## 5. Baselines, RL Agents & Stress Tests

Evaluated identically across **`N = 200` locked out-of-time test episodes** (`2011-05` to `2011-12`):
1. **Seeded Random Ensemble (Null Baseline):** 16 fixed seeds uniformly sampling price tiers (mean + 2.5/97.5 percentile band per `statistical-intervals.md`).
2. **Static Historical Price:** Always selects `0%` multiplier (actual historical pricing benchmark).
3. **Cost-Plus Fixed Markup Rule:** Constant target margin policy.
4. **Myopic Elasticity Optimizer (Strong Analytical Baseline):** Solves 1-step $\arg\max_P (P - c_i) \cdot \hat{Q}(P, s_t)$ at each day without horizon/inventory lookahead or price-jump smoothing.
5. **RL Challengers (`stable-baselines3`):**
   - **DQN** (`MlpPolicy`, discrete Q-learning with target network & replay buffer).
   - **PPO** (`MlpPolicy`, clipped surrogate actor-critic) — primary custom policy candidate.
   - *(Optional stretch if wheel resolves cleanly)* **Offline CQL (`d3rlpy`)** trained strictly on logged historical trajectories without simulator rollouts.
6. **Sim-to-Real Robustness Stress Test:** Re-evaluate frozen `PPO`, `DQN`, and `Myopic` policies when true test demand elasticity shifts by **$\pm 25\%$** (`0.75x` and `1.25x` misspecification) and under **1.5x demand variance**.

---

## 6. SOTA Frameworks & CI Isolation

- **Causal Estimation:** Cross-fitted Double Machine Learning (`scikit-learn` + `lightgbm`, plus optional `econml` comparison) — zero exotic build dependencies on macOS `arm64` or Linux CI.
- **RL Stack:** `gymnasium>=1.0`, `stable-baselines3>=2.4`, `torch>=2.4` (CPU-fast MLP policies train 100k steps in ~30–60s on Apple Silicon or Linux).
- **CI Discipline:** `pytest` suite runs `gymnasium.utils.env_checker.check_env`, verifies reward/inventory conservation invariants, DML confounding test on a known synthetic DGP ($\epsilon_{\text{true}} = -1.8$), and fast smoke training (`2,000` steps) offline in `< 15s`.

---

## 7. Success Criteria & Statistical Reporting

Per `docs/engineering/statistical-intervals.md`:
- **Primary Metric:** Mean Episode **Net Risk-Adjusted Profit** and **Gross Profit Lift (%)** vs Static Historical and vs Myopic Elasticity Optimizer on `N = 200` held-out test episodes, with **paired episode bootstrap 95% CI (2,000 resamples, seed 42)**.
- **Success Gate:**
  1. DML recovers negative elasticity on >= 85% of selected SKUs (fixing positive-elasticity confounding seen in naive OLS).
  2. Winning RL policy (`PPO` or `DQN`) beats **both** Static Historical and Myopic Elasticity on Net Risk-Adjusted Profit with **paired bootstrap 95% CI excluding zero**.
  3. **Stockout Rate** reduced by **>= 25% relative** vs Myopic Optimizer and **Price Volatility** (`mean |ΔP| / P`) stays below an explicit guardrail (`<= 6%` per step).
  4. Policy retains positive profit lift under $\pm 25\%$ elasticity misspecification.
- **Provenance:** `reports/metrics.json` stamped via `scripts/stamp_metrics_meta.py` and guarded by `scripts/check_headline_numbers.py`.

---

## 8. Open Decisions for Owner Before Handoff

1. **Pure DoubleML (`scikit-learn`/`lightgbm`) vs `econml`:** `econml` occasionally pulls heavy transitive pins (`shap`, `numba`, `sparse`) that complicate `uv sync` on Python 3.12 + macOS `arm64`. Implementing exact orthogonalized cross-fitted Double ML directly with `lightgbm` + `scikit-learn` (with `econml` optional) keeps workspace resolution fast and clean — confirm preference.
2. **Include Offline RL (`d3rlpy` CQL) or focus on `SB3` PPO vs DQN + Myopic + Causal DML:** Confirm whether `PPO` + `DQN` in the DML-calibrated Gymnasium simulator + $\pm 25\%$ misspecification stress test is the right v1 scope (keeping `d3rlpy` for a follow-up if Python 3.12 wheels are not clean).
3. **Cost Parameterization:** Confirm `unit_cost = 0.55 * P_ref` with `0.45 / 0.55 / 0.65` sensitivity sweep (since UCI Online Retail II does not publish wholesale COGS).
