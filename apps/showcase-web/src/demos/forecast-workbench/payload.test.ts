import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { DemandClass, ForecastPayload, ModelKey } from "../types";
import {
  bandAt,
  curveAt,
  growthAt,
  horizonKpi,
  latticeErrors,
  modelBlock,
  orderPolicy,
  originBlock,
  originDates,
  scoreboardRow,
} from "./kpis";

/**
 * Contract test against the REAL committed v3 payload
 * (`projects/02-demand-forecasting/reports/demo_payload.json`, built by
 * `demand_forecasting.demo_payload`, schema v3 — the direct multi-horizon
 * catalog). Walks every series × origin × model through the kpi helpers and
 * cross-checks the experiment-wide blocks against the committed metrics, so
 * a payload drift (renamed key, short array, unhandled null) fails here
 * instead of blanking the demo.
 */
const raw = JSON.parse(
  readFileSync("../../projects/02-demand-forecasting/reports/demo_payload.json", "utf8"),
) as ForecastPayload;
const committed = JSON.parse(
  readFileSync("../../projects/02-demand-forecasting/reports_uci/metrics.json", "utf8"),
)["_multistep"];
const probCommitted = JSON.parse(
  readFileSync("../../projects/02-demand-forecasting/reports_uci/probabilistic.json", "utf8"),
)["multistep"];

const LATTICE = [1, 2, 3, 5, 7, 10, 14];
const SHOCK_KEYS = ["0.5", "1.5", "2"];
const isoDate = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

describe("committed demo payload contract (schema v3)", () => {
  it("carries the workbench identity and the multi-horizon protocol", () => {
    expect(raw.schema_version).toBe(3);
    expect(raw.demo).toBe("forecast-workbench");
    expect(raw.project).toBe("02-demand-forecasting");
    expect(raw.track).toBe("uci");
    expect(raw.protocol).toBe("direct_multihorizon_v1");
    expect(raw.evaluation_metadata.protocol).toBe("direct_multihorizon_v1");
  });

  it("catalog keeps ~100 series with ALL erratic series represented", () => {
    expect(raw.catalog).toHaveLength(100);
    expect(raw.catalog_summary.by_class).toEqual({ erratic: 15, lumpy: 85 });
    const erratic = raw.catalog.filter((s) => s.demand_class === "erratic");
    expect(erratic).toHaveLength(15);
    // every erratic series is served by the boosted HGB (and vice versa)
    for (const s of raw.catalog) {
      expect(s.model_used === "direct_hgb").toBe(s.demand_class === "erratic");
    }
    // country diversity (the v2 audit found 64/100 UK)
    expect(raw.catalog_summary.countries["United Kingdom"]).toBeLessThanOrEqual(30);
    expect(Object.keys(raw.catalog_summary.countries).length).toBeGreaterThanOrEqual(4);
  });

  it("the 3 scored origins are the 3 most recent committed test origins", () => {
    const expected = committed.origins.test_dates.slice(-3);
    expect(originDates(raw)).toEqual(expected);
    for (const s of raw.catalog) {
      expect(s.origins.map((o) => o.origin_date)).toEqual(expected);
    }
  });

  it("origin contiguity via the payload: history ends at origin−1, actuals start at origin+1 — no gap", () => {
    for (const s of raw.catalog) {
      for (const o of s.origins) {
        expect(o.history.dates[o.history.dates.length - 1]).toBe(isoPrev(o.origin_date));
        expect(o.actuals.dates[0]).toBe(isoNext(o.origin_date));
        expect(o.actuals.dates[o.actuals.dates.length - 1]).toBe(isoNext(o.origin_date, 14));
        // daily-contiguous on both sides
        let prev = o.history.dates[0];
        for (const d of o.history.dates.slice(1)) {
          expect(isoNext(prev)).toBe(d);
          prev = d;
        }
        prev = o.actuals.dates[0];
        for (const d of o.actuals.dates.slice(1)) {
          expect(isoNext(prev)).toBe(d);
          prev = d;
        }
      }
    }
  });

  it("every series carries lattice curves, bands, and shock blocks", () => {
    for (const s of raw.catalog) {
      for (const o of s.origins) {
        expect(o.horizons).toEqual(LATTICE);
        for (const mk of ["zero", "routed", "floor"] as ModelKey[]) {
          const blk = modelBlock(o, mk)!;
          expect(blk.y_pred).toHaveLength(LATTICE.length);
          expect(Object.keys(blk.shock).sort()).toEqual([...SHOCK_KEYS].sort());
          for (const curve of Object.values(blk.shock)) {
            expect(curve).toHaveLength(LATTICE.length);
            expect(curve.every((v) => v >= 0 && Number.isFinite(v))).toBe(true);
          }
        }
        if (s.demand_class === "erratic") {
          const champ = modelBlock(o, "champion")!;
          expect(champ.y_pred).toEqual(o.models.routed.y_pred);
          expect(champ.p10).toHaveLength(LATTICE.length);
          for (let i = 0; i < LATTICE.length; i++) {
            expect(o.models.routed.p10![i]).toBeGreaterThanOrEqual(0);
            expect(o.models.routed.p10![i]).toBeLessThanOrEqual(o.models.routed.y_pred[i]);
            expect(o.models.routed.p90![i]).toBeGreaterThanOrEqual(o.models.routed.y_pred[i]);
          }
        } else {
          expect(o.models.champion_hgb).toBeUndefined();
          expect(o.models.routed.p10).toBeUndefined();
          // the honest sparse band: P(sale) + non-decreasing ladder
          const band = o.models.routed.band!;
          expect(band.p_sale).toBeGreaterThanOrEqual(0);
          expect(band.p_sale).toBeLessThanOrEqual(1);
          const ladder = Object.values(band.ladder);
          expect([...ladder].sort((a, b) => a - b)).toEqual(ladder);
        }
        // zero stays zero under every shock; the floor reads only shocked days
        for (const curve of Object.values(o.models.zero.shock)) {
          expect(curve.every((v) => v === 0)).toBe(true);
        }
        for (const [key, curve] of Object.entries(o.models.floor.shock)) {
          const factor = Number(key);
          expect(curve).toEqual(o.models.floor.y_pred.map((v) => round4(v * factor)));
        }
      }
    }
  });

  it("kpi helpers walk every series × origin × model without throwing", () => {
    let scored = 0;
    for (const s of raw.catalog) {
      for (const date of originDates(raw)) {
        const blk = originBlock(s, date);
        expect(blk).not.toBeNull();
        for (const mk of ["zero", "routed", "champion"] as ModelKey[]) {
          if (mk === "champion" && s.demand_class !== "erratic") continue;
          for (const h of LATTICE) {
            const k = horizonKpi(blk, mk, 1, h);
            expect(k).not.toBeNull();
            expect(Number.isFinite(k!.mae)).toBe(true);
            expect(k!.mase === null || Number.isFinite(k!.mase)).toBe(true);
          }
          for (const shock of [0.5, 1.5, 2]) {
            const errs = latticeErrors(blk, mk, shock);
            expect(errs).toHaveLength(LATTICE.length);
          }
          scored++;
        }
      }
    }
    expect(scored).toBeGreaterThan(0);
  });

  it("class scoreboard equals the committed metrics", () => {
    for (const cls of ["lumpy", "erratic"] as DemandClass[]) {
      const board = raw.class_scoreboard[cls];
      const committedCls = committed.headline_per_class[cls];
      expect(board.n_series).toBe(committedCls.n_series);
      for (const h of [7, 14]) {
        const row = scoreboardRow(raw.class_scoreboard, cls, h);
        expect(row.modelMae).toBeCloseTo(committedCls[`h${h}`].champion_mae, 9);
        expect(row.floorMae).toBeCloseTo(committedCls[`h${h}`].floor_mae, 9);
        expect(row.gap).not.toBeNull();
        expect(board.gap_bootstrap[`h${h}`]).toEqual(committedCls[`h${h}`].champion_vs_floor);
        expect(board.vs_zero_bootstrap[`h${h}`]).toEqual(
          committedCls[`h${h}`].champion_vs_naive_zero,
        );
        // per-series honesty: counts within range and consistent shares
        expect(row.beatsCount!).toBeGreaterThanOrEqual(0);
        expect(row.beatsCount!).toBeLessThanOrEqual(row.nSeries);
        // the stored share is rounded to 4 decimals
        expect(row.beatsShare!).toBeCloseTo(row.beatsCount! / row.nSeries, 3);
      }
      expect(board.routing_effect).toEqual(committed.routing.per_class[cls]);
    }
    // the headline routing win the hero quotes
    expect(committed.routing.per_class.lumpy.diff).toBeCloseTo(4.6, 0);
    expect(raw.headline.claim).toContain("+4.6 MAE [4.2, 5.1]");
  });

  it("horizon growth and bands equal the committed blocks", () => {
    expect(raw.horizon_growth.pooled).toEqual(committed.horizon_growth.pooled);
    for (const h of LATTICE) {
      expect(growthAt(raw.horizon_growth, "routed", h)).toBeCloseTo(
        committed.horizon_growth.pooled.routed[String(h)],
        9,
      );
      const committedMase = committed.per_horizon[String(h)].champion.mase;
      if (Number.isFinite(committedMase)) {
        expect(raw.horizon_growth.mase.champion[String(h)]).toBeCloseTo(committedMase, 9);
      }
    }
    expect(raw.bands.per_horizon).toEqual(probCommitted.per_horizon);
    expect(raw.bands.conformal_widths_by_h).toEqual(probCommitted.conformal_widths_by_h);
    expect(bandAt(raw.bands, 7)!.coverage).toBeCloseTo(
      probCommitted.per_horizon["7"].coverage,
      9,
    );
  });

  it("decision block carries the committed simulation plus a monotone τ mapping", () => {
    expect(raw.decision.per_class).toEqual(committed.decision_metric.per_class);
    expect(raw.decision.simulation).toBe(true);
    expect(raw.decision.tau_grid[0]).toBe("0.50");
    expect(raw.decision.tau_grid[raw.decision.tau_grid.length - 1]).toBe("0.99");
    for (const cls of ["lumpy", "erratic"] as DemandClass[]) {
      for (const policy of ["champion", "floor"] as const) {
        for (const h of LATTICE) {
          const taus = raw.decision.quantile_map[cls][policy][String(h)];
          const values = raw.decision.tau_grid.map((t) => taus[t]);
          expect([...values].sort((a, b) => a - b)).toEqual(values);
        }
      }
    }
    // the mapping drives real orders for a catalog series
    const s = raw.catalog[0];
    const blk = s.origins[0];
    const orders = orderPolicy(raw.decision, s.demand_class, "champion", curveAt(blk.models.routed, 1), blk.horizons, 0.9);
    expect(orders).toHaveLength(LATTICE.length);
    expect(orders.every((v) => v >= 0)).toBe(true);
  });

  it("evaluation + dataset metadata embed the protocol block and intermittency classes", () => {
    expect(raw.evaluation_metadata.origins.n_origins).toBe(20);
    expect(raw.evaluation_metadata.origins.gap_days).toBe(0);
    expect(raw.evaluation_metadata.origins.test_dates).toHaveLength(4);
    expect(raw.evaluation_metadata.feature_semantics).toContain("no actual within h days");
    expect(raw.dataset_metadata.intermittency?.class_counts.lumpy).toBe(1069);
    expect(raw.dataset_metadata.intermittency?.class_counts.erratic).toBe(15);
    expect(raw.dataset_metadata.target_definition.length).toBeGreaterThan(20);
  });

  it("stays under the 3 MB cap", () => {
    const bytes = readFileSync("../../projects/02-demand-forecasting/reports/demo_payload.json").byteLength;
    expect(bytes).toBeLessThanOrEqual(3 * 1024 * 1024);
  });
});

function isoNext(iso: string, n = 1): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return isoDate(d);
}

function isoPrev(iso: string): string {
  return isoNext(iso, -1);
}

function round4(v: number): number {
  return Math.round(v * 10000) / 10000;
}
