import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { ForecastWorkbenchPayload } from "../types";
import { MODELS, assembleChartData } from "./chartData";

/** The REAL committed payload — the sweep below fails if any (series ×
 * horizon × models) assembly produces misaligned arrays, undefined values,
 * a dangling envelope reference, or a degenerate yMax. Vitest runs with
 * apps/showcase-web as cwd (same pattern as payload.test.ts). */
const payload = JSON.parse(
  readFileSync("../../projects/02-demand-forecasting/reports_m5_full/demo_payload.json", "utf8"),
) as ForecastWorkbenchPayload;

const HORIZONS = [7, 14, 21, 28];
const MODEL_SELECTIONS: string[][] = [
  ["seasonal_naive", "lgbm"],
  ["seasonal_naive", "auto_ets", "lgbm", "convex_ensemble"],
  [
    "seasonal_naive",
    "auto_ets",
    "lgbm",
    "lgbm_tweedie",
    "lgbm_pool_store",
    "lgbm_pool_storecat",
    "lgbm_pool_dept",
    "convex_ensemble",
  ],
  ["convex_ensemble"],
];

function assertFiniteRun(values: number[], from: number, to: number) {
  for (let i = from; i < to; i++) {
    expect(Number.isFinite(values[i]), `index ${i} of [${from}, ${to})`).toBe(true);
  }
}

describe("assembleChartData — real-payload sweep", () => {
  it("every series array aligns 1:1 with the axis for every series × horizon × models", () => {
    let combos = 0;
    for (const entry of payload.catalog) {
      const win = entry.windows;
      for (const h of HORIZONS) {
        for (const models of MODEL_SELECTIONS) {
          combos += 1;
          const spec = assembleChartData(win, models, h);
          const n = win.history.length + win.actual.length;
          expect(spec.x, `${entry.series_id} h=${h}`).toHaveLength(n);
          expect(spec.take).toBe(h);
          for (const s of spec.series) {
            expect(s.values, `${s.name} ${entry.series_id} h=${h}`).toHaveLength(n);
            // values are numbers or explicit NaN gaps — never undefined/null
            for (const v of s.values) {
              expect(typeof v).toBe("number");
            }
          }
        }
      }
    }
    expect(combos).toBeGreaterThan(0);
  });

  it("envelope edges are finite exactly over the scored window and NaN elsewhere", () => {
    for (const entry of payload.catalog.slice(0, 6)) {
      const win = entry.windows;
      for (const h of [7, 28]) {
        const spec = assembleChartData(win, ["seasonal_naive", "convex_ensemble"], h);
        expect(spec.band, `envelope missing for ${entry.series_id}`).not.toBeNull();
        const [lo, hi] = spec.band!;
        const loV = spec.series[lo].values;
        const hiV = spec.series[hi].values;
        const hist = win.history.length;
        assertFiniteRun(loV, hist, hist + h);
        assertFiniteRun(hiV, hist, hist + h);
        // history prefix and the tail beyond the horizon stay NaN
        for (let i = 0; i < hist; i++) {
          expect(Number.isNaN(loV[i])).toBe(true);
          expect(Number.isNaN(hiV[i])).toBe(true);
        }
        for (let i = hist + h; i < loV.length; i++) {
          expect(Number.isNaN(loV[i])).toBe(true);
          expect(Number.isNaN(hiV[i])).toBe(true);
        }
        // sorted envelope: lo <= hi inside the window
        for (let i = hist; i < hist + h; i++) {
          expect(loV[i]).toBeLessThanOrEqual(hiV[i]);
        }
      }
    }
  });

  it("yMax is finite and covers the visible window including the envelope", () => {
    for (const entry of payload.catalog) {
      const win = entry.windows;
      const spec = assembleChartData(win, ["seasonal_naive", "convex_ensemble"], 28);
      expect(Number.isFinite(spec.yMax)).toBe(true);
      expect(spec.yMax).toBeGreaterThan(0);
      const hist = win.history.length;
      const hiV = spec.series[spec.band![1]].values;
      for (let i = hist; i < hist + 28; i++) {
        expect(spec.yMax).toBeGreaterThanOrEqual(hiV[i]);
      }
    }
  });

  it("no envelope is emitted when the ensemble is not selected", () => {
    const win = payload.catalog[0].windows;
    expect(assembleChartData(win, ["seasonal_naive", "lgbm"], 28).band).toBeNull();
  });

  it("carries all 8 candidates with distinct colors when every model is on", () => {
    const win = payload.catalog[0].windows;
    const all = MODELS.map((m) => m.key);
    const spec = assembleChartData(win, all, 28);
    // history + actual + 8 candidates + 2 envelope edges
    expect(spec.series).toHaveLength(12);
    expect(spec.band).not.toBeNull();
    const byName = new Map(spec.series.map((s) => [s.name, s]));
    const colors = MODELS.map((m) => byName.get(m.key)?.color);
    expect(new Set(colors).size).toBe(MODELS.length);
  });
});
