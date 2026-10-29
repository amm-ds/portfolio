import { describe, expect, it } from "vitest";
import type { ForecastWindow } from "../types";
import { bestModelAt, peakAbsError, peakDayMae, verdictText, wapeAt } from "./kpis";

// 4-day fixture: actual [10, 20, 10, 40]; naive flat 10; lgbm [12, 18, 14, 30].
const ACTUAL = [10, 20, 10, 40];
const NAIVE = [10, 10, 10, 10];
const LGBM = [12, 18, 14, 30];

function windowOf(curves: Record<string, number[]>): ForecastWindow {
  return {
    history: [1, 2, 3],
    actual: ACTUAL,
    curves,
    band: { p10: [8, 8, 8, 8], p90: [16, 20, 20, 36] },
    wape: {},
    shape: "steady",
  };
}

describe("wapeAt", () => {
  it("is Σ|err| / Σ actual over the first h days", () => {
    // h=2: |10-12| + |20-18| = 4; volume 30
    expect(wapeAt(ACTUAL, LGBM, 2)).toBeCloseTo(4 / 30);
    // h=4: 2 + 2 + 4 + 10 = 18; volume 80
    expect(wapeAt(ACTUAL, LGBM, 4)).toBeCloseTo(18 / 80);
  });
  it("clamps h to the array length", () => {
    expect(wapeAt(ACTUAL, LGBM, 99)).toBe(wapeAt(ACTUAL, LGBM, 4));
  });
  it("is 0 when the scored volume is 0", () => {
    expect(wapeAt([0, 0], [1, 1], 2)).toBe(0);
  });
});

describe("peakDayMae", () => {
  it("scores MAE on the top-decile-by-actual days (k = ceil(0.1·h))", () => {
    // h=4 -> k=1: only the biggest day (40): |30-40| = 10
    expect(peakDayMae(ACTUAL, LGBM, 4)).toBeCloseTo(10);
    // h=1 -> k=1: the top day of the first 1 is day 0
    expect(peakDayMae(ACTUAL, LGBM, 1)).toBeCloseTo(2);
    // naive on the top day: |10-40| = 30
    expect(peakDayMae(ACTUAL, NAIVE, 4)).toBeCloseTo(30);
  });
});

describe("bestModelAt", () => {
  it("prefers the lowest WAPE@h among the selected non-naive models", () => {
    const win = windowOf({ seasonal_naive: NAIVE, lgbm: LGBM, auto_ets: [10, 20, 10, 40] });
    // auto_ets is exact on this window -> wins
    expect(bestModelAt(win, ["seasonal_naive", "lgbm", "auto_ets"], 4)).toBe("auto_ets");
    expect(bestModelAt(win, ["seasonal_naive", "lgbm"], 4)).toBe("lgbm");
  });
  it("falls back to the floor when it is the only selection", () => {
    const win = windowOf({ seasonal_naive: NAIVE });
    expect(bestModelAt(win, ["seasonal_naive"], 4)).toBe("seasonal_naive");
  });
  it("returns null when no selected curve exists", () => {
    const win = windowOf({});
    expect(bestModelAt(win, ["lgbm"], 4)).toBeNull();
  });
});

describe("verdictText", () => {
  it("reports a win with the relative margin", () => {
    const win = windowOf({ seasonal_naive: NAIVE, lgbm: LGBM });
    const text = verdictText(win, "lgbm", 4);
    expect(text).toContain("beats the seasonal naive");
    // lgbm 18/80 = 0.225 vs naive 40/80 = 0.5 -> (0.225-0.5)/0.5 = -55.0%
    expect(text).toContain("55.0%");
    expect(text[0]).toMatch(/[A-Z]/);
  });
  it("reports an honest per-series loss without inventing a pooled claim", () => {
    const win = windowOf({ seasonal_naive: [10, 20, 10, 40], lgbm: [0, 0, 0, 0] });
    const text = verdictText(win, "lgbm", 4);
    expect(text).toContain("still wins this series");
    expect(text).toContain("pooled gap excludes zero");
  });
  it("degrades to a prompt when no model is selected", () => {
    const win = windowOf({});
    expect(verdictText(win, null, 4)).toContain("Select a model");
  });
});

describe("peakAbsError", () => {
  it("is the worst single-day |err| over the first h days", () => {
    // naive: 0, 10, 0, 30
    expect(peakAbsError(ACTUAL, NAIVE, 4)).toBe(30);
    expect(peakAbsError(ACTUAL, NAIVE, 2)).toBe(10);
    expect(peakAbsError(ACTUAL, LGBM, 4)).toBe(10);
  });
});
