import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { ForecastWorkbenchPayload } from "../types";

/** The REAL committed payload (built by `cli demo-payload-m5`) — the contract
 * test fails if the artifact drifts from what the UI reads. Vitest runs with
 * apps/showcase-web as cwd (same readFileSync pattern as ProjectsIndex.test). */
const PAYLOAD_PATH = "../../projects/02-demand-forecasting/reports_m5/demo_payload.json";

const payload = JSON.parse(readFileSync(PAYLOAD_PATH, "utf8")) as ForecastWorkbenchPayload;

describe("forecast-workbench payload contract (real committed JSON)", () => {
  it("carries the schema-v4 top-level contract", () => {
    expect(payload.schema_version).toBe(4);
    expect(payload.demo).toBe("forecast-workbench");
    expect(payload.project).toBe("02-demand-forecasting");
    expect(payload.protocol).toBe("m5_direct_v1");
    for (const key of ["demo", "project", "protocol", "catalog", "groups", "evaluation_metadata"]) {
      expect(payload).toHaveProperty(key);
    }
  });

  it("ships a 24-series catalog balanced across stores × classes", () => {
    expect(payload.catalog).toHaveLength(24);
    const byStore = new Map<string, { dense: number; intermittent: number }>();
    for (const entry of payload.catalog) {
      const bucket = byStore.get(entry.store) ?? { dense: 0, intermittent: 0 };
      bucket[entry.class] += 1;
      byStore.set(entry.store, bucket);
      expect(entry.series_id.length).toBeGreaterThan(0);
      expect(entry.adi).toBeGreaterThan(0);
      expect(entry.cv2).toBeGreaterThan(0);
    }
    expect([...byStore.keys()].sort()).toEqual(["CA_1", "CA_3", "TX_2"]);
    for (const bucket of byStore.values()) {
      expect(bucket.dense).toBe(4);
      expect(bucket.intermittent).toBe(4);
    }
  });

  it("carries both scored origins with full window shapes", () => {
    expect(payload.origins.map((o) => o.origin)).toEqual(["2016-05-10", "2016-05-17"]);
    expect(payload.history_days).toBe(56);
    for (const entry of payload.catalog) {
      for (const origin of payload.origins) {
        const win = entry.origins[origin.origin];
        expect(win, `${entry.series_id} @ ${origin.origin}`).toBeDefined();
        expect(win.history).toHaveLength(56);
        expect(win.actual).toHaveLength(28);
        expect(origin.forecast_dates).toHaveLength(28);
        for (const curve of Object.values(win.curves)) {
          expect(curve).toHaveLength(28);
        }
        expect(win.band.p10).toHaveLength(28);
        expect(win.band.p90).toHaveLength(28);
        expect(win.shape).toMatch(/steady|weekly-peaked|event-driven|slow-mover/);
        // zero-clipped, sorted band
        for (let i = 0; i < 28; i++) {
          expect(win.band.p10[i]).toBeGreaterThanOrEqual(0);
          expect(win.band.p10[i]).toBeLessThanOrEqual(win.band.p90[i]);
        }
      }
    }
  });

  it("ships the committed headline block with the quoted numbers", () => {
    const { headline, test_pooled, win_rate_vs_naive, band } = payload.groups;
    expect(test_pooled.seasonal_naive.wape).toBeCloseTo(0.6032, 3);
    expect(test_pooled.convex_ensemble.wape).toBeCloseTo(0.4983, 3);
    expect(headline.convex_ensemble_vs_naive.wape.diff).toBeCloseTo(-0.1049, 3);
    expect(headline.convex_ensemble_vs_naive.wape.ci95[0]).toBeCloseTo(-0.1154, 3);
    expect(headline.convex_ensemble_vs_naive.wape.ci95[1]).toBeCloseTo(-0.0946, 3);
    expect(test_pooled.convex_ensemble.wrmsse).toBeCloseTo(0.6043, 3);
    expect(test_pooled.seasonal_naive.wrmsse).toBeCloseTo(0.7617, 3);
    expect(win_rate_vs_naive.convex_ensemble.pooled).toBeCloseTo(0.8933, 3);
    expect(band.candidates.lgbm.coverage_80).toBeCloseTo(0.7869, 3);
    expect(band.candidates.lgbm.mean_band_width).toBeCloseTo(12.455, 2);
    expect(band.level).toBe(0.8);
    expect(band.per_horizon_width).toHaveLength(28);
  });

  it("per-series WAPEs are consistent with the shipped curves", () => {
    for (const entry of payload.catalog.slice(0, 4)) {
      for (const win of Object.values(entry.origins)) {
        const vol = win.actual.reduce((s, v) => s + v, 0);
        for (const [cand, wape] of Object.entries(win.wape)) {
          const curve = win.curves[cand];
          expect(curve, cand).toBeDefined();
          const err = win.actual.reduce((s, a, i) => s + Math.abs(curve[i] - a), 0);
          expect(wape).toBeCloseTo(err / vol, 3);
        }
      }
    }
  });
});
