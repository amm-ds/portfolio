import { describe, expect, it } from "vitest";
import type {
  CatalogSeries,
  DecisionBlock,
  ForecastPayload,
  HorizonGrowth,
  OriginBlock,
  ScoreboardClass,
} from "../types";
import {
  addDays,
  bandAt,
  candidateAvailable,
  curveAt,
  fmtDay,
  growthAt,
  growthMaseAt,
  growthRatio,
  horizonKpi,
  latticeErrors,
  modelBlock,
  mulberry32,
  orderPolicy,
  orderQuantity,
  originBlock,
  originDates,
  parseDay,
  policyWindow,
  routedLabel,
  scoreboardRow,
  surprisePick,
} from "./kpis";

const HORIZONS = [1, 2, 3, 5, 7, 10, 14];

/** One scored origin: history ends the day BEFORE the origin, actuals are the
 * 14 days AFTER it — the protocol-v2 contiguous layout. */
function makeOrigin(over: Partial<OriginBlock> = {}): OriginBlock {
  const originDate = "2010-12-11";
  const histDates = Array.from({ length: 20 }, (_, i) => addDays(originDate, i - 20)); // ..origin-1
  const actualDates = Array.from({ length: 14 }, (_, i) => addDays(originDate, i + 1)); // origin+1..
  const curve = (base: number) => HORIZONS.map((h) => base + h);
  return {
    origin_date: originDate,
    history: { dates: histDates, y: Array.from({ length: 20 }, (_, i) => i + 1) },
    // 14 real window days; the model curve stays at the 7 lattice points
    actuals: { dates: actualDates, y: Array.from({ length: 14 }, (_, i) => 30 + ((i + 1) % 3)) },
    horizons: HORIZONS,
    scale: 2,
    models: {
      zero: { y_pred: HORIZONS.map(() => 0), shock: { "0.5": HORIZONS.map(() => 0), "2": HORIZONS.map(() => 0) } },
      routed: {
        y_pred: curve(40),
        p10: curve(35),
        p90: curve(48),
        shock: { "0.5": curve(30), "2": curve(60) },
      },
      floor: { y_pred: curve(44), shock: { "0.5": curve(22), "2": curve(88) } },
      champion_hgb: {
        y_pred: curve(41),
        p10: curve(36),
        p90: curve(49),
        shock: { "0.5": curve(31), "2": curve(61) },
      },
    },
    ...over,
  };
}

function makeSeries(over: Partial<CatalogSeries> = {}): CatalogSeries {
  return {
    series_id: "United Kingdom|85123A",
    label: "United Kingdom · 85123A",
    country: "United Kingdom",
    product: "85123A",
    demand_class: "erratic",
    adi: 1.1,
    cv2: 1.5,
    model_used: "direct_hgb",
    origins: [makeOrigin()],
    ...over,
  };
}

const GROWTH: HorizonGrowth = {
  horizons: HORIZONS,
  pooled: {
    routed: { "1": 2.4, "2": 4.5, "3": 9.7, "5": 10.1, "7": 7.6, "10": 10.5, "14": 7.4 },
    seasonal_naive: { "1": 0, "14": 11.3 },
    zero: { "1": 2.4, "14": 7.6 },
  },
  mase: {
    champion: { "1": 0.25, "14": 0.8 },
    floor: { "1": null, "14": 1.3 },
  },
  per_class: {},
  note: "x",
};

const SCOREBOARD: Record<"erratic" | "lumpy", ScoreboardClass> = {
  erratic: {
    n_series: 15,
    beats_floor: { h7: { count: 6, n: 15, share: 0.4 }, h14: { count: 7, n: 15, share: 7 / 15 } },
    mae: { h7: { model: 70, floor: 68.35 }, h14: { model: 72.53, floor: 60 } },
    gap_bootstrap: {
      h7: { diff: 1.64, ci95: [-33.5, 27.7], spans_zero: true, n_boot: 2000, seed: 1 },
      h14: { diff: 12.53, ci95: [-5.5, 30.5], spans_zero: true, n_boot: 2000, seed: 1 },
    },
    vs_zero_bootstrap: {
      h7: { diff: 5.84, ci95: [-7.4, 20.7], spans_zero: true, n_boot: 2000, seed: 1 },
    },
    routing_effect: null,
  },
  lumpy: {
    n_series: 1069,
    beats_floor: { h7: { count: 213, n: 1069, share: 213 / 1069 }, h14: { count: 231, n: 1069, share: 231 / 1069 } },
    mae: { h7: { model: 6.72, floor: 11.07 }, h14: { model: 6.45, floor: 10.64 } },
    gap_bootstrap: {
      h7: { diff: -4.35, ci95: [-7.06, -2.26], spans_zero: false, n_boot: 2000, seed: 1 },
    },
    vs_zero_bootstrap: {
      h7: { diff: -0.48, ci95: [-0.88, -0.15], spans_zero: false, n_boot: 2000, seed: 1 },
    },
    routing_effect: { diff: 4.65, ci95: [4.15, 5.14], spans_zero: false, n_boot: 2000, seed: 1 },
  },
};

const DECISION: DecisionBlock = {
  simulation: true,
  label: "order-up-to policy simulation — no savings claims",
  cost_assumptions: { holding_cost_per_unit: 0.25, stockout_cost_per_unit_short: 4, cost_basis: "per cell" },
  service_levels: [0.8, 0.9, 0.95],
  per_class: {},
  tau_grid: ["0.50", "0.90", "0.99"],
  quantile_map: {
    erratic: {
      champion: {
        "7": { "0.50": 0, "0.90": 10, "0.99": 40 },
        "14": { "0.50": 1, "0.90": 12, "0.99": 45 },
      },
      floor: { "7": { "0.50": 0, "0.90": 8, "0.99": 30 } },
    },
    lumpy: { champion: { "7": {} }, floor: { "7": {} } },
  },
  mapping_note: "x",
};

describe("calendar", () => {
  it("parseDay/fmtDay/addDays round-trip without TZ shift", () => {
    expect(fmtDay("2010-12-09")).toBe("Dec 9");
    expect(addDays("2010-12-11", -1)).toBe("2010-12-10");
    expect(addDays("2010-12-11", 1)).toBe("2010-12-12");
    expect(addDays("2010-12-11", 14)).toBe("2010-12-25");
    expect(parseDay("2010-12-11").getDate()).toBe(11);
  });
});

describe("originBlock + modelBlock + curveAt", () => {
  const series = makeSeries({
    origins: [makeOrigin({ origin_date: "2010-11-05" }), makeOrigin()],
  });

  it("finds the origin block by date and the champion only where present", () => {
    expect(originBlock(series, "2010-12-11")?.origin_date).toBe("2010-12-11");
    expect(originBlock(series, "1999-01-01")).toBeNull();
    expect(modelBlock(series.origins[0], "champion")).not.toBeNull();
    const lumpy = makeSeries({ demand_class: "lumpy", model_used: "zero" });
    delete lumpy.origins[0].models.champion_hgb;
    expect(modelBlock(lumpy.origins[0], "champion")).toBeNull();
  });

  it("curveAt returns the base curve at shock 1 and the precomputed shock curves", () => {
    const o = series.origins[0];
    expect(curveAt(o.models.routed, 1)).toBe(o.models.routed.y_pred);
    expect(curveAt(o.models.routed, 0.5)).toBe(o.models.routed.shock["0.5"]);
    expect(curveAt(o.models.routed, 2)).toBe(o.models.routed.shock["2"]);
    expect(curveAt(null, 1)).toEqual([]);
  });

  it("routedLabel names the committed method per series", () => {
    expect(routedLabel(makeSeries())).toBe("routed · boosted HGB");
    expect(routedLabel(makeSeries({ demand_class: "lumpy", model_used: "sba" }))).toBe("routed · sba");
    expect(routedLabel(makeSeries({ model_used: "hurdle_hgb" }))).toBe("routed · hurdle");
    expect(routedLabel(makeSeries({ model_used: "hgb_tweedie" }))).toBe("routed · tweedie");
    expect(routedLabel(makeSeries({ demand_class: "lumpy", model_used: "zero" }))).toBe("routed · zero");
  });

  it("candidate chips resolve through the revision-3.1 alias entries", () => {
    const hurdleSeries = makeSeries({ model_used: "hurdle_hgb" });
    hurdleSeries.origins[0].models.hurdle_hgb = { alias: "routed" };
    expect(candidateAvailable(hurdleSeries, "hurdle")).toBe(true);
    expect(candidateAvailable(hurdleSeries, "tweedie")).toBe(false);
    // the alias block resolves to the routed curve…
    expect(modelBlock(hurdleSeries.origins[0], "hurdle")).toBe(
      hurdleSeries.origins[0].models.routed,
    );
    // …and a candidate the router did not select has no block at all
    expect(modelBlock(hurdleSeries.origins[0], "tweedie")).toBeNull();
  });
});

describe("latticeErrors + horizonKpi", () => {
  const o = makeOrigin(); // routed[i] = 40+h, actual at day h = 30 + h%3

  it("evaluates each direct h-step forecast against the actual of day origin+h", () => {
    const errs = latticeErrors(o, "routed", 1);
    expect(errs).toHaveLength(HORIZONS.length);
    expect(errs[0]).toMatchObject({ h: 1, date: "2010-12-12" }); // day after the origin
    // h=1: pred 41 vs actual 31 → +10 over
    expect(errs[0].signed).toBeCloseTo(10, 6);
    expect(errs[0].over).toBe(true);
    expect(latticeErrors(null, "routed", 1)).toEqual([]);
  });

  it("horizonKpi accumulates over the visible fan h′ ≤ h and nulls safely", () => {
    const k7 = horizonKpi(o, "routed", 1, 7);
    expect(k7).not.toBeNull();
    // fan points h ∈ {1,2,3,5,7}: preds 41,42,43,45,47;
    // actuals of days 1..7: 31,32,30,31,32,30,31 → |err| 10,10,13,13,16
    const wantAbs = [10, 10, 13, 13, 16];
    expect(k7!.mae).toBeCloseTo(wantAbs.reduce((a, b) => a + b, 0) / wantAbs.length, 6);
    expect(k7!.mase).toBeCloseTo(k7!.mae / 2, 6);
    expect(k7!.signed).toBeCloseTo(16, 6);
    const zero = horizonKpi(o, "zero", 1, 14);
    expect(zero!.wape).not.toBeNull();
    expect(horizonKpi(o, "routed", 1, 0)).toBeNull();
    expect(horizonKpi(null, "routed", 1, 7)).toBeNull();
    // zero-scale origin → MASE null
    expect(horizonKpi(makeOrigin({ scale: 0 }), "routed", 1, 7)!.mase).toBeNull();
  });

  it("the shock lever changes the curve and the KPIs", () => {
    const base = horizonKpi(o, "routed", 1, 7)!.mae;
    const shocked = horizonKpi(o, "routed", 2, 7)!.mae;
    expect(shocked).not.toBe(base); // 60+h curve differs from 40+h
  });
});

describe("growthAt / growthMaseAt / growthRatio", () => {
  it("reads pooled MAE by true horizon and nulls off-lattice", () => {
    expect(growthAt(GROWTH, "routed", 14)).toBeCloseTo(7.4, 6);
    expect(growthAt(GROWTH, "zero", 1)).toBeCloseTo(2.4, 6);
    expect(growthAt(GROWTH, "routed", 4)).toBeNull();
  });

  it("reads MASE with nulls", () => {
    expect(growthMaseAt(GROWTH, "champion", 14)).toBeCloseTo(0.8, 6);
    expect(growthMaseAt(GROWTH, "floor", 14)).toBeCloseTo(1.3, 6);
    expect(growthMaseAt(GROWTH, "floor", 1)).toBeNull();
  });

  it("growthRatio derives the horizon-truth multiple", () => {
    expect(growthRatio(GROWTH, 14, 1)).toBeCloseTo(0.8 / 0.25, 6);
    expect(growthRatio(GROWTH, 4, 1)).toBeNull();
  });
});

describe("scoreboardRow", () => {
  it("flattens the committed class row with the bootstrap verdict", () => {
    const lumpy7 = scoreboardRow(SCOREBOARD, "lumpy", 7);
    expect(lumpy7.nSeries).toBe(1069);
    expect(lumpy7.beatsCount).toBe(213);
    expect(lumpy7.beatsShare).toBeCloseTo(213 / 1069, 6);
    expect(lumpy7.modelMae).toBeCloseTo(6.72, 6);
    expect(lumpy7.gap).not.toBeNull();
    expect(lumpy7.gap!.spansZero).toBe(false);
    const erratic7 = scoreboardRow(SCOREBOARD, "erratic", 7);
    expect(erratic7.gap!.spansZero).toBe(true);
  });
});

describe("bandAt", () => {
  it("reads per-h coverage/width/verdict from the committed bands block", () => {
    const bands = {
      target_coverage: 0.8,
      per_horizon: {
        "7": { coverage: 0.9034, avg_width: 8.06, calibration_verdict: "conservative" },
      },
    } as never;
    expect(bandAt(bands, 7)).toEqual({ coverage: 0.9034, avgWidth: 8.06, verdict: "conservative" });
    expect(bandAt(bands, 4)).toBeNull();
    expect(bandAt(null, 7)).toBeNull();
  });
});

describe("decision layer", () => {
  it("orderQuantity clips at zero", () => {
    expect(orderQuantity(3, 2)).toBe(5);
    expect(orderQuantity(1, -4)).toBe(0);
  });

  it("orderPolicy maps the series curve through the committed offsets", () => {
    const curve = [10, 20];
    const orders = orderPolicy(DECISION, "erratic", "champion", curve, [7, 14], 0.9);
    expect(orders).toEqual([10 + 10, 20 + 12]);
    // missing offsets degrade to the point forecast
    const lumpy = orderPolicy(DECISION, "lumpy", "champion", curve, [7, 14], 0.9);
    expect(lumpy).toEqual(curve);
  });

  it("policyWindow sums over/under units and the documented cost", () => {
    const actuals = { y: Array.from({ length: 14 }, (_, i) => (i < 7 ? 5 : 50)) };
    const win = policyWindow([4, 40], [1, 8], actuals, { holding: 0.25, stockout: 4 });
    expect(win.overUnits).toBe(0);
    expect(win.underUnits).toBeCloseTo(1 + 10, 6);
    expect(win.cost).toBeCloseTo(0.25 * 0 + 4 * 11, 6);
  });
});

describe("surprisePick (class-stratified, seeded)", () => {
  const catalog = [
    makeSeries({ series_id: "A|1", demand_class: "lumpy", model_used: "zero" }),
    makeSeries({ series_id: "B|2", demand_class: "lumpy", model_used: "zero" }),
    makeSeries({ series_id: "C|3", demand_class: "lumpy", model_used: "zero" }),
    makeSeries({ series_id: "D|4", demand_class: "erratic" }),
  ];

  it("is deterministic for a fixed seed", () => {
    const a = surprisePick(catalog, mulberry32(42));
    const b = surprisePick(catalog, mulberry32(42));
    expect(a?.series_id).toBe(b?.series_id);
  });

  it("respects class quotas over a long stream (lumpy ≠ 75% — stratified ≈ 50%)", () => {
    const counts = { lumpy: 0, erratic: 0 };
    for (let s = 1; s <= 400; s++) {
      const pick = surprisePick(catalog, mulberry32(s));
      if (pick) counts[pick.demand_class]++;
    }
    // uniform-over-classes gives the 3 lumpy : 1 erratic catalog a 1/2 erratic rate
    expect(counts.erratic).toBeGreaterThan(140);
    expect(counts.erratic).toBeLessThan(260);
  });

  it("null on an empty catalog", () => {
    expect(surprisePick([], mulberry32(1))).toBeNull();
  });
});

describe("payload-typed helper smoke", () => {
  it("originDates reads the scored origin slider stops", () => {
    const payload = {
      catalog_summary: {
        origins: [{ origin_date: "2010-11-05" }, { origin_date: "2010-11-12" }, { origin_date: "2010-11-19" }],
      },
    } as ForecastPayload;
    expect(originDates(payload)).toEqual(["2010-11-05", "2010-11-12", "2010-11-19"]);
  });
});
