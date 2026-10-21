import { describe, expect, it } from "vitest";
import type { ConfusionRow } from "../types";
import { contactCount, costAt, nearestIndex, noticeText, recallAt, savings } from "./kpis";

// 5-threshold fixture, holdout n = 1,000 (per-1,000 counts are the raw counts).
const OVERALL: ConfusionRow[] = [
  { t: 0.1, tn: 600, fp: 300, fn: 10, tp: 90 },
  { t: 0.3, tn: 690, fp: 210, fn: 25, tp: 75 },
  { t: 0.5, tn: 760, fp: 140, fn: 45, tp: 55 },
  { t: 0.7, tn: 820, fp: 80, fn: 65, tp: 35 },
  { t: 0.9, tn: 870, fp: 30, fn: 85, tp: 15 },
];
const THRESHOLDS = OVERALL.map((r) => r.t);

describe("costAt", () => {
  it("is fp + fn_ratio * fn", () => {
    expect(costAt(OVERALL[1], 5)).toBe(210 + 5 * 25); // 335
    expect(costAt(OVERALL[1], 1)).toBe(210 + 25); // 235
    expect(costAt(OVERALL[2], 5)).toBe(140 + 5 * 45); // 365
  });
});

describe("savings", () => {
  it("is negative (savings) when the cursor beats the 0.5 default", () => {
    expect(savings(OVERALL[1], OVERALL[2], 5)).toBe(335 - 365); // -30
  });
  it("flips positive when the multiplier makes the cursor worse", () => {
    // fn_ratio 1: cursor cost 235 vs default 185 → +50 (costs)
    expect(savings(OVERALL[1], OVERALL[2], 1)).toBe(235 - 185);
  });
});

describe("contactCount / recallAt", () => {
  it("counts TP + FP contacts", () => {
    expect(contactCount(OVERALL[1])).toBe(75 + 210); // 285
  });
  it("computes recall as tp / (tp + fn)", () => {
    expect(recallAt(OVERALL[1])).toBeCloseTo(75 / 100); // 0.75
    expect(recallAt({ t: 0, tn: 0, fp: 0, fn: 0, tp: 0 })).toBe(0); // no churners
  });
});

describe("nearestIndex", () => {
  it("finds the grid index nearest to t", () => {
    expect(nearestIndex(THRESHOLDS, 0.3)).toBe(1);
    expect(nearestIndex(THRESHOLDS, 0.5)).toBe(2);
    expect(nearestIndex(THRESHOLDS, 0.175)).toBe(0);
  });
});

describe("noticeText", () => {
  it("reports the local trade of extra alarms per churner caught", () => {
    // moving from t=0.3 to t=0.1: +15 churners, +105 contacts → 7 alarms each
    expect(noticeText(OVERALL[1], OVERALL[0], 5)).toBe(
      "at 5× a miss, catching one more churner here costs ~7 extra false alarms",
    );
  });
  it("rounds fractional trades to one decimal", () => {
    // +20 churners, +30 contacts → 1.5 alarms each
    const laxer: ConfusionRow = { t: 0, tn: 0, fp: 310, fn: 0, tp: 110 };
    expect(noticeText(OVERALL[0], laxer, 5)).toBe(
      "at 5× a miss, catching one more churner here costs ~1.5 extra false alarms",
    );
  });
  it("falls back to the recall ceiling when no laxer row catches more", () => {
    expect(noticeText(OVERALL[0], null, 5)).toBe(
      "at 5× a miss this threshold already catches 90% of churners — every additional alarm is a false one",
    );
  });
});
