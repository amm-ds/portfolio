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
// Schema v3 (+ payload_revision "3.2"): the DIRECT MULTI-HORIZON catalog
// (protocol direct_multihorizon_v1) on the FULL h = 1..14 lattice — every
// model curve is a contiguous 14-day series (one real direct-h point per
// window day, no interpolated display points). Every catalog series carries
// its ADI/CV² class and committed routing method (`model_used`), plus the 3
// most recent scored weekly origins — each with an as-of-origin history
// (ends the day BEFORE the origin), 14 contiguous days of actuals (starting
// the day AFTER — no embargo gap), and per-model direct curves at every
// h = 1..14. Built by `demand_forecasting.demo_payload`.

/** Syntetos-Boylan ADI/CV² classes present in the UCI panel. */
export type DemandClass = "erratic" | "lumpy";

/** Model chips: `zero` is the naive baseline, `routed` the committed
 * per-series routing method, `champion` the boosted per-horizon direct HGB
 * (erratic series only), `hurdle` / `tweedie` the wave-20 peak-capable
 * candidates — enabled only on the series the committed router selected
 * them for (their curve IS the routed curve there). */
export type ModelKey = "zero" | "routed" | "champion" | "hurdle" | "tweedie";

/** The committed per-series routing decision (chosen on the selection
 * origins only): sparse series among zero/seasonal-naive/Croston/SBA/TSB +
 * the peak-capable ML candidates; smooth/erratic among direct_hgb + the ML
 * candidates. */
export type RoutedMethod =
  | "direct_hgb"
  | "zero"
  | "seasonal_naive"
  | "croston"
  | "sba"
  | "tsb"
  | "hurdle_hgb"
  | "hgb_tweedie";

/** One model's direct curve at one origin: one point per horizon h (aligned
 * with `OriginBlock.horizons`). `shock` carries the precomputed exact
 * re-scores under a demand shock of the last 7 days (0.5x/1.5x/2x); 1x is
 * the base `y_pred` itself. */
export interface DirectModelBlock {
  y_pred: number[];
  /** Learner rows only (erratic): the committed per-h conformal band. */
  p10?: number[];
  p90?: number[];
  /** Sparse rows only (lumpy): P(any sale) + the training-history quantile
   * ladder — an honest sparse band that cannot collapse to zero width. */
  band?: { p_sale: number; ladder: Record<string, number> };
  shock: Record<string, number[]>;
}

/** Revision 3.1 marker: a peak-capable candidate the router selected for this
 * series — its curve IS the routed curve, aliased to avoid duplicating bytes. */
export interface CandidateAlias {
  alias: "routed";
}

export type ModelEntry = DirectModelBlock | CandidateAlias;

/** One series at one scored origin. The origin marker IS the information
 * cutoff: `history` ends the day before it, `actuals` start the day after. */
export interface OriginBlock {
  origin_date: string;
  history: { dates: string[]; y: number[] };
  actuals: { dates: string[]; y: number[] };
  /** The committed h-lattice the direct curves are aligned to. */
  horizons: number[];
  /** Seasonal-naive scale of the emitted history (0 → MASE undefined). */
  scale: number;
  models: {
    zero: DirectModelBlock;
    routed: DirectModelBlock;
    /** Seasonal-naive floor (drives the decision layer). */
    floor: DirectModelBlock;
    /** Erratic series only — the boosted per-horizon direct HGB. */
    champion_hgb?: DirectModelBlock;
    /** Revision 3.1: present only when the router selected the candidate for
     * this series — the alias marker `{"alias": "routed"}`. */
    hurdle_hgb?: ModelEntry;
    hgb_tweedie?: ModelEntry;
  };
}

/** One catalog series. */
export interface CatalogSeries {
  series_id: string;
  label: string;
  country: string;
  product: string;
  demand_class: DemandClass;
  adi: number;
  /** Squared coefficient of variation (null when infinite — always zero). */
  cv2: number | null;
  /** Which model produced the `routed` curve — the committed routing table. */
  model_used: RoutedMethod;
  origins: OriginBlock[];
}

export interface BootstrapResult {
  diff: number;
  ci95: [number, number];
  spans_zero: boolean;
  n_boot: number;
  seed: number;
}

/** Per ADI/CV² class: committed pooled numbers plus the per-series
 * beats-floor counts recomputed from the drift-guarded re-run cells. */
export interface ScoreboardClass {
  n_series: number;
  beats_floor: Record<string, { count: number; n: number; share: number | null }>;
  mae: Record<string, { model: number; floor: number }>;
  gap_bootstrap: Record<string, BootstrapResult>;
  vs_zero_bootstrap: Record<string, BootstrapResult>;
  /** Revision 3.1: the wave-20 peak-capable candidates' committed rows per
   * horizon (pooled MAE + paired-bootstrap gaps vs routed and vs zero). */
  candidates?: Record<string, Record<string, CandidateScoreboardRow | undefined>>;
  routing_effect: BootstrapResult | null;
}

/** One candidate × horizon scoreboard row (committed). */
export interface CandidateScoreboardRow {
  mae: number;
  vs_routed: BootstrapResult | null;
  vs_zero: BootstrapResult | null;
}

/** One candidate's committed peak-capture numbers per class. */
export interface PeakCandidateStats {
  peak_mae: number;
  peak_recall: number;
  peak_mae_vs_zero?: BootstrapResult;
  peak_mae_vs_routed?: BootstrapResult;
  peak_recall_vs_zero?: BootstrapResult;
  peak_recall_vs_routed?: BootstrapResult;
}

/** One class' committed peak-capture numbers (every peak candidate + the
 * zero baseline), with the scored-window count. */
export interface PeakClassEntry {
  n_windows: number;
  routed?: PeakCandidateStats;
  zero?: PeakCandidateStats;
  hgb_tweedie?: PeakCandidateStats;
  hurdle_hgb?: PeakCandidateStats;
}

/** The committed peak-capture block (wave 20): per scored window, peak_mae on
 * the top-decile-by-actual days + peak timing recall, per class, with paired
 * bootstrap CIs. */
export interface PeakCaptureBlock {
  definition: string;
  candidates: string[];
  top_k_days: number;
  top_recall_days: number;
  bootstrap: { method: string; n_boot: number; seed: number };
  per_class: Record<string, PeakClassEntry>;
}

/** Pooled error vs the TRUE horizon h (direct per-h models). */
export interface HorizonGrowth {
  horizons: number[];
  pooled: Record<"routed" | "seasonal_naive" | "zero", Record<string, number>>;
  /** Pooled MASE per h (null where the pooled seasonal scale is zero). */
  mase: { champion: Record<string, number | null>; floor: Record<string, number | null> };
  per_class: Record<string, Record<"routed" | "seasonal_naive", Record<string, number>>>;
  note: string;
}

/** The committed per-horizon band calibration (pooled over scored origins). */
export interface BandsBlock {
  target_coverage: number;
  band_types: Record<string, string>;
  conformal_widths_by_h: Record<string, number>;
  per_horizon: Record<
    string,
    {
      coverage: number;
      avg_width: number;
      calibration_verdict: string;
      learner_coverage: number;
      sparse_coverage: number;
      pinball_p10: number;
      pinball_p50: number;
      pinball_p90: number;
    }
  >;
  pooled_coverage: number;
  pooled_verdict: string;
  sparse_ladder_levels: number[];
  note: string;
}

/** The committed order-up-to simulation plus the τ→quantile mapping:
 * order(origin, h, τ) = max(point + offset, 0) with offsets per
 * (class, policy, h) from the policy's selection-origin residuals. */
export interface DecisionBlock {
  simulation: boolean;
  label: string;
  cost_assumptions: {
    holding_cost_per_unit: number;
    stockout_cost_per_unit_short: number;
    cost_basis: string;
  };
  service_levels: number[];
  per_class: Record<
    string,
    Record<
      string,
      {
        champion: number;
        champion_per_unit_demand: number;
        floor: number;
        floor_per_unit_demand: number;
        delta_champion_minus_floor: number;
      }
    >
  >;
  /** τ stops as two-decimal strings (JSON keys of the quantile map). */
  tau_grid: string[];
  quantile_map: Record<
    string,
    Record<"champion" | "floor", Record<string, Record<string, number>>>
  >;
  mapping_note: string;
}

export interface ForecastPayload {
  schema_version: number;
  /** Additive revisions on top of schema v3: "3.1" (wave 20) candidate
   * aliases per series, `peak_capture`, `class_scoreboard.candidates`;
   * "3.2" (full lattice) contiguous 14-day curves at every h = 1..14. */
  payload_revision?: string;
  demo: string;
  project: string;
  track: string;
  protocol: string;
  catalog: CatalogSeries[];
  class_scoreboard: Record<DemandClass, ScoreboardClass>;
  horizon_growth: HorizonGrowth;
  peak_capture: PeakCaptureBlock;
  bands: BandsBlock;
  decision: DecisionBlock;
  headline: {
    claim: string;
    pooled_mae_by_model: Record<string, number>;
    routing_win_lumpy: BootstrapResult | null;
    n_series_experiment: number;
    class_counts: Record<string, number>;
    sparse_share: number;
  };
  catalog_summary: {
    n_series: number;
    by_class: Record<string, number>;
    countries: Record<string, number>;
    model_used_counts: Record<string, number>;
    origins: Array<{ origin_date: string; horizon_window: [string, string] }>;
    history_days: number;
    horizon_days: number;
    horizons: number[];
    shock_factors: number[];
    shock_note: string;
    routing_rule: string;
    /** The full committed candidate list + the wave-20 peak-capable
     * candidates' one-line definitions. */
    candidates?: string[];
    peak_capable_candidates?: Record<string, string>;
    class_thresholds: { adi: number; cv2: number };
    experiment_origins: {
      n_origins: number;
      dates: string[];
      selection_dates: string[];
      test_dates: string[];
      spacing_days: number;
      gap_days: number;
      cap_note: string;
    };
  };
  evaluation_metadata: {
    protocol: string;
    track: string;
    horizons: number[];
    window_days: number;
    origins: ForecastPayload["catalog_summary"]["experiment_origins"];
    holdout_designation: string;
    selection_rule: string;
    feature_semantics: string;
    uncertainty: string;
    metric_definitions: Record<string, string>;
    target_definition: string;
    nowcast_track_note: string;
  };
  dataset_metadata: {
    dataset: string;
    source: { url: string; sha256: string; sheet: string; license: string };
    cancellation_filtering: string;
    quantity_handling: string;
    geography: string;
    products: string;
    daily_aggregation: string;
    observed_panel: {
      date_start: string;
      date_end: string;
      n_days: number;
      n_rows: number;
      n_series: number;
      zero_share: number;
    };
    zero_sales_caveat: string;
    target_definition: string;
    intermittency?: {
      method: string;
      thresholds: { adi: number; cv2: number };
      class_counts: Record<string, number>;
      routing_rule: string;
    };
  };
}
