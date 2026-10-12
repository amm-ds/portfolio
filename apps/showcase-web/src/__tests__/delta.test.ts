import { describe, expect, it } from "vitest";
import { computeCallouts, isBaselineRun } from "../lib/delta";

describe("isBaselineRun", () => {
  it("matches naive/random/lag/majority/persistence names", () => {
    expect(isBaselineRun("naive_last")).toBe(true);
    expect(isBaselineRun("random_forest")).toBe(true);
    expect(isBaselineRun("lag_7_baseline")).toBe(true);
    expect(isBaselineRun("majority_class")).toBe(true);
    expect(isBaselineRun("persistence_forecast")).toBe(true);
  });

  it("does not match regular model names", () => {
    expect(isBaselineRun("xgboost_tuned")).toBe(false);
    expect(isBaselineRun("lightgbm_v2")).toBe(false);
  });
});

describe("computeCallouts", () => {
  it("returns callouts for each present run with headline metric", () => {
    const callouts = computeCallouts(
      { baseline: { mae: 10 }, tuned: { mae: 7 } },
      ["baseline", "tuned"],
    );
    expect(callouts).toHaveLength(2);
    expect(callouts.find((c) => c.run === "tuned")).toMatchObject({
      metric: "mae",
      value: 7,
      lowerIsBetter: true,
    });
  });

  it("computes an improved delta for the best run vs a naive baseline", () => {
    const callouts = computeCallouts(
      { naive_last: { mae: 100 }, lightgbm: { mae: 72 } },
      ["naive_last", "lightgbm"],
    );
    const best = callouts.find((c) => c.run === "lightgbm")!;
    expect(best.deltaPct).toBeCloseTo(-28);
    expect(best.baselineRun).toBe("naive_last");
    expect(best.improved).toBe(true);
    // the baseline itself carries no delta
    expect(callouts.find((c) => c.run === "naive_last")!.deltaPct).toBeNull();
  });

  it("treats higher-is-better metrics (f1) as improved when positive", () => {
    const callouts = computeCallouts(
      { random_guess: { f1: 0.5 }, bert_tuned: { f1: 0.65 } },
      ["random_guess", "bert_tuned"],
    );
    const best = callouts.find((c) => c.run === "bert_tuned")!;
    expect(best.deltaPct).toBeCloseTo(30);
    expect(best.improved).toBe(true);
  });

  it("marks a worse-than-baseline delta as regressed", () => {
    const callouts = computeCallouts(
      { naive_last: { mae: 50 }, overfit_net: { mae: 60 } },
      ["naive_last", "overfit_net"],
    );
    const best = callouts.find((c) => c.run === "overfit_net")!;
    expect(best.improved).toBe(false);
  });

  it("attaches the delta to the BEST run only when several candidates exist", () => {
    const callouts = computeCallouts(
      {
        naive_last: { mae: 100 },
        model_a: { mae: 80 },
        model_b: { mae: 60 },
      },
      ["naive_last", "model_a", "model_b"],
    );
    expect(callouts.find((c) => c.run === "model_b")!.deltaPct).toBeCloseTo(-40);
    expect(callouts.find((c) => c.run === "model_a")!.deltaPct).toBeNull();
  });

  it("returns no delta when no referenced run is a baseline", () => {
    const callouts = computeCallouts(
      { model_a: { mae: 5 }, model_b: { mae: 4 } },
      ["model_a", "model_b"],
    );
    expect(callouts.every((c) => c.deltaPct === null)).toBe(true);
  });

  it("skips referenced runs missing from metrics or without numeric values", () => {
    const callouts = computeCallouts(
      { naive_last: { mae: 10 }, good: { mae: 5 }, weird: { note: "n/a" } as never },
      ["naive_last", "missing_run", "weird", "good"],
    );
    expect(callouts.map((c) => c.run).sort()).toEqual(["good", "naive_last"]);
    expect(callouts.find((c) => c.run === "good")!.deltaPct).toBeCloseTo(-50);
  });

  it("falls back to the baseline headline metric when the best metric is absent there", () => {
    const callouts = computeCallouts(
      {
        naive_last: { rmse: 12 }, // no "mae" key
        model_x: { mae: 9, rmse: 11 },
      },
      ["naive_last", "model_x"],
    );
    const best = callouts.find((c) => c.run === "model_x")!;
    // baseline rmse 12 vs best mae 9 → -25%
    expect(best.deltaPct).toBeCloseTo(-25);
    expect(best.baselineRun).toBe("naive_last");
  });

  it("returns no delta when the baseline value is zero", () => {
    const callouts = computeCallouts(
      { naive_zeros: { mae: 0 }, model: { mae: 3 } },
      ["naive_zeros", "model"],
    );
    expect(callouts.every((c) => c.deltaPct === null)).toBe(true);
  });
});
