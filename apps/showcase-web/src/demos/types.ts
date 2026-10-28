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

