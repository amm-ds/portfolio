import type { ArmMixByFraction, GridPolicyName, ProfitGrid } from "../types";

/** A zeroed policy row for out-of-range indices: every kpi function must
 * degrade to safe values instead of throwing mid-drag. */
const ZERO_ROW: number[] = [];

function safeRow(row: number[] | undefined | null): number[] {
  return row ?? ZERO_ROW;
}

/** Policy profit at one lattice point; 0 when either index is out of range. */
export function policyProfitAt(
  grid: ProfitGrid,
  policy: GridPolicyName,
  costIdx: number,
  fracIdx: number,
): number {
  const value = safeRow(grid.policies[policy]?.profit?.[costIdx])[fracIdx];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

/** Best-arm profit at one lattice point (the headline policy). */
export function profitAt(grid: ProfitGrid, costIdx: number, fracIdx: number): number {
  return policyProfitAt(grid, "best_arm", costIdx, fracIdx);
}

/** Who wins at the cursor: best-arm targeting at the budgeted fraction vs
 * mailing everyone the men's creative. Ties go to mail-everyone (the simpler
 * policy — targeting needs a clear edge to pay for itself). */
export function winnerAt(bestProfit: number, mailEveryoneProfit: number): "best_arm" | "mail_everyone_mens" {
  return bestProfit > mailEveryoneProfit ? "best_arm" : "mail_everyone_mens";
}

/** Targeted fraction where the best-arm profit row peaks at this cost. */
export function peakFractionAt(grid: ProfitGrid, costIdx: number): number {
  const row = safeRow(grid.policies.best_arm?.profit?.[costIdx]);
  if (row.length === 0) return grid.fractions[0] ?? 0;
  let best = 0;
  for (let i = 1; i < row.length; i++) {
    if (row[i] > row[best]) best = i;
  }
  return grid.fractions[best] ?? 0;
}

/**
 * Cost index where best-arm targeting at the given fraction overtakes
 * mail-everyone: the first index whose profit difference turns non-negative
 * after being negative. Returns 0 when targeting already wins at the cheapest
 * cost, null when it never does.
 */
export function crossoverCost(
  grid: ProfitGrid,
  fracIdx: number,
  mailEveryoneMens: number[],
): number | null {
  const rows = grid.policies.best_arm?.profit ?? [];
  let prev = Number.NaN;
  for (let c = 0; c < rows.length; c++) {
    const diff = (safeRow(rows[c])[fracIdx] ?? 0) - (mailEveryoneMens[c] ?? 0);
    if (diff >= 0) {
      return Number.isNaN(prev) || prev < 0 ? c : null;
    }
    prev = diff;
  }
  return null;
}

/** Mail-everyone profit at a cost; the payload keys the map with two-decimal
 * strings ("0.05"), so costs are formatted, not used as raw numbers. */
export function mailEveryoneAt(profitByCost: Record<string, number>, cost: number): number {
  return profitByCost[cost.toFixed(2)] ?? 0;
}

/**
 * Model-estimated incremental conversions behind a profit readout:
 * inverts profit(f, c) = inc(f)·revenue − f·N·c. Degrades to 0 for
 * non-finite inputs (mid-drag states).
 */
export function incrementalAt(
  profit: number,
  fraction: number,
  cost: number,
  nCustomers: number,
  revenuePerConversion: number,
): number {
  if (!(revenuePerConversion > 0)) return 0;
  const inc = (profit + fraction * nCustomers * cost) / revenuePerConversion;
  return Number.isFinite(inc) ? Math.max(inc, 0) : 0;
}

/** Index of the grid value nearest to v (threshold/fraction/cost grids). */
export function nearestIndex(grid: number[], v: number): number {
  if (!Array.isArray(grid) || grid.length === 0) return 0;
  let best = 0;
  for (let i = 1; i < grid.length; i++) {
    if (Math.abs(grid[i] - v) < Math.abs(grid[best] - v)) best = i;
  }
  return best;
}

/** Sampled (fractions, values) curve — the Qini payloads and the arm-mix
 * lattice all share this shape; linear interpolation reads between samples. */
interface SampledCurve {
  fractions: number[];
  values: number[];
}

/**
 * Linear interpolation of a sampled curve at `budget`, clamped to the sampled
 * domain. Degrades to the nearest endpoint when the curve has < 2 points or
 * the budget is non-finite (mid-drag states).
 */
export function sampleCurveAt(points: SampledCurve, budget: number): number {
  const { fractions, values } = points;
  if (fractions.length === 0 || values.length === 0) return 0;
  if (fractions.length === 1 || values.length === 1 || !Number.isFinite(budget)) {
    return values[nearestIndex(fractions, budget)] ?? 0;
  }
  if (budget <= fractions[0]) return values[0];
  const last = fractions.length - 1;
  if (budget >= fractions[last]) return values[last];
  let hi = 1;
  while (hi < fractions.length && fractions[hi] < budget) hi++;
  const lo = hi - 1;
  const w = (budget - fractions[lo]) / (fractions[hi] - fractions[lo]);
  return values[lo] + w * (values[hi] - values[lo]);
}

/** Incremental conversions captured at a targeted fraction, interpolated
 * linearly on a (downsampled) Qini curve. */
export function qiniCaptureAt(
  points: { fractions: number[]; incremental: number[] },
  budget: number,
): number {
  return sampleCurveAt({ fractions: points.fractions, values: points.incremental }, budget);
}

/** Recommended-arm shares among the top-`budget` of the best-uplift ranking,
 * interpolated at the budget on the arm-mix lattice. */
export function armMixAt(
  mix: ArmMixByFraction | undefined,
  budget: number,
): { mens: number; womens: number; none: number } {
  const shares = mix?.shares;
  if (!mix || !shares) return { mens: 0, womens: 0, none: 0 };
  return {
    mens: sampleCurveAt({ fractions: mix.fractions, values: shares.mens }, budget),
    womens: sampleCurveAt({ fractions: mix.fractions, values: shares.womens }, budget),
    none: sampleCurveAt({ fractions: mix.fractions, values: shares.none }, budget),
  };
}
