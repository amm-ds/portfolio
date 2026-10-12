import type { Metrics } from "../api";

// Baseline-delta logic for story metric callouts. A referenced run whose name
// matches BASELINE_RE (naive/random/lag/majority/persistence) is a baseline;
// the best non-baseline run gets a signed delta chip relative to the first
// baseline ("MAE −28% vs naive_last").

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

  // Best candidate by its own headline metric direction.
  const bestRun = candidates.reduce((best, r) => {
    const a = headline(metrics[r])!;
    const b = headline(metrics[best])!;
    const lower = LOWER_IS_BETTER_RE.test(b.metric);
    return lower ? (a.value < b.value ? r : best) : a.value > b.value ? r : best;
  });

  const baselineRun = baselines[0];
  const bestCallout = callouts.find((c) => c.run === bestRun)!;
  // Prefer the baseline's value for the same metric; fall back to its headline.
  const baselineMetrics = metrics[baselineRun];
  const baselineValue =
    typeof baselineMetrics[bestCallout.metric] === "number"
      ? (baselineMetrics[bestCallout.metric] as number)
      : (headline(baselineMetrics)?.value ?? null);
  if (baselineValue === null || baselineValue === 0) return callouts;

  const deltaPct = ((bestCallout.value - baselineValue) / Math.abs(baselineValue)) * 100;
  bestCallout.deltaPct = deltaPct;
  bestCallout.baselineRun = baselineRun;
  bestCallout.improved = bestCallout.lowerIsBetter ? deltaPct < 0 : deltaPct > 0;
  return callouts;
}
