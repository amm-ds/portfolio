import { describe, expect, it } from "vitest";
import type { HierGroupBlock, HierNode, HierOrigin } from "../types";
import {
  axisFor,
  coherencePair,
  groupTotalRmae,
  horizonMae,
  isBottom,
  maeByVariant,
  nodeLeaf,
  nodeOrigin,
  nodeSegments,
  valuesOnAxis,
} from "./kpis";

/** Synthetic origin: 2-period history ending at the origin, 2-step horizon. */
function makeOrigin(overrides: Partial<HierOrigin> = {}): HierOrigin {
  return {
    origin: "2019-02-01",
    history: { dates: ["2018-12-01", "2019-01-01", "2019-02-01"], y: [10, 12, 14] },
    actuals: { dates: ["2019-03-01", "2019-04-01"], y: [16, 20] },
    models: {
      seasonal_naive: { y_pred: [14, 14] },
      auto_ets: { y_pred: [15, 18] },
      lgbm_global: { y_pred: [18, 22] },
      "lgbm_global+bottom_up": { y_pred: [16, 20] },
      "lgbm_global+mint_shrink": { y_pred: [16.5, 19] },
    },
    coherence: null,
    ...overrides,
  };
}

function makeNode(overrides: Partial<HierNode> = {}): HierNode {
  return {
    node: "['Total']",
    group: "Labour",
    level: "total",
    parent_path: [],
    children_count: 2,
    children: ["a", "b"],
    origins: [makeOrigin()],
    ...overrides,
  };
}

describe("horizonMae", () => {
  it("averages absolute errors over the horizon", () => {
    // |14−16| = 2, |14−20| = 6 → MAE 4
    expect(horizonMae([14, 14], [16, 20])).toBeCloseTo(4, 12);
    // exact forecast → 0
    expect(horizonMae([16, 20], [16, 20])).toBe(0);
  });

  it("returns null on length mismatch, empty curves, or non-finite values", () => {
    expect(horizonMae([1, 2, 3], [1, 2])).toBeNull();
    expect(horizonMae([], [1])).toBeNull();
    expect(horizonMae(undefined, [1])).toBeNull();
    expect(horizonMae([NaN, 1], [1, 2])).toBeNull();
  });
});

describe("maeByVariant", () => {
  it("computes every variant against the actuals", () => {
    const o = makeOrigin();
    const mae = maeByVariant(o);
    expect(mae.seasonal_naive).toBeCloseTo(4, 12);
    expect(mae.auto_ets).toBeCloseTo((1 + 2) / 2, 12);
    expect(mae.lgbm_global).toBeCloseTo((2 + 2) / 2, 12);
    expect(mae["lgbm_global+bottom_up"]).toBeCloseTo(0, 12);
    expect(mae["lgbm_global+mint_shrink"]).toBeCloseTo((0.5 + 1) / 2, 12);
  });

  it("returns nulls for a missing origin — never fabricated", () => {
    const mae = maeByVariant(null);
    for (const v of Object.keys(mae)) expect(mae[v as keyof typeof mae]).toBeNull();
  });
});

describe("node identity helpers", () => {
  it("parses slug and stringified-list ids", () => {
    expect(nodeSegments("nsw-hol")).toEqual(["nsw-hol"]);
    expect(nodeSegments("['Total']")).toEqual(["Total"]);
    expect(nodeSegments("['Males', 'New South Wales']")).toEqual(["Males", "New South Wales"]);
    expect(nodeLeaf("['Males', 'New South Wales']")).toBe("New South Wales");
    expect(nodeLeaf("total")).toBe("total");
  });

  it("isBottom keys off children, not the level string alone", () => {
    expect(isBottom(makeNode({ children_count: 0, children: [], level: "bottom" }))).toBe(true);
    expect(isBottom(makeNode({ children_count: 0, children: [], level: "weird" }))).toBe(true);
    expect(isBottom(makeNode())).toBe(false);
  });
});

describe("origin + axis helpers", () => {
  it("nodeOrigin finds the block by date and misses safely", () => {
    const node = makeNode({
      origins: [makeOrigin(), makeOrigin({ origin: "2019-03-01" })],
    });
    expect(nodeOrigin(node, "2019-03-01")?.origin).toBe("2019-03-01");
    expect(nodeOrigin(node, "2000-01-01")).toBeNull();
  });

  it("axisFor concatenates history and actuals contiguously", () => {
    const o = makeOrigin();
    expect(axisFor(o)).toEqual([
      "2018-12-01",
      "2019-01-01",
      "2019-02-01",
      "2019-03-01",
      "2019-04-01",
    ]);
    expect(axisFor(null)).toEqual([]);
  });

  it("valuesOnAxis maps onto the axis and leaves gaps as NaN", () => {
    const axis = axisFor(makeOrigin());
    const hist = valuesOnAxis(axis, ["2018-12-01", "2019-02-01"], [10, 14]);
    expect(hist[0]).toBe(10);
    expect(Number.isNaN(hist[1])).toBe(true);
    expect(hist[2]).toBe(14);
    const act = valuesOnAxis(axis, ["2019-03-01"], [16]);
    expect(Number.isNaN(act[2])).toBe(true);
    expect(act[3]).toBe(16);
  });
});

describe("committed-block selectors", () => {
  const group = {
    coherence: {
      seasonal_naive: 0,
      "lgbm_global+bottom_up": 0,
      "lgbm_global+mint_shrink": 0,
      lgbm_global: 0.016,
    },
    headline: {
      claim: "lgbm_global+mint_shrink posts rmae 0.297 …",
      total: {
        rmae: 0.2969,
        mae: 88.5,
        naive_mae: 298.1,
        bootstrap: { diff: -209.6, ci95: [-321.1, -49.8], spans_zero: false },
      },
      bottom: {
        rmae: 0.804,
        mae: 10.5,
        naive_mae: 13.0,
        bootstrap: { diff: -2.5, ci95: [-5.7, 0.1], spans_zero: true },
      },
    },
  } as unknown as HierGroupBlock;

  it("coherencePair picks raw vs MinT and misses safely", () => {
    expect(coherencePair(group)).toEqual({ raw: 0.016, mint: 0 });
    expect(coherencePair({ coherence: {} } as unknown as HierGroupBlock)).toBeNull();
  });

  it("groupTotalRmae reads the committed headline", () => {
    expect(groupTotalRmae(group)).toBeCloseTo(0.2969, 12);
    expect(groupTotalRmae({} as unknown as HierGroupBlock)).toBeNull();
  });
});
