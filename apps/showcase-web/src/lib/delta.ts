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

function headline(run: Record<string, unknown>): { metric: string; value: number } | null {
  const entries = numericEntries(run);
  return entries.length > 0 ? { metric: entries[0][0], value: entries[0][1] } : null;
}

export function isBaselineRun(run: string): boolean {
  return BASELINE_RE.test(run);
}

/** Format a metric value for display (integers plain, decimals to 4 places). */
export function formatMetricValue(value: number): string {
  return Number.isInteger(value) ? value.toString() : value.toFixed(4);
}

/**
 * Headline metric for a project card: the first numeric metric of the first
 * non-baseline run (baselines only as a last resort); null when nothing fits.
 */
export function pickHeadlineMetric(
  metrics: Metrics,
): { run: string; metric: string; value: number } | null {
  const runs = Object.keys(metrics).filter((r) => !r.startsWith("_"));
  const ordered = [...runs.filter((r) => !isBaselineRun(r)), ...runs.filter(isBaselineRun)];
  for (const run of ordered) {
    const h = headline(metrics[run]);
    if (h) return { run, metric: h.metric, value: h.value };
  }
  return null;
}

export function computeCallouts(metrics: Metrics, referencedRuns: string[]): MetricCallout[] {
  const present = referencedRuns.filter((r) => headline(metrics[r] ?? {}) !== null);
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
  const baselineHeadline = headline(baselineMetrics);

  // Every candidate gets its own delta vs the baseline (the baseline row
  // itself carries none). Prefer the baseline's value for the candidate's
  // headline metric; fall back to the baseline's headline.
  for (const c of callouts) {
    if (c.run === baselineRun) continue;
    const baselineValue =
      typeof baselineMetrics[c.metric] === "number"
        ? (baselineMetrics[c.metric] as number)
        : (baselineHeadline?.value ?? null);
    if (baselineValue === null || baselineValue === 0) continue;

    const deltaPct = ((c.value - baselineValue) / Math.abs(baselineValue)) * 100;
    c.deltaPct = deltaPct;
    c.baselineRun = baselineRun;
    c.improved = c.lowerIsBetter ? deltaPct < 0 : deltaPct > 0;
  }
  return callouts;
}
