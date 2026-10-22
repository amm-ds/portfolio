import { describe, expect, it } from "vitest";
import type { ProfitGrid } from "../types";
import {
  crossoverCost,
  incrementalAt,
  mailEveryoneAt,
  nearestIndex,
  peakFractionAt,
  policyProfitAt,
  profitAt,
  winnerAt,
} from "./kpis";

// 3 costs × 4 fractions synthetic lattice, values in total campaign profit ($).
const COSTS = [0.01, 0.02, 0.03];
const FRACTIONS = [0.1, 0.25, 0.5, 1.0];
const GRID: ProfitGrid = {
  costs: COSTS,
  fractions: FRACTIONS,
  policies: {
    best_arm: {
      profit: [
        [100, 300, 250, 50],
        [80, 260, 240, 40],
        [60, 220, 230, 30],
      ],
    },
    single_arm: {
      profit: [
        [90, 200, 180, 20],
        [70, 180, 170, 10],
        [50, 160, 160, 0],
      ],
    },
    random: {
      profit: [
        [40, 100, 120, 140],
        [30, 90, 110, 130],
        [20, 80, 100, 120],
      ],
    },
  },
  n_boot: 100,
  seed: 1,
  alpha: 0.05,
  model_estimated: true,
  note: "synthetic fixture",
};

// Mail-everyone-mens line: profitable at cheap costs, collapses as cost grows
// slower than targeting because it sends 4× the emails at the same budget row.
const MAIL_MENS = [400, 200, 100];

describe("profitAt / policyProfitAt", () => {
  it("reads best-arm profit at a lattice point", () => {
    expect(profitAt(GRID, 0, 1)).toBe(300);
    expect(profitAt(GRID, 2, 2)).toBe(230);
  });
  it("reads other policies at the same point", () => {
    expect(policyProfitAt(GRID, "single_arm", 0, 1)).toBe(200);
    expect(policyProfitAt(GRID, "random", 0, 1)).toBe(100);
  });
  it("degrades to 0 out of range instead of throwing mid-drag", () => {
    expect(profitAt(GRID, 99, 1)).toBe(0);
    expect(profitAt(GRID, 0, 99)).toBe(0);
  });
});

describe("winnerAt", () => {
  it("names best-arm when targeting profits are higher", () => {
    expect(winnerAt(300, 250)).toBe("best_arm");
  });
  it("names mail-everyone-mens when the baseline profits are higher", () => {
    expect(winnerAt(100, 400)).toBe("mail_everyone_mens");
  });
  it("gives ties to mail-everyone (targeting needs a clear edge)", () => {
    expect(winnerAt(250, 250)).toBe("mail_everyone_mens");
  });
});

describe("peakFractionAt", () => {
  it("returns the fraction at the row argmax", () => {
    expect(peakFractionAt(GRID, 0)).toBe(0.25); // 300 is the row max
    expect(peakFractionAt(GRID, 2)).toBe(0.5); // 230 is the row max
  });
  it("degrades to the first fraction out of range", () => {
    expect(peakFractionAt(GRID, 99)).toBe(0.1);
  });
});

describe("crossoverCost", () => {
  it("finds the cost index where best-arm overtakes mail-everyone", () => {
    // diffs at fracIdx 1: 300−400=−100, 260−200=+60, 220−100=+120 → idx 1
    expect(crossoverCost(GRID, 1, MAIL_MENS)).toBe(1);
  });
  it("returns 0 when targeting already wins at the cheapest cost", () => {
    expect(crossoverCost(GRID, 3, [10, 0, -10])).toBe(0);
  });
  it("returns null when mail-everyone never loses", () => {
    expect(crossoverCost(GRID, 0, [500, 400, 300])).toBeNull();
  });
});

describe("mailEveryoneAt", () => {
  const MAP = { "0.01": 49818.73, "0.50": 18618.73 };
  it("looks up by two-decimal string key", () => {
    expect(mailEveryoneAt(MAP, 0.01)).toBe(49818.73);
    expect(mailEveryoneAt(MAP, 0.5)).toBe(18618.73);
  });
  it("degrades to 0 on a missing key", () => {
    expect(mailEveryoneAt(MAP, 0.3)).toBe(0);
  });
});

describe("incrementalAt", () => {
  it("inverts the profit formula", () => {
    // profit 300 at f=0.25, c=0.02, N=1000, revenue=10 → inc = (300+5)/10 = 30.5
    expect(incrementalAt(300, 0.25, 0.02, 1000, 10)).toBeCloseTo(30.5);
  });
  it("clamps the degenerate inverted value at 0", () => {
    expect(incrementalAt(-500, 0.25, 0.02, 1000, 10)).toBe(0);
  });
  it("degrades to 0 with a zero revenue model", () => {
    expect(incrementalAt(300, 0.25, 0.02, 1000, 0)).toBe(0);
  });
});

describe("nearestIndex", () => {
  it("finds the nearest grid index", () => {
    expect(nearestIndex(COSTS, 0.02)).toBe(1);
    expect(nearestIndex(FRACTIONS, 0.24)).toBe(1);
  });
  it("degrades to 0 on an empty grid", () => {
    expect(nearestIndex([], 0.5)).toBe(0);
  });
});
