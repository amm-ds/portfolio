import { describe, expect, it } from "vitest";
import type { OriginBlock, OriginLabel } from "../types";
import {
  coverageNote,
  dayErrors,
  deriveFeatures,
  fmtDay,
  horizonStats,
  isoWeek,
  originPctThroughHistory,
  pctEdge,
  spikeDelta,
  windowMetrics,
} from "./kpis";

const N = 20; // origin history days (≥ max lag 14 + live horizons)

/** "2010-12-11" minus (N-1-i) days — 20 days ending on a Saturday. */
const DATES = Array.from({ length: N }, (_, i) => {
  const d = new Date(2010, 11, 11);
  d.setDate(d.getDate() - (N - 1 - i));
  const iso = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${iso(d.getMonth() + 1)}-${iso(d.getDate())}`;
});

/** 14 window days starting the day after the origin date. */
const WIN_DATES = Array.from({ length: 14 }, (_, i) => {
  const d = new Date(2010, 11, 12);
  d.setDate(d.getDate() + i);
  const iso = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${iso(d.getMonth() + 1)}-${iso(d.getDate())}`;
});

const f14 = (fn: (i: number) => number) => Array.from({ length: 14 }, (_, i) => fn(i));

function makeOrigin(over: Partial<OriginBlock> = {}): OriginBlock {
  return {
    origin_date: "2010-12-11",
    history: { dates: DATES, y: Array.from({ length: N }, (_, i) => i + 1) },
    actuals: { dates: WIN_DATES, y: Array.from({ length: 14 }, () => 30) },
    scale: 2,
    models: {
      champion: {
        y_pred: f14((i) => 50 + i),
        p10: f14((i) => 40 + i),
        p90: f14((i) => 60 + i),
        mae: 5,
        mase: 0.8,
        bias: 1,
        wape: 0.2,
      },
      challenger: {
        y_pred: f14((i) => 52 + i),
        mae: 6,
        mase: 0.9,
        bias: -1,
        wape: 0.25,
      },
      naive: {
        y_pred: f14((i) => 55 + i),
        mae: 7,
        mase: 1.2,
        bias: 2,
        wape: 0.3,
      },
    },
    ...over,
  };
}

describe("windowMetrics", () => {
  it("returns the committed 14-day window metrics per model", () => {
    const o = makeOrigin();
    expect(windowMetrics(o, "champion")).toEqual({ mae: 5, mase: 0.8, bias: 1, wape: 0.2 });
    expect(windowMetrics(o, "naive")).toEqual({ mae: 7, mase: 1.2, bias: 2, wape: 0.3 });
  });

  it("is null on a missing block or model", () => {
    expect(windowMetrics(null, "champion")).toBeNull();
    const o = makeOrigin({ models: { ...makeOrigin().models, naive: undefined as never } });
    expect(windowMetrics(o, "naive")).toBeNull();
  });
});

describe("horizonStats", () => {
  const o = makeOrigin(); // champion y_pred[i] = 50+i, actuals all 30

  it("derives day-h metrics from the committed curve vs actuals", () => {
    const s1 = horizonStats(o, "champion", 1);
    expect(s1).not.toBeNull();
    expect(s1!.mae).toBe(20); // |50 − 30|
    expect(s1!.mase).toBe(10); // 20 / scale 2
    expect(s1!.bias).toBe(20);
    expect(s1!.wape).toBeCloseTo(20 / 30, 6);
    expect(s1!.signed).toBe(20);
  });

  it("accumulates bias and WAPE over 1..h", () => {
    const s14 = horizonStats(o, "champion", 14);
    // Σ(50+i−30) = 20·14 + 91 = 371; bias = 371/14; wape = 371 / (14·30)
    expect(s14!.bias).toBeCloseTo(371 / 14, 6);
    expect(s14!.wape).toBeCloseTo(371 / 420, 6);
    // day-14 |err| = |63 − 30| = 33; mase is a day-h value, not cumulative
    expect(s14!.mase).toBeCloseTo(33 / 2, 6);
  });

  it("mase is null on a zero-scale origin, null out of range or misaligned", () => {
    const sparse = makeOrigin({ scale: 0 });
    expect(horizonStats(sparse, "champion", 7)!.mase).toBeNull();
    expect(horizonStats(o, "champion", 0)).toBeNull();
    expect(horizonStats(o, "champion", 15)).toBeNull();
    expect(horizonStats(makeOrigin({ actuals: { dates: WIN_DATES, y: [1, 2] } }), "champion", 7)).toBeNull();
    expect(horizonStats(null, "champion", 7)).toBeNull();
  });
});

describe("dayErrors", () => {
  it("splits the window into signed per-day errors", () => {
    const errs = dayErrors(makeOrigin(), "champion");
    expect(errs).toHaveLength(14);
    expect(errs[0]).toEqual({ h: 1, signed: 20, abs: 20, over: true });
    // a curve under the actuals flips the sign and the color scheme
    const under = makeOrigin({
      models: {
        ...makeOrigin().models,
        challenger: { y_pred: f14(() => 10), mae: 20, mase: 1, bias: -20, wape: 0.6 },
      },
    });
    expect(dayErrors(under, "challenger")[3].over).toBe(false);
    expect(dayErrors(null, "naive")).toEqual([]);
  });
});

describe("pctEdge", () => {
  it("percent by which the winner beats the floor", () => {
    expect(pctEdge(8.5, 10)).toBeCloseTo(15, 6);
    expect(pctEdge(12, 10)).toBeCloseTo(-20, 6);
  });

  it("null when the floor is zero or a side is missing", () => {
    expect(pctEdge(1, 0)).toBeNull();
    expect(pctEdge(null, 10)).toBeNull();
    expect(pctEdge(1, null)).toBeNull();
  });
});

describe("coverageNote", () => {
  const band = {
    target_coverage: 0.8,
    quantile_coverage_pooled: 0.91933,
    split_conformal_coverage_last_fold: 0.85843,
    calibration_verdict: "conservative",
    horizon_coverage: Array.from({ length: 14 }, () => 0.85),
    horizon_avg_width: Array.from({ length: 14 }, (_, i) => i),
    note: "x",
  };

  it("formats the committed pooled coverage with the target", () => {
    const note = coverageNote({ scalars: { band } } as never);
    expect(note.value).toBe("91.9%");
    expect(note.sub).toContain("target 80%");
    expect(note.degenerate).toBe(false);
  });

  it("flags the degenerate all-zero width curve", () => {
    const degenerate = { ...band, horizon_avg_width: Array.from({ length: 14 }, () => 0) };
    const note = coverageNote({ scalars: { band: degenerate } } as never);
    expect(note.degenerate).toBe(true);
    expect(note.sub).toContain("degenerate width");
  });

  it("degrades to n/a without a probabilistic report", () => {
    const note = coverageNote({ scalars: { band: null } } as never);
    expect(note.value).toBe("n/a");
    expect(note.degenerate).toBe(false);
  });
});

describe("originPctThroughHistory", () => {
  const payload = (originDate: string) =>
    ({
      origins_meta: {
        origins: [{ label: "test" as OriginLabel, origin_date: originDate }],
      },
      dataset_metadata: {
        observed_panel: { date_start: "2009-12-09", date_end: "2010-12-09" },
      },
    }) as never;

  it("positions the origin date inside the observed panel", () => {
    expect(originPctThroughHistory(payload("2009-12-09"), "test")).toBe(0);
    expect(originPctThroughHistory(payload("2010-06-09"), "test")).toBe(50);
    expect(originPctThroughHistory(payload("2010-12-09"), "test")).toBe(100);
  });

  it("null without a date range or meta", () => {
    expect(originPctThroughHistory({} as never, "test")).toBeNull();
  });
});

describe("spikeDelta", () => {
  it("returns the signed delta and percent lift", () => {
    expect(spikeDelta(150, 100)).toEqual({ delta: 50, pct: 50 });
    expect(spikeDelta(80, 100)).toEqual({ delta: -20, pct: -20 });
  });

  it("never divides by a zero committed forecast", () => {
    expect(spikeDelta(10, 0)).toEqual({ delta: 10, pct: 0 });
  });
});

describe("calendar derivation", () => {
  it("fmtDay renders MMM d without TZ shift", () => {
    expect(fmtDay("2010-12-09")).toBe("Dec 9");
    expect(fmtDay("2010-01-01")).toBe("Jan 1");
  });

  it("isoWeek matches the polars week of the serving example", () => {
    // 2010-07-02 is ISO week 26; the serving meta example (week 27) sits
    // mid-year where ISO and simple divisions agree — pin both ends
    expect(isoWeek(new Date(2010, 0, 1))).toBe(53);
    expect(isoWeek(new Date(2010, 6, 2))).toBe(26);
  });
});

describe("deriveFeatures", () => {
  const o = makeOrigin(); // origin history ends Saturday 2010-12-11, y[i] = i+1

  it("builds calendar features for origin date + h (polars weekday)", () => {
    const f = deriveFeatures(o, 1, 1.5); // 2010-12-12, a Sunday
    expect(f.dow).toBe(7);
    expect(f.is_weekend).toBe(1);
    expect(f.month).toBe(12);
    expect(f.t).toBe(N - 1 + 1);
    expect(f.doy_sin).toBeCloseTo(Math.sin((346 * Math.PI * 2) / 365.25), 6);
    expect(f.week).toBe(isoWeek(new Date(2010, 11, 12)));
    const f2 = deriveFeatures(o, 2, 1.5); // Monday
    expect(f2.dow).toBe(1);
    expect(f2.is_weekend).toBe(0);
  });

  it("scales the lags inside the hot week and leaves older lags committed", () => {
    const f = deriveFeatures(o, 1, 1.5);
    expect(f.lag_1).toBe(20 * 1.5); // offset 0 — hot
    expect(f.lag_7).toBe(14 * 1.5); // offset −6 — hot
    expect(f.lag_14).toBe(7); // offset −13 — committed
  });

  it("falls back to the committed forecast when a lag day lands in the window", () => {
    const f = deriveFeatures(o, 3, 1.5);
    // lag_1 day = D+2 = window day 2 → committed champion y_pred[1] = 51 (offset +2 — hot)
    expect(f.lag_1).toBe(51 * 1.5);
    expect(f.lag_7).toBe(16 * 1.5); // history y[15]=16, offset −4 — hot
    expect(f.lag_14).toBe(9); // history y[8]=9, offset −11 — committed
  });

  it("spike 1 leaves every lag committed", () => {
    const f = deriveFeatures(o, 1, 1);
    expect(f.lag_1).toBe(20);
    expect(f.lag_7).toBe(14);
    expect(f.lag_14).toBe(7);
  });
});
