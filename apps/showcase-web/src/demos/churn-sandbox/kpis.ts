import type { ConfusionRow } from "../types";

/** A zeroed row for out-of-range cursor indices / undefined rows: every kpi
 * function must degrade to safe values instead of throwing mid-drag. */
const ZERO_ROW: ConfusionRow = { t: 0, tn: 0, fp: 0, fn: 0, tp: 0 };

function safeRow(row: ConfusionRow | undefined | null): ConfusionRow {
  return row ?? ZERO_ROW;
}

function safeRatio(fnRatio: number): number {
  return Number.isFinite(fnRatio) && fnRatio > 0 ? fnRatio : 1;
}

/** cost(t) = fp_cost·FP + fn_cost·FN with fp_cost = 1 (per the payload cost model). */
export function rowCost(row: ConfusionRow | undefined | null, fnRatio: number): number {
  const r = safeRow(row);
  return r.fp + safeRatio(fnRatio) * r.fn;
}

/** Campaign cost at the cursor threshold, under the given miss multiplier. */
export function costAt(row: ConfusionRow | undefined | null, fnRatio: number): number {
  return rowCost(row, fnRatio);
}

/** FP-cost component across the threshold grid (fp_cost = 1 per the cost model). */
export function fpCostSeries(overall: ConfusionRow[]): number[] {
  return (overall ?? []).map((r) => safeRow(r).fp);
}

/** FN-cost component across the threshold grid, scaled by the miss multiplier. */
export function fnCostSeries(overall: ConfusionRow[], fnRatio: number): number[] {
  return (overall ?? []).map((r) => safeRatio(fnRatio) * safeRow(r).fn);
}

/** Cost delta vs the default 0.5 threshold (negative = savings). */
export function savings(
  row: ConfusionRow | undefined | null,
  defaultRow: ConfusionRow | undefined | null,
  fnRatio: number,
): number {
  return rowCost(row, fnRatio) - rowCost(defaultRow, fnRatio);
}

/** How many holdout customers get contacted at the cursor threshold. */
export function contactCount(row: ConfusionRow | undefined | null): number {
  const r = safeRow(row);
  return r.fp + r.tp;
}

/** Fraction of churners the campaign catches at the cursor threshold. */
export function recallAt(row: ConfusionRow | undefined | null): number {
  const r = safeRow(row);
  const churners = r.tp + r.fn;
  return churners === 0 ? 0 : r.tp / churners;
}

/** Index of the threshold grid value nearest to t. */
export function nearestIndex(thresholds: number[], t: number): number {
  if (!Array.isArray(thresholds) || thresholds.length === 0) return 0;
  let best = 0;
  for (let i = 1; i < thresholds.length; i++) {
    if (Math.abs(thresholds[i] - t) < Math.abs(thresholds[best] - t)) best = i;
  }
  return best;
}

/**
 * One-sentence, state-aware takeaway for the workbench Notice: what catching
 * one more churner costs at the cursor, given the current miss multiplier.
 * `laxer` is the confusion row one step toward contacting more customers
 * (lower threshold); when it catches no extra churners the sentence switches
 * to the recall ceiling.
 */
export function noticeText(
  cursorRow: ConfusionRow | undefined | null,
  laxer: ConfusionRow | null,
  fnRatio: number,
): string {
  const cursor = safeRow(cursorRow);
  if (laxer && laxer.tp > cursor.tp) {
    const gained = laxer.tp - cursor.tp;
    const extraAlarms = Math.max(laxer.fp + laxer.tp - (cursor.fp + cursor.tp), 0);
    const per = extraAlarms / gained;
    const rounded = per >= 10 ? Math.round(per) : Math.round(per * 10) / 10;
    return `At ${safeRatio(fnRatio)}× a miss, catching one more churner here costs ~${rounded} extra false alarms`;
  }
  const recall = Math.round(recallAt(cursor) * 100);
  return `At ${safeRatio(fnRatio)}× a miss this threshold already catches ${recall}% of churners — every additional alarm is a false one`;
}

/**
 * Where the cost-optimal cutoff sits at the current miss multiplier, relative
 * to the cursor. When the cursor is at the minimum the sentence affirms it;
 * otherwise it names the optimal threshold and the gap to the cursor, above or
 * below. Degrades to a safe prompt when the cursor row is out of range.
 */
export function optimalityText(
  overall: ConfusionRow[],
  cursorIdx: number,
  fnRatio: number,
): string {
  const rows = Array.isArray(overall) ? overall : [];
  const cursor = rows[cursorIdx];
  if (!cursor || rows.length === 0) {
    return "Move the cursor to compare against the cheapest cutoff.";
  }
  let bestIdx = 0;
  for (let i = 1; i < rows.length; i++) {
    if (rowCost(rows[i], fnRatio) < rowCost(rows[bestIdx], fnRatio)) bestIdx = i;
  }
  if (bestIdx === cursorIdx) {
    return `This is the cheapest cutoff for a ${safeRatio(fnRatio)}× miss cost`;
  }
  const optimal = safeRow(rows[bestIdx]);
  const direction = optimal.t > cursor.t ? "above" : "below";
  const gap = Math.abs(optimal.t - cursor.t).toFixed(2);
  return `The cheapest cutoff at ${safeRatio(fnRatio)}× is t = ${optimal.t.toFixed(2)} — ${direction} your cursor by ${gap}`;
}
