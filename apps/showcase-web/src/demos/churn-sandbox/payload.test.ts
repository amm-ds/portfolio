import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ChurnPayload } from "../types";
import { fetchChurnPayload } from "./payload";

/** The REAL committed payload (built by `churn-pipeline demo-payload`) — the
 * contract test fails if the artifact drifts from what the UI reads. Vitest
 * runs with apps/showcase-web as cwd (same readFileSync pattern as the
 * forecast workbench's payload.test.ts). */
const PAYLOAD_PATH = "../../projects/05-ml-pipeline-churn/reports/demo_payload.json";

const payload = JSON.parse(readFileSync(PAYLOAD_PATH, "utf8")) as ChurnPayload;

describe("churn-sandbox payload contract (real committed JSON)", () => {
  it("carries the top-level contract the demo reads", () => {
    expect(payload.demo).toBe("churn-threshold-sandbox");
    expect(payload.project).toBe("05-ml-pipeline-churn");
    for (const key of [
      "demo",
      "project",
      "holdout_n",
      "model",
      "cost_model",
      "headline",
      "thresholds",
      "overall",
      "slices",
      "calibration",
      "customers",
      "feature_domains",
      "roc_auc",
    ]) {
      expect(payload).toHaveProperty(key);
    }
    // the retired report link stays retired — nothing serves it
    expect(payload).not.toHaveProperty("report");
  });

  it("pins the committed model and cost model", () => {
    expect(payload.model.name).toBe("selected_model_calibrated");
    expect(payload.model.threshold_default).toBe(0.5);
    // the served operating threshold the demo seeds its cursor with
    expect(payload.model.threshold_selected).toBe(0.175);
    expect(payload.model.roc_auc).toBeCloseTo(0.8317, 3);
    expect(payload.roc_auc).toBe(payload.model.roc_auc);
    expect(payload.model.ece).toBeCloseTo(0.0164, 3);
    expect(payload.cost_model).toEqual({
      fp_cost: 1,
      fn_cost: 5,
      note: "cost = fp_cost·FP + fn_cost·FN across the 1,409-row holdout",
    });
    expect(payload.holdout_n).toBe(1409);
  });

  it("pins the headline decision-cost numbers quoted in the manifest hero", () => {
    const { headline } = payload;
    expect(headline.cost_naive).toBe(1035);
    expect(headline.cost_selected).toBe(601);
    expect(headline.delta_ci).toEqual({
      point: -434,
      lo: -508,
      hi: -353,
      significant_95: true,
    });
    // the hero renders these as "$601 vs $1,035 contact-everyone" + the paired CI
    expect(Math.round(headline.cost_selected)).toBe(601);
    expect(Math.round(headline.cost_naive)).toBe(1035);
    // …and the committed threshold grid reproduces the headline cost at the
    // pipeline miss multiplier (FP·1 + FN·5, argmin on the shipped grid)
    const costAt = (row: { fp: number; fn: number }) => row.fp + payload.cost_model.fn_cost * row.fn;
    expect(Math.min(...payload.overall.map(costAt))).toBe(headline.cost_selected);
  });

  it("ships the threshold grid and per-threshold confusion rows in lockstep", () => {
    expect(payload.thresholds).toHaveLength(45);
    expect(payload.thresholds[0]).toBe(0.02);
    expect(payload.thresholds.at(-1)).toBe(0.9);
    expect(payload.overall).toHaveLength(payload.thresholds.length);
    for (let i = 0; i < payload.overall.length; i++) {
      const row = payload.overall[i];
      expect(row.t).toBe(payload.thresholds[i]);
      // counts partition the holdout
      expect(row.tn + row.fp + row.fn + row.tp).toBe(payload.holdout_n);
    }
    // contract slices carry per-threshold rows on the same grid
    for (const rows of Object.values(payload.slices.contract)) {
      expect(rows).toHaveLength(payload.thresholds.length);
    }
  });

  it("pins the preset customers and calibration bins", () => {
    expect(payload.customers.map((c) => c.churn_probability)).toEqual([0.5961, 0.0345, 0.0581]);
    for (const c of payload.customers) {
      expect(c.churn_probability).toBeGreaterThan(0);
      expect(c.churn_probability).toBeLessThan(1);
      expect(c.features.tenure_months).toBeGreaterThanOrEqual(
        payload.feature_domains.tenure_months.min,
      );
      expect(c.features.tenure_months).toBeLessThanOrEqual(
        payload.feature_domains.tenure_months.max,
      );
    }
    expect(payload.calibration.length).toBeGreaterThan(0);
    for (const bin of payload.calibration) {
      expect(bin.n).toBeGreaterThan(0);
      expect(bin.observed).toBeGreaterThanOrEqual(0);
      expect(bin.observed).toBeLessThanOrEqual(1);
    }
  });
});


describe("churn-sandbox runtime payload validation", () => {
  afterEach(() => vi.unstubAllGlobals());

  function serve(value: unknown): void {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(value))));
  }

  it("accepts the committed legacy-v1 payload and forwards cancellation", async () => {
    serve(payload);
    const controller = new AbortController();
    await expect(fetchChurnPayload("churn-sandbox", controller.signal)).resolves.toEqual(payload);
    expect(fetch).toHaveBeenCalledWith("/demos/churn-sandbox/payload", {
      signal: controller.signal,
    });
  });

  it("rejects a declared wrong schema version", async () => {
    const wrongVersion = structuredClone(payload);
    Object.assign(wrongVersion, { schema_version: 2 });
    serve(wrongVersion);
    await expect(fetchChurnPayload("churn-sandbox")).rejects.toThrow("schema_version");
  });

  it("rejects malformed nested model data", async () => {
    const malformed = structuredClone(payload);
    Object.assign(malformed.model, { threshold_selected: "not-a-number" });
    serve(malformed);
    await expect(fetchChurnPayload("churn-sandbox")).rejects.toThrow("invalid churn demo payload");
  });
});
