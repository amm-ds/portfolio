import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { ForecastPayload, ModelKey, OriginLabel } from "../types";
import { ORIGIN_LABELS, dayErrors, horizonStats, originBlock, windowMetrics } from "./kpis";

/**
 * Contract test against the REAL committed payload
 * (`projects/02-demand-forecasting/reports/demo_payload.json`, built by
 * `demand_forecasting.demo_payload`, schema v2). Parses it with the same
 * types the workbench fetches and walks every series × origin × model
 * through the kpi helpers, so a payload drift (renamed key, short array,
 * unhandled null) fails here instead of blanking the demo.
 */
const raw = JSON.parse(
  readFileSync("../../projects/02-demand-forecasting/reports/demo_payload.json", "utf8"),
) as ForecastPayload;

const MODELS: ModelKey[] = ["naive", "champion", "challenger"];
const H = 14;

describe("committed demo payload contract (schema v2)", () => {
  it("carries the workbench identity and schema", () => {
    expect(raw.schema_version).toBe(2);
    expect(raw.demo).toBe("forecast-workbench");
    expect(raw.project).toBe("02-demand-forecasting");
    expect(raw.track).toBe("uci");
    expect(Array.isArray(raw.catalog)).toBe(true);
  });

  it("catalog size and class counts match the committed summary", () => {
    const summary = raw.scalars.catalog_summary;
    expect(raw.catalog).toHaveLength(summary.n_series);
    for (const cls of ["smooth", "intermittent", "sparse"] as const) {
      expect(raw.catalog.filter((s) => s.demand_class === cls)).toHaveLength(
        summary.by_class[cls],
      );
    }
    expect(summary.history_days).toBe(180);
    expect(summary.horizon_days).toBe(H);
  });

  it("every series has aligned v1 history, forecast, and error arrays", () => {
    for (const s of raw.catalog) {
      expect(s.series_id).toContain("|");
      expect(s.label).toContain("·");
      expect(s.history.dates).toHaveLength(s.history.y.length);
      expect(s.history.y).toHaveLength(raw.scalars.catalog_summary.history_days);
      const fc = s.forecast;
      expect(fc.dates).toHaveLength(H);
      expect(fc.y_pred).toHaveLength(H);
      expect(fc.p10).toHaveLength(H);
      expect(fc.p90).toHaveLength(H);
      expect(fc.naive).toHaveLength(H);
      for (let h = 1; h <= H; h++) {
        // quantile HGBs don't clip at zero: near-zero sparse days can invert
        // the band by a rounding-width — tolerate a hairline inversion only
        expect(fc.p90[h - 1]).toBeGreaterThanOrEqual(fc.p10[h - 1] - 0.01);
      }
      // mase nulls exactly where the seasonal scale is zero
      const nulls = s.errors.champion.mase.filter((v) => v === null).length;
      expect(nulls === H).toBe(s.errors.scale === 0);
    }
  });

  it("every series carries the three origins with history, actuals, and model curves", () => {
    for (const s of raw.catalog) {
      for (const label of ORIGIN_LABELS) {
        const o = s.origins[label as OriginLabel];
        expect(o, `${s.series_id}:${label}`).toBeDefined();
        expect(o.history.dates).toHaveLength(o.history.y.length);
        expect(o.history.y.length).toBeLessThanOrEqual(60);
        expect(o.actuals.dates).toHaveLength(H);
        expect(o.actuals.y).toHaveLength(H);
        // the as-of-origin history stops at the origin date — no leakage
        expect(o.history.dates[o.history.dates.length - 1]).toBe(o.origin_date);
        for (const m of MODELS) {
          const blk = o.models[m];
          expect(blk.y_pred, `${s.series_id}:${label}:${m}`).toHaveLength(H);
          expect(Number.isFinite(blk.mae)).toBe(true);
          expect(Number.isFinite(blk.bias)).toBe(true);
          expect(blk.mase === null || Number.isFinite(blk.mase)).toBe(true);
          expect(blk.wape === null || Number.isFinite(blk.wape)).toBe(true);
          if (m === "champion") {
            expect(blk.p10).toHaveLength(H);
            expect(blk.p90).toHaveLength(H);
          } else {
            // the band is committed for the champion only
            expect(blk.p10).toBeUndefined();
            expect(blk.p90).toBeUndefined();
          }
        }
        // mase is null exactly where the origin history's scale is zero
        expect((o.models.champion.mase === null) === (o.scale === 0)).toBe(true);
      }
      // the test origin's window is the v1 forecast block
      expect(s.origins.test.actuals.dates).toEqual(s.forecast.dates);
    }
  });

  it("origins_meta records the origin dates, the holdout, and the selection echo", () => {
    const meta = raw.origins_meta;
    expect(meta.origins.map((o) => o.label)).toEqual(["early", "middle", "test"]);
    expect(meta.origins.map((o) => o.origin_date)).toEqual([
      "2010-03-04",
      "2010-05-13",
      "2010-09-30",
    ]);
    expect(meta.origins[2].holdout).toBe("test");
    expect(meta.selection_used_origins).toEqual([1, 2, 3]);
    expect(meta.horizon_days).toBe(H);
    // per-series origin dates agree with the meta block
    for (const s of raw.catalog.slice(0, 5)) {
      for (const m of meta.origins) {
        expect(s.origins[m.label].origin_date).toBe(m.origin_date);
      }
    }
  });

  it("evaluation_metadata embeds the protocol block and metric definitions", () => {
    const em = raw.evaluation_metadata;
    expect(em.protocol).toBe("rolling_origin_holdout_v1");
    expect(em.rolling_origin.n_origins).toBeGreaterThanOrEqual(4);
    expect(em.rolling_origin.horizon_days).toBe(H);
    expect(em.test_origin).toBeGreaterThan(0);
    expect(em.target_definition.length).toBeGreaterThan(20);
    for (const key of ["mae", "mase", "bias", "wape"] as const) {
      expect(em.metric_definitions[key]?.length).toBeGreaterThan(0);
    }
  });

  it("dataset_metadata embeds the source, cleaning rules, and the zero-sales caveat", () => {
    const dm = raw.dataset_metadata;
    expect(dm.source.url).toContain("http");
    expect(dm.zero_sales_caveat.length).toBeGreaterThan(20);
    expect(dm.observed_panel.date_end >= dm.observed_panel.date_start).toBe(true);
  });

  it("scalars carry the honest headline: no run clears MASE 1, ~15.7% MAE edge", () => {
    const { headline, models, band } = raw.scalars;
    expect(headline.champion).toBe(models.champion);
    expect(headline.champion).toBe(raw.evaluation_metadata.best_model);
    expect(headline.challenger).toBe(models.challenger);
    // the honest headline — zero runs below MASE 1 on the frozen test window
    expect(headline.runs_below_mase_1).toEqual([]);
    expect(headline.only_champion_below_mase_1).toBe(false);
    expect(headline.champion_mase).toBeGreaterThan(1);
    expect(headline.champion_mae_edge_vs_strongest_naive_pct).toBeCloseTo(15.7, 0);
    expect(headline.champion_mae).toBeLessThan(headline.strongest_naive_mae);
    for (const v of Object.values(headline.mase_by_model)) {
      expect(Number.isFinite(v)).toBe(true);
    }
    // probabilistic report: pooled coverage beats the target; the UCI
    // conformal width curve is degenerate (all-zero)
    expect(band).not.toBeNull();
    expect(band!.quantile_coverage_pooled).toBeGreaterThan(band!.target_coverage);
    expect(band!.horizon_coverage).toHaveLength(H);
    expect(band!.horizon_avg_width).toHaveLength(H);
    expect(band!.horizon_avg_width.every((w) => w <= 0)).toBe(true);
  });

  it("kpi helpers walk every series × origin × model without throwing", () => {
    let scored = 0;
    let zeroScale = 0;
    for (const s of raw.catalog) {
      for (const label of ORIGIN_LABELS) {
        const blk = originBlock(s, label);
        expect(blk).not.toBeNull();
        for (const m of MODELS) {
          windowMetrics(blk, m);
          const errs = dayErrors(blk, m);
          expect(errs).toHaveLength(H);
          for (let h = 1; h <= H; h++) {
            const st = horizonStats(blk, m, h);
            expect(st).not.toBeNull();
            expect(Number.isFinite(st!.mae)).toBe(true);
            expect(st!.mase === null || Number.isFinite(st!.mase)).toBe(true);
            expect(Number.isFinite(st!.bias)).toBe(true);
          }
          if (blk!.models[m].mase === null) zeroScale++;
          else scored++;
        }
      }
    }
    // the committed catalog really contains zero-scale sparse windows
    expect(zeroScale).toBeGreaterThan(0);
    expect(scored).toBeGreaterThan(zeroScale);
  });
});
