import { describe, expect, it } from "vitest";
import { parseDatasets, parseRunDetail, parseRuns } from "./contracts";
import { FIXTURE_DATASETS, FIXTURE_RUNS } from "./fixtures";

describe("API response contracts", () => {
  it("accepts valid registry, run summary, and run detail payloads", () => {
    expect(parseDatasets(FIXTURE_DATASETS)).toHaveLength(2);
    expect(parseRuns(FIXTURE_RUNS)).toHaveLength(4);
    expect(parseRunDetail(FIXTURE_RUNS[0]).cases).toHaveLength(4);
  });

  it("rejects scores outside the documented 0–1 range", () => {
    const runs = structuredClone(FIXTURE_RUNS);
    runs[0].metrics!.accuracy = 1.1;
    expect(() => parseRuns(runs)).toThrow("run metrics.accuracy");
  });

  it("rejects malformed run cases at the trust boundary", () => {
    const run = structuredClone(FIXTURE_RUNS[0]);
    run.cases[0].passed = "yes" as unknown as boolean;
    expect(() => parseRunDetail(run)).toThrow("run case.passed");
  });

  it("rejects unsupported run states", () => {
    const runs = structuredClone(FIXTURE_RUNS);
    runs[0].status = "complete" as unknown as typeof runs[0]["status"];
    expect(() => parseRuns(runs)).toThrow("run.status");
  });
});
