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
  /** A demo mid-rebuild may declare no payload yet: the manifest still
   * serves and the payload route 404s until a payload block lands. */
  payload: PayloadRef | null;
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
  roc_auc: number;
}

// --- forecast workbench payload (`projects/02-demand-forecasting/reports_m5_full/demo_payload.json`, schema v4, protocol m5_full_v1) ---

/** The single scored-once window of one catalog series (origin 2016-05-22,
 * the competition window — the catalog carries one origin by design). */
export interface ForecastWindow {
  /** 56-day history tail ending at the origin day. */
  history: number[];
  /** 28-day actuals, origin + 1 .. origin + 28. */
  actual: number[];
  /** Per-candidate 28-day forecast curves (all 8 candidates). */
  curves: Record<string, number[]>;
  /** Ensemble member envelope (per-day min/max of the blend members) — an
   * envelope, NOT a calibrated prediction interval. */
  band: { lo: number[]; hi: number[] };
  /** Per-series window WAPE per candidate, computed from the curves. */
  wape: Record<string, number>;
}

export interface CatalogEntry {
  series_id: string;
  store: string;
  class: "dense" | "intermittent";
  adi: number;
  cv2: number;
  units_last_28d: number;
  half: "top_units" | "bottom_intermittency";
  windows: ForecastWindow;
}

export interface ForecastPooledMetrics {
  wape: number;
  wrmsse: number;
  bias: number;
  zero_day_accuracy: number;
  zero_day_accuracy_intermittent: number;
}

export interface ForecastWorkbenchPayload {
  schema_version: number;
  demo: string;
  project: string;
  protocol: string;
  /** Committed headline block (reports_m5_full metrics) verbatim. Panel-wide
   * where the committed run persisted panel stats; `_scope` records which
   * rows are catalog-scoped (carried for evidence/tests, not rendered). */
  groups: {
    headline: {
      metric: string;
      champion: string;
      champion_wrmsse: number;
      wrmsse_champion: { candidate: string; wrmsse: number };
      absolute_ensemble_wrmsse: number;
      convex_ensemble_vs_naive: {
        wrmsse: {
          diff: number;
          rel: number;
          ci95: [number, number] | null;
          spans_zero: boolean | null;
          note: string;
        };
      };
    };
    test_pooled: Record<string, ForecastPooledMetrics>;
    test_by_class: Record<
      string,
      { dense: { wape: number } | null; intermittent: { wape: number } | null }
    >;
    win_rate_vs_naive: Record<
      string,
      { pooled: number; dense: number | null; intermittent: number | null }
    >;
    stability: Record<string, number>;
    classes: {
      counts: { dense: number; intermittent: number };
      thresholds: { adi: number; cv2: number };
    };
    ensemble: {
      pool: string[];
      selection_screen: Record<string, { mean: number; std: number; score: number }>;
      members: string[];
      weights: number[];
      rule: string;
    };
    band: {
      method: string;
      level: number | null;
      per_horizon_width: number[];
      per_horizon_coverage: number[];
      candidates: Record<string, { mean_width: number }>;
    };
    /** Scope notes per block (panel vs catalog statistic) — displayed so a
     * catalog-scoped number is never read as a panel claim. */
    _scope: Record<string, string>;
  };
  catalog_rule: string;
  curve_provenance: string;
  history_days: number;
  origins: { origin: string; history_start: string; forecast_dates: string[] }[];
  catalog: CatalogEntry[];
  evaluation_metadata: {
    protocol: string;
    dataset: {
      dataset?: string;
      provenance_ref?: string;
      observed_panel: Record<string, unknown>;
      citation: string;
    };
    split: Record<string, unknown>;
    seeds: Record<string, number>;
    determinism?: string;
  };
}

