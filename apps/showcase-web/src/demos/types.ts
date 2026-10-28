/** Shared demo-platform types. `DemoManifest` mirrors the pydantic model in
 * `libs/portfolio-core/src/portfolio_core/demo.py`; `DemoRegistryEntry` is the
 * fixed shape returned by `GET /demos` (sorted by group, id). The churn
 * payload interfaces moved here from the old sandbox module so both the
 * sandbox and tests import from one place. */

export interface HeroMetric {
  label: string;
  value: string;
  ci: string | null;
}

export interface Scenario {
  name: string;
  controls: Record<string, number | string | boolean>;
}

export interface LiveEndpoint {
  method: "GET" | "POST";
  path: string;
  label: string;
  cost: string;
}

export interface PayloadRef {
  path: string;
  schema_version: number;
  required_keys: string[];
}

export interface DemoManifest {
  id: string;
  title: string;
  hook: string;
  project: string;
  group: string;
  skills: string[];
  modes: string[];
  hero: HeroMetric | null;
  scenarios: Scenario[];
  live_endpoints: LiveEndpoint[];
  payload: PayloadRef;
}

/** Fixed registry-entry contract (`GET /demos`). */
export interface DemoRegistryEntry {
  id: string;
  title: string;
  hook: string;
  group: string;
  href: string;
  project: string;
  status: string;
  hero: HeroMetric | null;
}

// --- churn sandbox payload (`projects/05-ml-pipeline-churn/reports/demo_payload.json`) ---

export interface ConfusionRow {
  t: number;
  tn: number;
  fp: number;
  fn: number;
  tp: number;
}

export interface CalibrationBin {
  bin_lo: number;
  bin_hi: number;
  n: number;
  mean_predicted: number;
  observed: number;
}

export interface CustomerPreset {
  label: string;
  features: {
    tenure_months: number;
    monthly_charges: number;
    contract: string;
    internet_service: string;
  };
  churn_probability: number;
}

export interface ChurnPayload {
  demo: string;
  project: string;
  holdout_n: number;
  model: {
    name: string;
    roc_auc: number;
    ece: number;
    threshold_default: number;
    threshold_selected: number;
  };
  cost_model: { fp_cost: number; fn_cost: number; note: string };
  headline: {
    cost_naive: number;
    cost_selected: number;
    delta_ci: { point: number; lo: number; hi: number; significant_95: boolean };
  };
  thresholds: number[];
  overall: ConfusionRow[];
  slices: Record<string, Record<string, ConfusionRow[]>>;
  calibration: CalibrationBin[];
  customers: CustomerPreset[];
  feature_domains: {
    tenure_months: { min: number; max: number };
    monthly_charges: { min: number; max: number };
    contract: string[];
    internet_service: string[];
  };
  /** Optional URL of the written project report, surfaced in the evidence drawer. */
  report?: string;
  roc_auc: number;
}

// --- forecast workbench payload (`projects/02-demand-forecasting/reports_m5/demo_payload.json`, schema v4) ---

/** Candidate model names the demo can draw (per-series curves in each window;
 * `convex_ensemble` applies the committed selection rule to its members). */
export type ForecastModel = "seasonal_naive" | "auto_ets" | "lgbm" | "convex_ensemble";

/** The scored window of one catalog series at one test origin. */
export interface ForecastWindow {
  /** 56-day history tail ending at the origin day. */
  history: number[];
  /** 28-day actuals, origin + 1 .. origin + 28. */
  actual: number[];
  /** Per-candidate 28-day forecast curves (may include committed ensemble
   * members beyond the four demo candidates). */
  curves: Record<string, number[]>;
  /** lgbm split-conformal band (p10/p90) around the lgbm curve. */
  band: { p10: number[]; p90: number[] };
  /** Per-series test WAPE per candidate, computed from the curves. */
  wape: Record<string, number>;
  /** Deterministic shape tag: steady | weekly-peaked | event-driven | slow-mover. */
  shape: string;
}

export interface CatalogEntry {
  series_id: string;
  store: string;
  class: "dense" | "intermittent";
  adi: number;
  cv2: number;
  origins: Record<string, ForecastWindow>;
}

export interface ForecastPooledMetrics {
  mae: number;
  wape: number;
  rmae: number;
  wrmsse: number;
  wrmsse_weighted: number;
  peak_mae: number;
}

export interface ForecastWorkbenchPayload {
  schema_version: number;
  demo: string;
  project: string;
  protocol: string;
  /** Committed headline block (reports_m5 metrics/probabilistic) verbatim. */
  groups: {
    headline: {
      lgbm_vs_naive: {
        wape: { diff: number; ci95: [number, number]; spans_zero: boolean };
        wrmsse: { diff: number; ci95: [number, number]; spans_zero: boolean };
      };
      convex_ensemble_vs_naive: {
        wape: { diff: number; ci95: [number, number]; spans_zero: boolean };
        wrmsse: { diff: number; ci95: [number, number]; spans_zero: boolean };
      };
      baseline: string;
    };
    test_pooled: Record<string, ForecastPooledMetrics>;
    test_by_class: Record<string, Record<string, ForecastPooledMetrics | null>>;
    win_rate_vs_naive: Record<
      string,
      { pooled: number; dense: number | null; intermittent: number | null }
    >;
    classes: {
      counts: { dense: number; intermittent: number };
      thresholds: { adi: number; cv2: number };
    };
    ensemble: {
      pool: string[];
      selection_wape: Record<string, number>;
      members: string[];
      weight_on_a: number;
      rule: string;
    };
    band: {
      method: string;
      level: number;
      per_horizon_width: number[];
      candidates: Record<
        string,
        { pinball_p50: number; pinball_p90: number; coverage_80: number; mean_band_width: number }
      >;
    };
  };
  catalog_rule: string;
  curve_provenance: string;
  history_days: number;
  origins: { origin: string; history_start: string; forecast_dates: string[] }[];
  catalog: CatalogEntry[];
  evaluation_metadata: {
    protocol: string;
    dataset: {
      subset_rule: string;
      observed_panel: Record<string, unknown>;
      citation: string;
    };
    split: Record<string, unknown>;
    seeds: Record<string, number>;
    determinism: string;
  };
}

// --- uplift policy simulator payload (`projects/10-uplift-experimentation/reports/demo_payload.json`) ---

/** Policy profit matrix over the (cost × fraction) lattice: [costIdx][fracIdx],
 * values in total campaign profit ($). `ci` present for best_arm and random. */
export interface GridPolicy {
  profit: number[][];
  ci?: { lo: number[][]; hi: number[][] };
}

export type GridPolicyName = "best_arm" | "single_arm" | "random";

export interface ProfitGrid {
  costs: number[];
  fractions: number[];
  policies: Record<GridPolicyName, GridPolicy>;
  n_boot: number;
  seed: number;
  alpha: number;
  model_estimated: boolean;
  note: string;
}

/** Empirical per-arm Qini curve on the randomized arm-vs-control pairs,
 * downsampled to ≤100 points, with the arm's random line and coefficient. */
export interface QiniArmPoints {
  fractions: number[];
  incremental: number[];
  random_fractions: number[];
  random_incremental: number[];
  qini_coefficient: number;
  qini_ci: [number, number];
}

export interface UpliftSegmentStats {
  n: number;
  visit_rate: number;
  conversion_rate: number;
  mean_spend: number;
  incremental_conversions_full_send_model_estimated: { mens: number; womens: number };
}

/** Cumulative recommended-arm mix along the best-uplift ranking, sampled on
 * the same 1% lattice as `profit_grid.fractions`: shares of
 * mens/womens/none among the top-fraction of ranked customers. */
export interface ArmMixByFraction {
  fractions: number[];
  shares: { mens: number[]; womens: number[]; none: number[] };
}

export interface UpliftPayload {
  schema_version: number;
  demo: string;
  project: string;
  n_customers: number;
  scalars: {
    n_customers: number;
    revenue_per_conversion: number;
    cost_default: number;
    policy_budget: number;
    incremental_conversions_full_send_model_estimated: { mens: number; womens: number };
    incremental_conversions_full_send_best_arm: number;
    per_arm_qini: Record<
      "mens" | "womens",
      {
        qini_coefficient: number;
        qini_ci: [number, number];
        incremental_conversions_full: number;
        incremental_conversions_full_ci: [number, number];
        n_arm: number;
        n_control: number;
      }
    >;
    recommended_arm_shares: { mens: number; womens: number; none: number };
    break_even: {
      two_arm_committed: { cost_per_email: number; source: string };
      multi_arm_best_arm: { cost_per_email: number; vs: string; policy_budget: number; source: string };
    };
    /** Mail-everyone total profit per arm, keyed by cost with two-decimal
     * string keys ("0.01"…"0.50"). */
    mail_everyone_profit: { mens: Record<string, number>; womens: Record<string, number> };
    model_estimated_note: string;
  };
  profit_grid: ProfitGrid;
  qini_points: {
    mens: QiniArmPoints;
    womens: QiniArmPoints;
    random: { fractions: number[]; incremental: number[]; note: string };
  };
  arm_mix_by_fraction: ArmMixByFraction;
  segments: Record<"Mens E-Mail" | "Womens E-Mail" | "No E-Mail", UpliftSegmentStats>;
}

