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

// --- demand forecast workbench payload (`projects/02-demand-forecasting/reports/demo_payload.json`) ---

/** One catalog series: committed history, the last-fold backtest window with
 * champion/naive forecasts and the p10/p90 band, and the per-horizon errors.
 * `mase` entries are null for all-zero-history (sparse) series, whose
 * seasonal-naive scale is 0 — callers must render "n/a", never NaN. */
export interface CatalogSeries {
  series_id: string;
  label: string;
  demand_class: "smooth" | "intermittent" | "sparse";
  history: { dates: string[]; y: number[] };
  forecast: {
    dates: string[];
    y_pred: number[];
    p10: number[];
    p90: number[];
    naive: number[];
  };
  errors: {
    /** In-sample seasonal-naive scale of the stored history (0 → MASE undefined). */
    scale: number;
    champion: { mae: number[]; mase: (number | null)[] };
    naive: { mae: number[]; mase: (number | null)[] };
  };
}

export interface ForecastPayload {
  schema_version: number;
  demo: string;
  project: string;
  track: string;
  catalog: CatalogSeries[];
  scalars: {
    headline: {
      claim: string;
      champion: string;
      champion_mase: number;
      champion_mae: number;
      naive_mase: number;
      only_champion_below_mase_1: boolean;
      mase_by_model: Record<string, number>;
    };
    band: {
      target_coverage: number;
      quantile_coverage_pooled: number;
      split_conformal_coverage_last_fold: number;
      note: string;
    } | null;
    models: {
      champion: string;
      global: string;
      naive: string;
      selection_rule: string;
    };
    feature_schema: {
      calendar: string[];
      lags: string[];
      series: string;
      note: string;
    };
    catalog_summary: {
      n_series: number;
      by_class: { smooth: number; intermittent: number; sparse: number };
      history_days: number;
      horizon_days: number;
      forecast_window: [string, string];
      class_thresholds: {
        zero_frac_smooth_max: number;
        zero_frac_intermittent_max: number;
      };
    };
  };
}
