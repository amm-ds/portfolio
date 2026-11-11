/** Field vitals: observers shape LCP/INP/CLS, flush beacons a privacy-safe batch. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { deviceClass, routeKey } from "../lib/vitals";

const observerCallbacks = new Map<string, (list: { getEntries(): unknown[] }) => void>();

class FakePerformanceObserver {
  private cb: (list: { getEntries(): unknown[] }) => void;
  constructor(cb: (list: { getEntries(): unknown[] }) => void) {
    this.cb = cb;
  }
  observe(opts: { type: string }) {
    observerCallbacks.set(opts.type, this.cb);
  }
}

function emit(type: string, entries: unknown[]) {
  observerCallbacks.get(type)?.({ getEntries: () => entries });
}

describe("vitals collector", () => {
  beforeEach(() => {
    vi.resetModules();
    observerCallbacks.clear();
    vi.stubGlobal("PerformanceObserver", FakePerformanceObserver);
  });

  it("reduces routes to their first two segments", () => {
    expect(routeKey("/")).toBe("/");
    expect(routeKey("/projects")).toBe("/projects");
    expect(routeKey("/projects/07-open-data-mobility")).toBe("/projects/07-open-data-mobility");
    expect(routeKey("/projects/07-open-data-mobility/report")).toBe(
      "/projects/07-open-data-mobility",
    );
    expect(routeKey("/demos/churn-sandbox/extra/deep")).toBe("/demos/churn-sandbox");
  });

  it("classifies device by viewport width", () => {
    const original = window.innerWidth;
    try {
      for (const [w, expected] of [
        [500, "mobile"],
        [800, "tablet"],
        [1400, "desktop"],
      ] as const) {
        Object.defineProperty(window, "innerWidth", { value: w, configurable: true });
        expect(deviceClass()).toBe(expected);
      }
    } finally {
      Object.defineProperty(window, "innerWidth", { value: original, configurable: true });
    }
  });

  it("beacons one shaped batch on flush: input-shift excluded, INP max kept", async () => {
    const sendBeacon = vi.fn().mockReturnValue(true);
    Object.defineProperty(navigator, "sendBeacon", { value: sendBeacon, configurable: true });

    const mod = await import("../lib/vitals");
    mod.installVitals();
    expect(observerCallbacks.has("largest-contentful-paint")).toBe(true);

    emit("largest-contentful-paint", [{ startTime: 1234.4 }]);
    emit("layout-shift", [
      { value: 0.02, hadRecentInput: false },
      { value: 0.5, hadRecentInput: true }, // user-caused: excluded
    ]);
    emit("event", [
      { duration: 88, interactionId: 7 },
      { duration: 40, interactionId: 0 }, // not an interaction: excluded
    ]);

    mod.flush();
    expect(sendBeacon).toHaveBeenCalledTimes(1);
    const [url, blob] = sendBeacon.mock.calls[0] as [string, Blob];
    expect(url).toBe("/vitals");
    const parsed = JSON.parse(await blob.text()) as {
      vitals: { metric: string; value: number; route: string; device: string; sha: string }[];
    };
    expect(parsed.vitals.map((v) => v.metric).sort()).toEqual(["CLS", "INP", "LCP"]);
    expect(parsed.vitals.find((v) => v.metric === "LCP")?.value).toBe(1234);
    expect(parsed.vitals.find((v) => v.metric === "CLS")?.value).toBe(0.02);
    expect(parsed.vitals.find((v) => v.metric === "INP")?.value).toBe(88);
    for (const vital of parsed.vitals) {
      expect(vital.route).toBe("/");
      expect(vital.device).toBe("desktop");
      expect(vital.sha.length).toBeGreaterThanOrEqual(3);
    }
    // nothing left to send
    mod.flush();
    expect(sendBeacon).toHaveBeenCalledTimes(1);
  });

  it("does not beacon when nothing was measured", async () => {
    const sendBeacon = vi.fn().mockReturnValue(true);
    Object.defineProperty(navigator, "sendBeacon", { value: sendBeacon, configurable: true });
    const mod = await import("../lib/vitals");
    mod.installVitals();
    mod.flush();
    expect(sendBeacon).not.toHaveBeenCalled();
  });
});
