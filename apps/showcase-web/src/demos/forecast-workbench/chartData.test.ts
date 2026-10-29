import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { ForecastWorkbenchPayload } from "../types";
import { assembleChartData } from "./chartData";

/** The REAL committed payload — the sweep below fails if any (series × origin
 * × horizon × models) assembly produces misaligned arrays, undefined values,
 * a dangling band reference, or a degenerate yMax. Vitest runs with
 * apps/showcase-web as cwd (same pattern as payload.test.ts). */
const payload = JSON.parse(
  readFileSync("../../projects/02-demand-forecasting/reports_m5/demo_payload.json", "utf8"),
) as ForecastWorkbenchPayload;

const HORIZONS = [7, 14, 21, 28];
const MODEL_SELECTIONS: string[][] = [
  ["seasonal_naive", "lgbm"],
  ["seasonal_naive", "auto_ets", "lgbm", "convex_ensemble"],
  ["seasonal_naive", "auto_ets", "lgbm", "lgbm_l2", "convex_ensemble", "ensemble_l2"],
  ["convex_ensemble"],
];

function assertFiniteRun(values: number[], from: number, to: number) {
  for (let i = from; i < to; i++) {
    expect(Number.isFinite(values[i]), `index ${i} of [${from}, ${to})`).toBe(true);
  }
}

describe("assembleChartData — real-payload sweep", () => {
  it("every series array aligns 1:1 with the axis for every series × origin × horizon × models", () => {
    let combos = 0;
    for (const entry of payload.catalog) {
      for (const [origin, win] of Object.entries(entry.origins)) {
        for (const h of HORIZONS) {
          for (const models of MODEL_SELECTIONS) {
            combos += 1;
            const spec = assembleChartData(win, models, h);
            const n = win.history.length + win.actual.length;
            expect(spec.x, `${entry.series_id}@${origin} h=${h}`).toHaveLength(n);
            expect(spec.take).toBe(h);
            for (const s of spec.series) {
              expect(s.values, `${s.name} ${entry.series_id}@${origin} h=${h}`).toHaveLength(n);
              // values are numbers or explicit NaN gaps — never undefined/null
              for (const v of s.values) {
                expect(typeof v).toBe("number");
              }
            }
          }
        }
      }
    }
    expect(combos).toBeGreaterThan(0);
  });

  it("band edges are finite exactly over the scored window and NaN elsewhere", () => {
    for (const entry of payload.catalog.slice(0, 6)) {
      for (const [origin, win] of Object.entries(entry.origins)) {
        for (const h of [7, 28]) {
          const spec = assembleChartData(win, ["seasonal_naive", "lgbm"], h);
          expect(spec.band, `band missing for ${entry.series_id}@${origin}`).not.toBeNull();
          const [lo, hi] = spec.band!;
          const p10 = spec.series[lo].values;
          const p90 = spec.series[hi].values;
          const hist = win.history.length;
          assertFiniteRun(p10, hist, hist + h);
          assertFiniteRun(p90, hist, hist + h);
          // history prefix and the tail beyond the horizon stay NaN
          for (let i = 0; i < hist; i++) {
            expect(Number.isNaN(p10[i])).toBe(true);
            expect(Number.isNaN(p90[i])).toBe(true);
          }
          for (let i = hist + h; i < p10.length; i++) {
            expect(Number.isNaN(p10[i])).toBe(true);
            expect(Number.isNaN(p90[i])).toBe(true);
          }
          // sorted band: p10 <= p90 inside the window
          for (let i = hist; i < hist + h; i++) {
            expect(p10[i]).toBeLessThanOrEqual(p90[i]);
          }
        }
      }
    }
  });

  it("yMax is finite and covers the visible window including the band", () => {
    for (const entry of payload.catalog) {
      for (const win of Object.values(entry.origins)) {
        const spec = assembleChartData(win, ["seasonal_naive", "lgbm"], 28);
        expect(Number.isFinite(spec.yMax)).toBe(true);
        expect(spec.yMax).toBeGreaterThan(0);
        const hist = win.history.length;
        const p90 = spec.series[spec.band![1]].values;
        for (let i = hist; i < hist + 28; i++) {
          expect(spec.yMax).toBeGreaterThanOrEqual(p90[i]);
        }
      }
    }
  });

  it("no band is emitted when lgbm is not selected", () => {
    const win = payload.catalog[0].origins[payload.origins[0].origin];
    expect(assembleChartData(win, ["seasonal_naive", "convex_ensemble"], 28).band).toBeNull();
  });

  it("carries the wave-28 L2 curves with distinct colors when all models are on", () => {
    const win = payload.catalog[0].origins[payload.origins[0].origin];
    const spec = assembleChartData(
      win,
      ["seasonal_naive", "auto_ets", "lgbm", "lgbm_l2", "convex_ensemble", "ensemble_l2"],
      28,
    );
    // history + actual + 6 candidates + 2 band edges
    expect(spec.series).toHaveLength(10);
    expect(spec.band).not.toBeNull();
    const byName = new Map(spec.series.map((s) => [s.name, s]));
    expect(byName.get("lgbm_l2")?.color).not.toBe(byName.get("lgbm")?.color);
    expect(byName.get("ensemble_l2")?.color).not.toBe(byName.get("convex_ensemble")?.color);
    expect(byName.get("lgbm_l2")?.color).not.toBe(byName.get("ensemble_l2")?.color);
  });
});
