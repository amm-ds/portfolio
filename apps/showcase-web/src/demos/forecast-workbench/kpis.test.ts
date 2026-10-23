import { describe, expect, it } from "vitest";
import type { CatalogSeries } from "../types";
import {
  classPooledMase,
  coverageNote,
  deriveFeatures,
  fmtDay,
  historyPeak,
  isoWeek,
  maeAt,
  maseAt,
  representativeByClass,
  spikeDelta,
  windowMase,
} from "./kpis";

const N = 20; // history days (≥ max lag 14 + live horizons)

/** "2010-12-11" minus (N-1-i) days — 20 days ending on a Saturday. */
const DATES = Array.from({ length: N }, (_, i) => {
  const d = new Date(2010, 11, 11);
  d.setDate(d.getDate() - (N - 1 - i));
  const iso = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${iso(d.getMonth() + 1)}-${iso(d.getDate())}`;
});

function makeSeries(over: Partial<CatalogSeries> = {}): CatalogSeries {
  const mase = (v: number | null) => Array<number | null>(14).fill(v);
  return {
    series_id: "United Kingdom|85123A",
    label: "United Kingdom · 85123A",
    demand_class: "smooth",
    history: { dates: DATES, y: Array.from({ length: N }, (_, i) => i + 1) },
    forecast: {
      dates: DATES.slice(-1).concat(), // replaced below
      y_pred: Array.from({ length: 14 }, (_, i) => 50 + i),
      p10: Array.from({ length: 14 }, (_, i) => 40 + i),
      p90: Array.from({ length: 14 }, (_, i) => 60 + i),
      naive: Array.from({ length: 14 }, (_, i) => 55 + i),
    },
    errors: {
      scale: 2,
      champion: { mae: Array.from({ length: 14 }, (_, i) => 5 + i * 0.5), mase: mase(0.8) },
      naive: { mae: Array.from({ length: 14 }, (_, i) => 7 + i * 0.5), mase: mase(1.2) },
    },
    ...over,
  };
}

const makeSeriesMulti = () => {
  const smooth = makeSeries();
  const intermittent = makeSeries({
    series_id: "France|85123A",
    label: "France · 85123A",
    demand_class: "intermittent",
    errors: {
      scale: 1,
      champion: {
        mae: Array.from({ length: 14 }, () => 6),
        mase: Array.from({ length: 14 }, () => 1.1),
      },
      naive: {
        mae: Array.from({ length: 14 }, () => 5.5),
        mase: Array.from({ length: 14 }, () => 1.05),
      },
    },
  });
  const sparse = makeSeries({
    series_id: "Denmark|37410",
    label: "Denmark · 37410",
    demand_class: "sparse",
    errors: {
      scale: 0,
      champion: {
        mae: Array.from({ length: 14 }, () => 0),
        mase: Array.from({ length: 14 }, () => null),
      },
      naive: {
        mae: Array.from({ length: 14 }, () => 0),
        mase: Array.from({ length: 14 }, () => null),
      },
    },
  });
  return [smooth, intermittent, sparse];
};

describe("maseAt / maeAt", () => {
  it("returns the committed value at horizon h (1-based)", () => {
    const s = makeSeries();
    expect(maseAt(s.errors, 1)).toBe(0.8);
    expect(maseAt(s.errors, 14)).toBe(0.8);
    expect(maseAt(s.errors, 7, "naive")).toBe(1.2);
    expect(maeAt(s.errors, 1)).toBe(5);
    expect(maeAt(s.errors, 14, "naive")).toBe(13.5);
  });

  it("returns null out of range and for null entries (zero-scale sparse)", () => {
    const s = makeSeries({
      errors: {
        scale: 0,
        champion: { mae: Array(14).fill(0), mase: Array(14).fill(null) },
        naive: { mae: Array(14).fill(0), mase: Array(14).fill(null) },
      },
    });
    expect(maseAt(s.errors, 7)).toBeNull();
    expect(maseAt(s.errors, 0)).toBeNull();
    expect(maseAt(s.errors, 15)).toBeNull();
    expect(maseAt(undefined, 7)).toBeNull();
  });
});

describe("windowMase", () => {
  it("pools the non-null per-horizon entries", () => {
    const s = makeSeries();
    expect(windowMase(s.errors)).toBeCloseTo(0.8, 6);
    expect(windowMase(s.errors, "naive")).toBeCloseTo(1.2, 6);
  });

  it("is null when every entry is null (all-zero sparse history)", () => {
    const [_, , sparse] = makeSeriesMulti();
    expect(windowMase(sparse.errors)).toBeNull();
  });
});

describe("coverageNote", () => {
  const payload = {
    scalars: {
      band: {
        target_coverage: 0.8,
        quantile_coverage_pooled: 0.91933,
        split_conformal_coverage_last_fold: 0.85843,
        note: "x",
      },
    },
  } as never;

  it("formats the committed pooled coverage with the target", () => {
    expect(coverageNote(payload)).toEqual({
      value: "91.9%",
      sub: "p10–p90 on backtest (target 80%)",
    });
  });

  it("degrades to n/a without a probabilistic report", () => {
    const noBand = { scalars: { band: null } } as never;
    expect(coverageNote(noBand).value).toBe("n/a");
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

describe("historyPeak", () => {
  it("finds the max daily demand and its date", () => {
    const s = makeSeries();
    expect(historyPeak(s)).toEqual({ value: 20, date: DATES[N - 1] });
  });

  it("returns null for empty history", () => {
    const s = makeSeries({ history: { dates: [], y: [] } });
    expect(historyPeak(s)).toBeNull();
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
  const s = makeSeries(); // history ends Saturday 2010-12-11, y[i] = i+1

  it("builds calendar features for last history date + h (polars weekday)", () => {
    const f = deriveFeatures(s, 1, 1.5); // 2010-12-12, a Sunday
    expect(f.dow).toBe(7);
    expect(f.is_weekend).toBe(1);
    expect(f.month).toBe(12);
    expect(f.t).toBe(N - 1 + 1);
    expect(f.doy_sin).toBeCloseTo(Math.sin((346 * Math.PI * 2) / 365.25), 6);
    expect(f.week).toBe(isoWeek(new Date(2010, 11, 12)));
    const f2 = deriveFeatures(s, 2, 1.5); // Monday
    expect(f2.dow).toBe(1);
    expect(f2.is_weekend).toBe(0);
  });

  it("scales the lags inside the hot week and leaves older lags committed", () => {
    const f = deriveFeatures(s, 1, 1.5);
    expect(f.lag_1).toBe(20 * 1.5); // offset 0 — hot
    expect(f.lag_7).toBe(14 * 1.5); // offset −6 — hot
    expect(f.lag_14).toBe(7); // offset −13 — committed
  });

  it("falls back to the committed forecast when a lag day lands in the window", () => {
    const f = deriveFeatures(s, 3, 1.5);
    // lag_1 day = D+2 = forecast day 2 → committed y_pred[1] = 51 (offset +2 — hot)
    expect(f.lag_1).toBe(51 * 1.5);
    expect(f.lag_7).toBe(16 * 1.5); // history y[15]=16, offset −4 — hot
    expect(f.lag_14).toBe(9); // history y[8]=9, offset −11 — committed
  });

  it("spike 1 leaves every lag committed", () => {
    const f = deriveFeatures(s, 1, 1);
    expect(f.lag_1).toBe(20);
    expect(f.lag_7).toBe(14);
    expect(f.lag_14).toBe(7);
  });
});

describe("class pools and representatives", () => {
  it("pools the window MASE per class, skipping zero-scale series", () => {
    const catalog = makeSeriesMulti();
    expect(classPooledMase(catalog, "smooth")).toBeCloseTo(0.8, 6);
    expect(classPooledMase(catalog, "intermittent")).toBeCloseTo(1.1, 6);
    expect(classPooledMase(catalog, "sparse")).toBeNull();
    expect(classPooledMase(catalog, "smooth", "naive")).toBeCloseTo(1.2, 6);
  });

  it("picks the first (highest-volume) series of each class", () => {
    const catalog = makeSeriesMulti();
    const reps = representativeByClass(catalog);
    expect(reps.smooth?.series_id).toBe("United Kingdom|85123A");
    expect(reps.intermittent?.series_id).toBe("France|85123A");
    expect(reps.sparse?.series_id).toBe("Denmark|37410");
  });
});
