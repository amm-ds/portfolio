import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import ForecastWorkbench from "../demos/forecast-workbench/ForecastWorkbench";
import type { ForecastWorkbenchPayload } from "../demos/types";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const CURVES = {
  seasonal_naive: [12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12],
  auto_ets: [11, 12, 13, 12, 11, 12, 13, 12, 11, 12, 13, 12, 11, 12, 13, 12, 11, 12, 13, 12, 11, 12, 13, 12, 11, 12, 13, 12],
  lgbm: [10, 11, 14, 13, 11, 10, 12, 14, 13, 11, 10, 12, 14, 13, 11, 10, 12, 14, 13, 11, 10, 12, 14, 13, 11, 10, 12, 14],
  convex_ensemble: [11, 12, 13, 12, 11, 11, 13, 13, 12, 11, 11, 12, 13, 13, 11, 11, 12, 13, 13, 11, 11, 12, 13, 13, 11, 11, 12, 13],
};
const ACTUAL = [10, 12, 15, 12, 11, 9, 13, 15, 14, 11, 10, 12, 16, 15, 12, 10, 11, 14, 16, 13, 11, 10, 13, 15, 14, 12, 11, 13];
const HISTORY = [9, 10, 11, 10, 12, 13, 11, 10];

function windowOf(shape: string) {
  return {
    history: HISTORY,
    actual: ACTUAL,
    curves: CURVES,
    band: {
      p10: CURVES.lgbm.map((v) => Math.max(0, v - 4)),
      p90: CURVES.lgbm.map((v) => v + 4),
    },
    wape: { seasonal_naive: 0.2, auto_ets: 0.18, lgbm: 0.15, convex_ensemble: 0.16 },
    shape,
  };
}

/** 4-series fixture: 2 stores × (dense + intermittent), 2 scored origins. */
const PAYLOAD: ForecastWorkbenchPayload = {
  schema_version: 4,
  demo: "forecast-workbench",
  project: "02-demand-forecasting",
  protocol: "m5_direct_v1",
  groups: {
    headline: {
      lgbm_vs_naive: {
        wape: { diff: -0.0911, ci95: [-0.1023, -0.0803], spans_zero: false },
        wrmsse: { diff: -0.1509, ci95: [-0.1625, -0.1396], spans_zero: false },
      },
      convex_ensemble_vs_naive: {
        wape: { diff: -0.1049, ci95: [-0.1154, -0.0946], spans_zero: false },
        wrmsse: { diff: -0.1574, ci95: [-0.1679, -0.147], spans_zero: false },
      },
      baseline: "seasonal_naive",
    },
    test_pooled: {
      seasonal_naive: { mae: 5.77, wape: 0.6032, rmae: 1.0, wrmsse: 0.7617, wrmsse_weighted: 0.7197, peak_mae: 14.43 },
      auto_ets: { mae: 4.82, wape: 0.5035, rmae: 0.8347, wrmsse: 0.6105, wrmsse_weighted: 0.5891, peak_mae: 12.95 },
      lgbm: { mae: 4.9, wape: 0.5121, rmae: 0.849, wrmsse: 0.6108, wrmsse_weighted: 0.5851, peak_mae: 12.81 },
      convex_ensemble: { mae: 4.77, wape: 0.4983, rmae: 0.826, wrmsse: 0.6043, wrmsse_weighted: 0.5828, peak_mae: 12.89 },
    },
    test_by_class: {},
    win_rate_vs_naive: {
      seasonal_naive: { pooled: 0.0, dense: 0.0, intermittent: 0.0 },
      convex_ensemble: { pooled: 0.8933, dense: 0.8898, intermittent: 0.9051 },
    },
    classes: { counts: { dense: 463, intermittent: 137 }, thresholds: { adi: 1.32, cv2: 0.49 } },
    ensemble: {
      pool: ["lgbm", "auto_ets", "auto_ces"],
      selection_wape: { lgbm: 0.4877, auto_ets: 0.4729, auto_ces: 0.4834 },
      members: ["auto_ets", "auto_ces"],
      weight_on_a: 0.67,
      rule: "best two of the pool by selection WAPE",
    },
    band: {
      method: "split-conformal",
      level: 0.8,
      per_horizon_width: ACTUAL.map(() => 6),
      candidates: {
        lgbm: { pinball_p50: 2.45, pinball_p90: 1.46, coverage_80: 0.7869, mean_band_width: 12.46 },
        convex_ensemble: { pinball_p50: 2.38, pinball_p90: 1.46, coverage_80: 0.7846, mean_band_width: 11.96 },
      },
    },
  },
  catalog_rule: "test fixture",
  curve_provenance: "test fixture",
  history_days: 8,
  origins: [
    { origin: "2016-05-10", history_start: "2016-03-15", forecast_dates: ACTUAL.map((_, i) => `2016-05-${11 + i}`) },
    { origin: "2016-05-17", history_start: "2016-03-22", forecast_dates: ACTUAL.map((_, i) => `2016-05-${18 + i}`) },
  ],
  catalog: [
    {
      series_id: "FOODS_1_004_CA_1",
      store: "CA_1",
      class: "dense",
      adi: 1.16,
      cv2: 0.7,
      origins: { "2016-05-10": windowOf("weekly-peaked"), "2016-05-17": windowOf("weekly-peaked") },
    },
    {
      series_id: "FOODS_1_032_CA_1",
      store: "CA_1",
      class: "intermittent",
      adi: 1.35,
      cv2: 1.29,
      origins: { "2016-05-10": windowOf("slow-mover"), "2016-05-17": windowOf("slow-mover") },
    },
    {
      series_id: "FOODS_3_090_CA_3",
      store: "CA_3",
      class: "dense",
      adi: 1.23,
      cv2: 0.68,
      origins: { "2016-05-10": windowOf("event-driven"), "2016-05-17": windowOf("event-driven") },
    },
    {
      series_id: "FOODS_3_586_TX_2",
      store: "TX_2",
      class: "intermittent",
      adi: 1.5,
      cv2: 1.15,
      origins: { "2016-05-10": windowOf("steady"), "2016-05-17": windowOf("steady") },
    },
  ],
  evaluation_metadata: {
    protocol: "m5_direct_v1",
    dataset: { subset_rule: "fixture", observed_panel: {}, citation: "fixture" },
    split: {},
    seeds: { lgbm_random_state: 42 },
    determinism: "fixture",
  },
};

const MANIFEST = {
  id: "forecast-workbench",
  title: "demand forecast workbench",
  hook: "Pick a store-product series from the committed M5 track and compare the candidates on the scored-once test origins.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["time series forecasting"],
  modes: ["browser"],
  hero: null,
  scenarios: [
    { name: "base", controls: { models: "seasonal_naive,lgbm", origin: "2016-05-10", horizon: 28 } },
  ],
  live_endpoints: [],
  payload: { path: "reports_m5/demo_payload.json", schema_version: 4, required_keys: [] },
};

function mockFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith("/demos/forecast-workbench/manifest")) return Promise.resolve(jsonResponse(MANIFEST));
      if (url.endsWith("/demos/forecast-workbench/payload")) return Promise.resolve(jsonResponse(PAYLOAD));
      return Promise.resolve(jsonResponse({}, 404));
    }),
  );
}

function renderDemo() {
  return render(
    <MemoryRouter>
      <ForecastWorkbench />
    </MemoryRouter>,
  );
}

/** jsdom lacks ResizeObserver; keep the workbench on its static fallbacks. */
beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const lgbmPolylines = () =>
  Array.from(document.querySelectorAll('.demo-chart polyline[stroke="#2dd4bf"]'));

/** Regression guard for the NaN band geometry bug: every rendered polyline
 * and path in the chart must carry only finite coordinates (gaps are split
 * into separate runs, never interpolated as NaN). */
function expectFiniteChartGeometry() {
  const polylines = document.querySelectorAll(".demo-chart polyline");
  expect(polylines.length).toBeGreaterThan(0);
  for (const el of Array.from(polylines)) {
    expect(el.getAttribute("points")).not.toMatch(/NaN|undefined/);
  }
  for (const el of Array.from(document.querySelectorAll(".demo-chart path"))) {
    expect(el.getAttribute("d")).not.toMatch(/NaN|undefined/);
  }
}

describe("ForecastWorkbench", () => {
  it("shows a loading state then the title, hook and populated series picker", async () => {
    mockFetch();
    renderDemo();
    expect(screen.getByText("loading demo…")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "demand forecast workbench" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/compare the candidates on the scored-once test origins/i),
    ).toBeInTheDocument();
    // series picker: one chip per catalog series, grouped under store tags
    expect(screen.getByText("CA_1")).toBeInTheDocument();
    expect(screen.getByText("CA_3")).toBeInTheDocument();
    expect(screen.getByText("TX_2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /FOODS_1_004/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /FOODS_3_586/ })).toBeInTheDocument();
    // class badges on the chips
    const chip = screen.getByRole("button", { name: /FOODS_1_032/ });
    expect(chip.textContent).toContain("intermittent");
  });

  it("renders the chart and exactly three KPI tiles on the default selection", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    expect(
      screen.getByRole("img", { name: "forecast curves versus actuals for the selected series" }),
    ).toBeInTheDocument();
    const tiles = document.querySelectorAll(".wb-kpi-band .wb-kpi");
    expect(tiles).toHaveLength(3);
    expect(screen.getByText("band coverage")).toBeInTheDocument();
    expect(screen.getByText("peak-day MAE @ 28d")).toBeInTheDocument();
    // default selection: lgbm beats the naive on the fixture window; the
    // committed pooled chip is quoted at the full horizon
    const wapeTile = screen.getByText("WAPE @ 28d").closest(".wb-kpi")!;
    expect(wapeTile.textContent).toMatch(/LightGBM vs naive [\d.]+%/);
    expect(wapeTile.textContent).toMatch(/pooled −9\.1 pts committed/);
  });

  it("adds a curve when a model chip is toggled on", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    const polylinesBefore = document.querySelectorAll(".demo-chart polyline").length;
    fireEvent.click(screen.getByRole("button", { name: /ensemble/ }));
    const after = document.querySelectorAll(".demo-chart polyline").length;
    expect(after).toBe(polylinesBefore + 1);
    fireEvent.click(screen.getByRole("button", { name: /ensemble/ }));
    expect(document.querySelectorAll(".demo-chart polyline").length).toBe(polylinesBefore);
  });

  it("shortens the scored window when the horizon toggle moves", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    // lgbm curve: 28 visible window points at the full horizon
    const pointsAt = () => lgbmPolylines()[0].getAttribute("points")!.trim().split(" ").length;
    expect(pointsAt()).toBe(28);
    fireEvent.click(screen.getByRole("button", { name: "7d" }));
    expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument();
    expect(pointsAt()).toBe(7);
  });

  it("shows the honest-gap note for an intermittent series only", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    // default series is dense -> no honest-gap note
    expect(screen.queryByTestId("honest-gap")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /FOODS_1_032/ }));
    const note = screen.getByTestId("honest-gap");
    expect(note.textContent).toContain("The honest gap");
    expect(note.textContent).toContain("90.5% of intermittent series");
    // verdict notice reacts to the selection too
    expect(document.querySelector(".wb-notice")!.textContent).toContain("h = 28");
  });

  it("renders the demo at /demos/forecast-workbench inside App", async () => {
    mockFetch();
    render(
      <MemoryRouter initialEntries={["/demos/forecast-workbench"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "demand forecast workbench" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: "← back to demos" })).toHaveAttribute(
      "href",
      "/projects#demos",
    );
  });

  it("keeps every chart coordinate finite across series, origin, model and horizon changes", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    // default view: naive + LightGBM + band at the full horizon
    expect(lgbmPolylines().length).toBeGreaterThan(0);
    expect(document.querySelector(".demo-chart path[d]")).not.toBeNull();
    expectFiniteChartGeometry();
    // toggle the ensemble on (band indices shift by one)
    fireEvent.click(screen.getByRole("button", { name: /ensemble/ }));
    expectFiniteChartGeometry();
    // switch origin
    fireEvent.click(screen.getByRole("button", { name: "2016-05-17" }));
    expectFiniteChartGeometry();
    // switch to an intermittent series
    fireEvent.click(screen.getByRole("button", { name: /FOODS_1_032/ }));
    expectFiniteChartGeometry();
    // clipped-domain path: horizon 7
    fireEvent.click(screen.getByRole("button", { name: "7d" }));
    expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument();
    expectFiniteChartGeometry();
  });

  it("shows an error state when the payload cannot be loaded", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse({ detail: "no payload" }, 404))),
    );
    renderDemo();
    await waitFor(() =>
      expect(screen.getByText(/could not load the demo payload/i)).toBeInTheDocument(),
    );
  });
});
