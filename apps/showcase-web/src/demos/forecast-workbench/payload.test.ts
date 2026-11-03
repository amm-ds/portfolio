import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { ForecastWorkbenchPayload } from "../types";

/** The REAL committed payload (built by `cli demo-payload-m5-full`) — the
 * contract test fails if the artifact drifts from what the UI reads. Vitest
 * runs with apps/showcase-web as cwd (same readFileSync pattern as
 * ProjectsIndex.test). */
const PAYLOAD_PATH = "../../projects/02-demand-forecasting/reports_m5_full/demo_payload.json";

const payload = JSON.parse(readFileSync(PAYLOAD_PATH, "utf8")) as ForecastWorkbenchPayload;

const ALL_CANDIDATES = [
  "seasonal_naive",
  "lgbm",
  "lgbm_tweedie",
  "lgbm_pool_store",
  "lgbm_pool_storecat",
  "lgbm_pool_dept",
  "auto_ets",
  "convex_ensemble",
];

describe("forecast-workbench payload contract (real committed JSON)", () => {
  it("carries the schema-v4 top-level contract for the full panel", () => {
    expect(payload.schema_version).toBe(4);
    expect(payload.demo).toBe("forecast-workbench");
    expect(payload.project).toBe("02-demand-forecasting");
    expect(payload.protocol).toBe("m5_full_v1");
    for (const key of ["demo", "project", "protocol", "catalog", "groups", "origins", "evaluation_metadata"]) {
      expect(payload).toHaveProperty(key);
    }
  });

  it("ships the 48-series catalog balanced across stores and halves", () => {
    expect(payload.catalog).toHaveLength(48);
    const byStore = new Map<string, number>();
    const halves = { top_units: 0, bottom_intermittency: 0 };
    for (const entry of payload.catalog) {
      byStore.set(entry.store, (byStore.get(entry.store) ?? 0) + 1);
      halves[entry.half] += 1;
      expect(entry.series_id.length).toBeGreaterThan(0);
      expect(entry.adi).toBeGreaterThan(0);
      expect(entry.cv2).toBeGreaterThan(0);
      expect(entry.units_last_28d).toBeGreaterThan(0);
      expect(["dense", "intermittent"]).toContain(entry.class);
    }
    expect([...byStore.keys()].sort()).toEqual([
      "CA_1",
      "CA_2",
      "CA_3",
      "CA_4",
      "TX_1",
      "TX_2",
      "TX_3",
      "WI_1",
    ]);
    expect(halves).toEqual({ top_units: 24, bottom_intermittency: 24 });
  });

  it("carries the single scored-once origin with full window shapes", () => {
    expect(payload.origins.map((o) => o.origin)).toEqual(["2016-05-22"]);
    expect(payload.history_days).toBe(56);
    for (const entry of payload.catalog) {
      const win = entry.windows;
      expect(win.history).toHaveLength(56);
      expect(win.actual).toHaveLength(28);
      expect(payload.origins[0].forecast_dates).toHaveLength(28);
      expect(Object.keys(win.curves).sort()).toEqual([...ALL_CANDIDATES].sort());
      for (const curve of Object.values(win.curves)) {
        expect(curve).toHaveLength(28);
      }
      expect(win.band.lo).toHaveLength(28);
      expect(win.band.hi).toHaveLength(28);
      // sorted, non-negative envelope
      for (let i = 0; i < 28; i++) {
        expect(win.band.lo[i]).toBeGreaterThanOrEqual(0);
        expect(win.band.lo[i]).toBeLessThanOrEqual(win.band.hi[i]);
      }
      // per-series WAPE row for every candidate
      expect(Object.keys(win.wape).sort()).toEqual([...ALL_CANDIDATES].sort());
    }
  });

  it("ships the committed headline block with the quoted numbers", () => {
    const { headline, test_pooled, win_rate_vs_naive, band, classes, stability } = payload.groups;
    expect(headline.metric).toBe("official_wrmsse");
    expect(headline.champion).toBe("convex_ensemble");
    expect(test_pooled.seasonal_naive.wrmsse).toBeCloseTo(0.8929, 3);
    expect(test_pooled.convex_ensemble.wrmsse).toBeCloseTo(0.6161, 3);
    expect(test_pooled.lgbm_pool_store.wrmsse).toBeCloseTo(0.6217, 3);
    expect(test_pooled.lgbm_pool_storecat.wrmsse).toBeCloseTo(0.6575, 3);
    expect(test_pooled.lgbm_pool_dept.wrmsse).toBeCloseTo(0.6313, 3);
    expect(test_pooled.lgbm_tweedie.wrmsse).toBeCloseTo(0.6473, 3);
    expect(test_pooled.lgbm.wrmsse).toBeCloseTo(0.6601, 3);
    expect(test_pooled.auto_ets.wrmsse).toBeCloseTo(0.7093, 3);
    // the pooled arms all beat the global model (the full-scale lesson)
    for (const pooled of ["lgbm_pool_store", "lgbm_pool_storecat", "lgbm_pool_dept"]) {
      expect(test_pooled[pooled].wrmsse).toBeLessThan(test_pooled.lgbm.wrmsse);
    }
    expect(headline.convex_ensemble_vs_naive.wrmsse.rel).toBeCloseTo(-0.31, 2);
    expect(test_pooled.seasonal_naive.wape).toBeCloseTo(0.9159, 3);
    expect(test_pooled.convex_ensemble.wape).toBeCloseTo(0.7633, 3);
    expect(test_pooled.convex_ensemble.bias).toBeCloseTo(0.0328, 3);
    expect(test_pooled.seasonal_naive.zero_day_accuracy).toBeCloseTo(0.6663, 3);
    expect(test_pooled.convex_ensemble.zero_day_accuracy).toBeCloseTo(0.5734, 3);
    expect(stability.convex_ensemble).toBeLessThan(0.001);
    // panel-wide class counts + the thin-screen stability caveat
    expect(classes.counts).toEqual({ dense: 2754, intermittent: 27736 });
    expect(win_rate_vs_naive.convex_ensemble.pooled).toBeCloseTo(0.5625, 3);
    // the envelope is a member min/max, not a calibrated interval
    expect(band.candidates.convex_ensemble.mean_width).toBeGreaterThan(0);
    expect(band.level).toBeNull();
    expect(band.per_horizon_coverage).toHaveLength(28);
    expect(band.per_horizon_width).toHaveLength(28);
  });

  it("ships the committed ensemble (members + weights) verbatim", () => {
    const ens = payload.groups.ensemble;
    expect(ens.members).toEqual(["lgbm_pool_storecat", "lgbm_pool_store", "lgbm_pool_dept"]);
    expect(ens.weights[0]).toBeCloseTo(0.6, 5);
    expect(ens.weights[1]).toBeCloseTo(0.1, 5);
    expect(ens.weights[2]).toBeCloseTo(0.3, 5);
    // the selection screen carries every pool candidate
    expect(Object.keys(ens.selection_screen).sort()).toEqual([...ens.pool].sort());
    for (const block of Object.values(ens.selection_screen)) {
      expect(block.score).toBeCloseTo(block.mean + block.std, 10);
    }
  });

  it("per-series WAPEs are consistent with the shipped curves", () => {
    for (const entry of payload.catalog.slice(0, 4)) {
      const win = entry.windows;
      const vol = win.actual.reduce((s, v) => s + v, 0);
      for (const [cand, wape] of Object.entries(win.wape)) {
        const curve = win.curves[cand];
        expect(curve, cand).toBeDefined();
        const err = win.actual.reduce((s, a, i) => s + Math.abs(curve[i] - a), 0);
        expect(wape).toBeCloseTo(err / vol, 3);
      }
    }
  });
});
