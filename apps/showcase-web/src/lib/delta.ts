import type { Metrics } from "../api";

// Baseline-delta logic for story metric results. A referenced run whose name
// matches BASELINE_RE (naive/random/lag/majority/persistence) is a baseline;
// EVERY non-baseline run gets a signed delta vs the first baseline
// ("−28% vs naive_last"), shown in the story results table — rows whose
// metric cannot be compared against the baseline keep a null delta.

export interface MetricCallout {
  run: string;
  metric: string;
  value: number;
  lowerIsBetter: boolean;
  /** Signed percent vs the baseline run; null when no baseline applies. */
  deltaPct: number | null;
  baselineRun: string | null;
  /** Whether the delta is an improvement (for coloring). */
  improved: boolean | null;
}

const BASELINE_RE = /naive|random|lag|majority|persistence/i;
const LOWER_IS_BETTER_RE = /mae|rmse|mse|error|loss|wer|latency|mape/i;

function numericEntries(run: Record<string, unknown>): [string, number][] {
  return Object.entries(run).filter((e): e is [string, number] => typeof e[1] === "number");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const PREFERRED_METRICS = [
  "profit_at_budget",
  "qini_coefficient",
  "f1",
  "pr_auc",
  "roc_auc",
  "mae",
  "wrmsse",
];

/** Headline numeric metric of a run; prefers decision metrics over constant
 *  full-population totals when present, and returns null for non-run records. */
function headline(value: unknown): { metric: string; value: number } | null {
  if (!isRecord(value)) return null;
  const entries = numericEntries(value);
  if (entries.length === 0) return null;
  for (const key of PREFERRED_METRICS) {
    const match = entries.find(([k]) => k === key);
    if (match) return { metric: match[0], value: match[1] };
  }
  return { metric: entries[0][0], value: entries[0][1] };
}

export function isBaselineRun(run: string): boolean {
  return BASELINE_RE.test(run);
}

/** Format a metric value for display (integers plain, decimals to 4 places). */
export function formatMetricValue(value: number): string {
  return Number.isInteger(value) ? value.toString() : value.toFixed(4);
}

/**
 * Headline metric for a project card: a metrics file may declare its champion
 * run (`_meta.champion`) — that run carries the headline ahead of ladder
 * order; otherwise the first numeric metric of the first non-baseline run
 * (baselines only as a last resort); null when nothing fits.
 */
export function pickHeadlineMetric(
  metrics: Metrics,
): { run: string; metric: string; value: number } | null {
  const meta = metrics["_meta"];
  const champion = isRecord(meta) ? meta.champion : undefined;
  if (typeof champion === "string") {
    const h = headline(metrics[champion]);
    if (h) return { run: champion, metric: h.metric, value: h.value };
  }
  const runs = Object.keys(metrics).filter((r) => !r.startsWith("_"));
  const ordered = [...runs.filter((r) => !isBaselineRun(r)), ...runs.filter(isBaselineRun)];
  for (const run of ordered) {
    const h = headline(metrics[run]);
    if (h) return { run, metric: h.metric, value: h.value };
  }
  return null;
}

export function computeCallouts(metrics: Metrics, referencedRuns: string[]): MetricCallout[] {
  const present = referencedRuns.filter((r) => headline(metrics[r]) !== null);
  const callouts: MetricCallout[] = present.map((run) => {
    const h = headline(metrics[run])!;
    return {
      run,
      metric: h.metric,
      value: h.value,
      lowerIsBetter: LOWER_IS_BETTER_RE.test(h.metric),
      deltaPct: null,
      baselineRun: null,
      improved: null,
    };
  });

  const baselines = present.filter(isBaselineRun);
  const candidates = present.filter((r) => !isBaselineRun(r));
  if (baselines.length === 0 || candidates.length === 0) return callouts;

  const baselineRun = baselines[0];
  const baselineMetrics = metrics[baselineRun];

  // Every candidate gets its own delta vs the baseline (the baseline row
  // itself carries none) — but ONLY on the same metric. Comparing a run's
  // headline against the baseline's headline when the names differ produces
  // nonsense (e.g. agent faithfulness "vs" random-chunk recall@5); such rows
  // show no delta.
  for (const c of callouts) {
    if (c.run === baselineRun) continue;
    const baselineValue = isRecord(baselineMetrics) ? baselineMetrics[c.metric] : undefined;
    if (typeof baselineValue !== "number" || baselineValue === 0) continue;

    const deltaPct = ((c.value - baselineValue) / Math.abs(baselineValue)) * 100;
    c.deltaPct = deltaPct;
    c.baselineRun = baselineRun;
    c.improved = c.lowerIsBetter ? deltaPct < 0 : deltaPct > 0;
  }
  return callouts;
}
