import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { CatalogSeries, ForecastPayload } from "../types";
import {
  classPooledMase,
  coverageNote,
  historyPeak,
  maeAt,
  maseAt,
  representativeByClass,
  windowMase,
} from "./kpis";

/**
 * Contract test against the REAL committed payload
 * (`projects/02-demand-forecasting/reports/demo_payload.json`, built by
 * `demand_forecasting.demo_payload`). Parses it with the same types the
 * workbench fetches and walks every series through the kpi helpers, so a
 * payload drift (renamed key, short array, unhandled null) fails here
 * instead of blanking the demo.
 */
const raw = JSON.parse(
  readFileSync("../../projects/02-demand-forecasting/reports/demo_payload.json", "utf8"),
) as ForecastPayload;

describe("committed demo payload contract", () => {
  it("carries the workbench identity and schema", () => {
    expect(raw.schema_version).toBe(1);
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
    expect(summary.horizon_days).toBe(14);
  });

  it("every series has aligned history, forecast, and error arrays", () => {
    for (const s of raw.catalog) {
      expect(s.series_id).toContain("|");
      expect(s.label).toContain("·");
      expect(s.history.dates).toHaveLength(s.history.y.length);
      expect(s.history.y).toHaveLength(raw.scalars.catalog_summary.history_days);
      const fc = s.forecast;
      expect(fc.dates).toHaveLength(14);
      expect(fc.y_pred).toHaveLength(14);
      expect(fc.p10).toHaveLength(14);
      expect(fc.p90).toHaveLength(14);
      expect(fc.naive).toHaveLength(14);
      for (let h = 1; h <= 14; h++) {
        expect(maeAt(s.errors, h)).not.toBeNull();
        const p10 = fc.p10[h - 1];
        const p90 = fc.p90[h - 1];
        // quantile HGBs don't clip at zero: near-zero sparse days can invert
        // the band by a rounding-width — tolerate a hairline inversion only
        expect(p90).toBeGreaterThanOrEqual(p10 - 0.01);
      }
      // mase nulls exactly where the seasonal scale is zero
      const nulls = s.errors.champion.mase.filter((v) => v === null).length;
      expect(nulls === 14).toBe(s.errors.scale === 0);
    }
  });

  it("kpi helpers walk every series without throwing and handle sparse nulls", () => {
    let sparseNull = 0;
    for (const s of raw.catalog) {
      for (let h = 1; h <= 14; h++) {
        maseAt(s.errors, h);
        maseAt(s.errors, h, "naive");
      }
      windowMase(s.errors);
      windowMase(s.errors, "naive");
      historyPeak(s);
      if (s.demand_class === "sparse" && windowMase(s.errors) === null) sparseNull++;
    }
    // the committed catalog really contains zero-scale sparse series
    expect(sparseNull).toBeGreaterThan(0);
  });

  it("scalars carry the committed headline, band, models, and features", () => {
    const { headline, band, models, feature_schema: fs } = raw.scalars;
    expect(headline.champion).toBe(models.champion);
    expect(headline.champion_mase).toBeCloseTo(headline.mase_by_model[headline.champion], 10);
    expect(headline.champion_mase).toBeLessThan(1);
    expect(headline.naive_mase).toBeGreaterThan(1);
    expect(headline.only_champion_below_mase_1).toBe(true);
    expect(band).not.toBeNull();
    expect(band!.quantile_coverage_pooled).toBeGreaterThan(band!.target_coverage);
    expect(models.naive).toBe("seasonal_naive");
    expect(fs.lags).toEqual(["lag_1", "lag_7", "lag_14"]);
    expect(fs.calendar).toContain("dow");
    expect(fs.calendar).toContain("doy_sin");
  });

  it("per-class pools and representatives are finite (or honestly null)", () => {
    for (const cls of ["smooth", "intermittent", "sparse"] as const) {
      const pooled = classPooledMase(raw.catalog, cls);
      if (cls === "sparse") {
        expect(pooled === null || Number.isFinite(pooled)).toBe(true);
      } else {
        expect(pooled).not.toBeNull();
        expect(Number.isFinite(pooled!)).toBe(true);
      }
    }
    const reps = representativeByClass(raw.catalog);
    for (const cls of ["smooth", "intermittent", "sparse"] as const) {
      expect(reps[cls]?.demand_class).toBe(cls);
    }
    // coverage KPI renders from the committed band
    expect(coverageNote(raw).value).toMatch(/%$/);
  });

  it("the forecast window dates trail the history tail (overlap invariant)", () => {
    const s: CatalogSeries = raw.catalog[0];
    const histTail = s.history.dates.slice(-14);
    expect(s.forecast.dates).toEqual(histTail);
  });
});
