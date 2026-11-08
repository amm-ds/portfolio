import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import ForecastWorkbench from "../demos/forecast-workbench/ForecastWorkbench";
import { ModelSpreadPanel } from "../demos/forecast-workbench/panels";
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
  lgbm_tweedie: [10.5, 11, 13.5, 13, 11.5, 10, 12.5, 14, 12.5, 11.5, 10.5, 12, 13.5, 12.5, 11.5, 10.5, 12, 13.5, 12.5, 11.5, 10.5, 12, 13.5, 12.5, 11.5, 10.5, 12, 13.5],
  lgbm_pool_store: [11, 11.5, 13.5, 13, 11, 10.5, 12.5, 13.5, 13, 11, 10.5, 12.5, 13.5, 13, 11, 10.5, 12.5, 13.5, 13, 11, 10.5, 12.5, 13.5, 13, 11, 10.5, 12.5, 13.5],
  lgbm_pool_storecat: [11.5, 12, 14, 13.5, 11.5, 11, 13, 14, 13.5, 11.5, 11, 13, 14, 13.5, 11.5, 11, 13, 14, 13.5, 11.5, 11, 13, 14, 13.5, 11.5, 11, 13, 14],
  lgbm_pool_dept: [11, 12, 14.5, 13, 11, 10.5, 12.5, 14, 13, 11, 10.5, 12.5, 14, 13, 11, 10.5, 12.5, 14, 13, 11, 10.5, 12.5, 14, 13, 11, 10.5, 12.5, 14],
  convex_ensemble: [10.8, 11.4, 13.8, 13.1, 11.2, 10.4, 12.3, 13.9, 12.9, 11.2, 10.4, 12.3, 13.8, 12.9, 11.2, 10.4, 12.3, 13.8, 12.9, 11.2, 10.4, 12.3, 13.8, 12.9, 11.2, 10.4, 12.3, 13.8],
};
const ACTUAL = [10, 12, 15, 12, 11, 9, 13, 15, 14, 11, 10, 12, 16, 15, 12, 10, 11, 14, 16, 13, 11, 10, 13, 15, 14, 12, 11, 13];
const HISTORY = [9, 10, 11, 10, 12, 13, 11, 10];

function windowOf() {
  const wape: Record<string, number> = {};
  for (const [cand, curve] of Object.entries(CURVES)) {
    const err = ACTUAL.reduce((s, a, i) => s + Math.abs(curve[i] - a), 0);
    wape[cand] = err / ACTUAL.reduce((s, a) => s + a, 0);
  }
  return {
    history: HISTORY,
    actual: ACTUAL,
    curves: CURVES,
    band: {
      lo: CURVES.convex_ensemble.map((v) => Math.max(0, v - 1)),
      hi: CURVES.convex_ensemble.map((v) => v + 1),
    },
    wape,
  };
}

/** Intermittent-series window where the flat naive curve nails the actuals —
 * the honest per-series verdict there is "the seasonal naive wins this one". */
function naiveFavorableWindow() {
  return { ...windowOf(), actual: CURVES.seasonal_naive.slice() };
}

const POOLED = {
  seasonal_naive: { wape: 0.9159, wrmsse: 0.8929, bias: -0.012, zero_day_accuracy: 0.6663, zero_day_accuracy_intermittent: 0.6782 },
  auto_ets: { wape: 0.771, wrmsse: 0.7093, bias: -0.0063, zero_day_accuracy: 0.6095, zero_day_accuracy_intermittent: 0.6242 },
  lgbm: { wape: 0.7626, wrmsse: 0.6601, bias: 0.0041, zero_day_accuracy: 0.5808, zero_day_accuracy_intermittent: 0.5966 },
  lgbm_tweedie: { wape: 0.7642, wrmsse: 0.6473, bias: 0.0122, zero_day_accuracy: 0.5659, zero_day_accuracy_intermittent: 0.5812 },
  lgbm_pool_store: { wape: 0.7641, wrmsse: 0.6217, bias: 0.0265, zero_day_accuracy: 0.5812, zero_day_accuracy_intermittent: 0.5969 },
  lgbm_pool_storecat: { wape: 0.7674, wrmsse: 0.6575, bias: 0.0482, zero_day_accuracy: 0.5708, zero_day_accuracy_intermittent: 0.5862 },
  lgbm_pool_dept: { wape: 0.7608, wrmsse: 0.6313, bias: 0.0041, zero_day_accuracy: 0.5802, zero_day_accuracy_intermittent: 0.596 },
  convex_ensemble: { wape: 0.7633, wrmsse: 0.6161, bias: 0.0328, zero_day_accuracy: 0.5734, zero_day_accuracy_intermittent: 0.589 },
};

/** 4-series fixture: 2 stores × (top-units + hardest-intermittent), one
 * scored-once origin, the 8 full-panel candidates. */
const PAYLOAD: ForecastWorkbenchPayload = {
  schema_version: 4,
  demo: "forecast-workbench",
  project: "02-demand-forecasting",
  protocol: "m5_full_v1",
  groups: {
    headline: {
      metric: "official_wrmsse",
      champion: "convex_ensemble",
      champion_wrmsse: 0.6161,
      wrmsse_champion: { candidate: "convex_ensemble", wrmsse: 0.6161 },
      absolute_ensemble_wrmsse: 0.6161,
      convex_ensemble_vs_naive: {
        wrmsse: { diff: -0.2768, rel: -0.31, ci95: null, spans_zero: null, note: "fixture" },
      },
    },
    test_pooled: POOLED,
    test_by_class: {},
    win_rate_vs_naive: {
      convex_ensemble: { pooled: 0.5625, dense: 1.0, intermittent: 0.4 },
    },
    stability: { convex_ensemble: 0.0001 },
    classes: { counts: { dense: 2754, intermittent: 27736 }, thresholds: { adi: 1.32, cv2: 0.49 } },
    ensemble: {
      pool: ["lgbm", "lgbm_tweedie", "lgbm_pool_store", "lgbm_pool_storecat", "lgbm_pool_dept", "auto_ets"],
      selection_screen: {
        lgbm_pool_storecat: { mean: 0.6049, std: 0.0179, score: 0.6228 },
        lgbm_pool_store: { mean: 0.6187, std: 0.0126, score: 0.6313 },
        lgbm_pool_dept: { mean: 0.6436, std: 0.0214, score: 0.6651 },
      },
      members: ["lgbm_pool_storecat", "lgbm_pool_store", "lgbm_pool_dept"],
      weights: [0.6, 0.1, 0.3],
      rule: "fixture",
    },
    band: {
      method: "member envelope (min/max), not a calibrated interval",
      level: null,
      per_horizon_width: ACTUAL.map(() => 1.6),
      per_horizon_coverage: ACTUAL.map(() => 0.05),
      candidates: { convex_ensemble: { mean_width: 1.6 } },
    },
    _scope: { test_by_class: "catalog", win_rate_vs_naive: "catalog" },
  },
  catalog_rule: "test fixture",
  curve_provenance: "test fixture",
  history_days: 8,
  origins: [
    {
      origin: "2016-05-22",
      history_start: "2016-03-28",
      forecast_dates: ACTUAL.map((_, i) => {
        const d = new Date(Date.UTC(2016, 4, 23 + i));
        return d.toISOString().slice(0, 10);
      }),
    },
  ],
  catalog: [
    {
      series_id: "FOODS_1_004_CA_1",
      store: "CA_1",
      class: "dense",
      adi: 1.16,
      cv2: 0.7,
      units_last_28d: 350,
      half: "top_units",
      windows: windowOf(),
    },
    {
      series_id: "FOODS_1_032_CA_1",
      store: "CA_1",
      class: "intermittent",
      adi: 3.2,
      cv2: 4.1,
      units_last_28d: 2,
      half: "bottom_intermittency",
      windows: naiveFavorableWindow(),
    },
    {
      series_id: "HOUSEHOLD_1_110_TX_2",
      store: "TX_2",
      class: "dense",
      adi: 1.1,
      cv2: 0.4,
      units_last_28d: 408,
      half: "top_units",
      windows: windowOf(),
    },
    {
      series_id: "HOBBIES_1_052_TX_2",
      store: "TX_2",
      class: "intermittent",
      adi: 2.9,
      cv2: 3.3,
      units_last_28d: 1,
      half: "bottom_intermittency",
      windows: naiveFavorableWindow(),
    },
  ],
  evaluation_metadata: {
    protocol: "m5_full_v1",
    dataset: { dataset: "fixture", observed_panel: {}, citation: "fixture" },
    split: {},
    seeds: { lgbm_random_state: 42 },
  },
};

const MANIFEST = {
  id: "forecast-workbench",
  title: "Demand Forecast Workbench",
  hook: "Pick a committed M5 store-product series and compare the candidates on the scored-once competition window.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["time series forecasting"],
  modes: ["browser"],
  hero: null,
  scenarios: [{ name: "base", controls: { models: "seasonal_naive,lgbm", horizon: 28 } }],
  live_endpoints: [],
  payload: { path: "reports_m5_full/demo_payload.json", schema_version: 4, required_keys: [] },
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
  Array.from(document.querySelectorAll(".demo-chart polyline")).filter(
    (el) => (el as SVGPolylineElement).style.stroke === "var(--chart-teal)",
  );

const peaksAt = (card: Element) =>
  Array.from(card.querySelectorAll(".fwb-verdict-peak")).map((e) => e.textContent);

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
        screen.getByRole("heading", { level: 1, name: "Demand Forecast Workbench" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/compare the candidates on the scored-once competition window/i),
    ).toBeInTheDocument();
    // series picker: one chip per catalog series, grouped under store tags
    expect(screen.getByText("CA_1")).toBeInTheDocument();
    expect(screen.getByText("TX_2")).toBeInTheDocument();
    // halves sub-group the chips inside each store
    expect(screen.getAllByText("top units").length).toBe(2);
    expect(screen.getAllByText("hardest intermittent").length).toBe(2);
    expect(screen.getByRole("button", { name: /FOODS_1_004/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /HOUSEHOLD_1_110/ })).toBeInTheDocument();
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
    expect(screen.getByText("official WRMSSE")).toBeInTheDocument();
    expect(screen.getByText("zero-day accuracy")).toBeInTheDocument();
    // the demo opens on the full scored window (h=28) with every candidate
    // selected; LightGBM leads the fixture window
    const wapeTile = screen.getByText("WAPE @ 28d").closest(".wb-kpi")!;
    expect(wapeTile.textContent).toMatch(/LightGBM vs naive [\d.]+%/);
    // the committed pooled chip is quoted at the full scored horizon (the
    // fixture's per-series winner is LightGBM → its committed pooled WRMSSE gap)
    expect(wapeTile.textContent).toMatch(/pooled WRMSSE −0\.2328 committed/);
    fireEvent.click(screen.getByRole("button", { name: "7d" }));
    expect(screen.getByText("WAPE @ 7d").closest(".wb-kpi")!.textContent).not.toMatch(/committed/);
    // the headline tile carries the committed scored-once numbers
    const wrmsseTile = screen.getByText("official WRMSSE").closest(".wb-kpi")!;
    expect(wrmsseTile.textContent).toContain("0.6161");
    expect(wrmsseTile.textContent).toContain("0.8929");
    const zeroTile = screen.getByText("zero-day accuracy").closest(".wb-kpi")!;
    expect(zeroTile.textContent).toMatch(/57\.3%/);
    expect(zeroTile.textContent).toMatch(/66\.6%/);
  });

  it("opens with horizon 28d and every model chip selected", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    expect(
      (screen.getByRole("button", { name: "28d" }) as HTMLButtonElement).getAttribute("aria-pressed"),
    ).toBe("true");
    for (const name of [
      "seasonal naive",
      "AutoETS",
      "LightGBM",
      "LightGBM tweedie",
      "pooled store",
      "pooled store×cat",
      "pooled dept",
      "ensemble",
    ]) {
      const chip = screen.getByRole("button", { name });
      expect(chip.getAttribute("aria-pressed"), name).toBe("true");
    }
    // the pooled chips carry their grouping tooltips
    expect(screen.getByRole("button", { name: "pooled store" }).getAttribute("title")).toBe(
      "one LightGBM fit per store (10 groups)",
    );
    expect(
      screen.getByRole("button", { name: "pooled store×cat" }).getAttribute("title"),
    ).toBe("one LightGBM fit per store×category cell (30 groups)");
  });

  it("removes a curve when a model chip is toggled off and restores it on re-toggle", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    const polylinesBefore = document.querySelectorAll(".demo-chart polyline").length;
    fireEvent.click(screen.getByRole("button", { name: "ensemble" }));
    const after = document.querySelectorAll(".demo-chart polyline").length;
    // the ensemble curve plus its two envelope edges leave the chart
    expect(after).toBe(polylinesBefore - 3);
    fireEvent.click(screen.getByRole("button", { name: "ensemble" }));
    expect(document.querySelectorAll(".demo-chart polyline").length).toBe(polylinesBefore);
  });

  it("rescales the scored window when the horizon toggle moves", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    // default: full scored window — 28 visible window points on the lgbm curve
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
    expect(note.textContent).toContain("40.0% of intermittent series");
    expect(note.textContent).toContain("not a calibrated interval");
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
        screen.getByRole("heading", { level: 1, name: "Demand Forecast Workbench" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: "← back to demos" })).toHaveAttribute(
      "href",
      "/projects#demos",
    );
  });

  it("keeps every chart coordinate finite across series, model and horizon changes", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    // default view: every candidate + envelope on the full scored window
    expect(lgbmPolylines().length).toBeGreaterThan(0);
    expect(document.querySelector(".demo-chart path[d]")).not.toBeNull();
    expectFiniteChartGeometry();
    // toggle the ensemble off (envelope indices shift by two)
    fireEvent.click(screen.getByRole("button", { name: "ensemble" }));
    expectFiniteChartGeometry();
    // switch to an intermittent series
    fireEvent.click(screen.getByRole("button", { name: /FOODS_1_032/ }));
    expectFiniteChartGeometry();
    // next-week window
    fireEvent.click(screen.getByRole("button", { name: "7d" }));
    expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument();
    expectFiniteChartGeometry();
  });

  it("renders three dynamic cards below the chart that update with the horizon toggle", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    // the churn-style card row sits in the secondary band under the chart
    expect(screen.getByText("error composition")).toBeInTheDocument();
    expect(screen.getByText("model spread")).toBeInTheDocument();
    expect(screen.getByText("model verdict")).toBeInTheDocument();
    expect(document.querySelectorAll(".wb-secondary .figure-card")).toHaveLength(3);

    const errCard = () =>
      screen.getByText("error composition").closest(".wb-secondary-panel")!;
    const spreadCard = () => screen.getByText("model spread").closest(".wb-secondary-panel")!;
    // full-horizon headlines (the demo opens at h=28 with every candidate on)
    expect(errCard().textContent).toMatch(/wape @28d 0\.\d{3}/);
    expect(spreadCard().textContent).toMatch(/8 models/);
    const errBefore = errCard().textContent;
    // next-week window: every card recomputes client-side
    fireEvent.click(screen.getByRole("button", { name: "7d" }));
    expect(errCard().textContent).toMatch(/wape @7d 0\.\d{3}/);
    expect(errCard().textContent).not.toBe(errBefore);
    expect(spreadCard().textContent).toMatch(/mean spread [\d.]+/);
    expect(
      screen.getByText("model verdict").closest(".wb-secondary-panel")!.textContent,
    ).toMatch(/h = 7/);
  });

  it("keeps the spread card live for any selection — a band across models, recomputed when the ensemble toggles off", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    const spreadCard = () => screen.getByText("model spread").closest(".wb-secondary-panel")!;
    // default: every candidate — a disagreement band with a closest-model chip
    expect(spreadCard().textContent).toMatch(/8 models/);
    expect(spreadCard().textContent).toMatch(/closest/);
    expect(spreadCard().textContent).toMatch(/not a calibrated interval/);
    // deselecting the ensemble does NOT collapse the card — it recomputes
    fireEvent.click(screen.getByRole("button", { name: "ensemble" }));
    expect(spreadCard().textContent).toMatch(/7 models/);
    expect(spreadCard().querySelector(".state-box")).toBeNull();
    const before = spreadCard().textContent;
    fireEvent.click(screen.getByRole("button", { name: "ensemble" }));
    expect(spreadCard().textContent).not.toBe(before);
  });

  it("names the seasonal naive as the honest per-series winner on the intermittent series", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /FOODS_1_032/ }));
    const verdictCard = screen.getByText("model verdict").closest(".wb-secondary-panel")!;
    expect(verdictCard.textContent).toContain("seasonal naive wins this window");
    expect(verdictCard.textContent).toContain("40.0% of intermittent series");
    // the naive row carries the best highlight
    const bestRow = verdictCard.querySelector(".fwb-verdict-item.best")!;
    expect(bestRow.textContent).toContain("seasonal naive");
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

  it("renders the model spread card as a per-day disagreement band over the visible horizon, recomputing at 28/14/7", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    const spreadCard = () => screen.getByText("model spread").closest(".wb-secondary-panel")!;
    // band polygon + actuals line + readout chips, honest footer
    expect(spreadCard().querySelectorAll("svg path[d]")).not.toHaveLength(0);
    expect(spreadCard().textContent).toMatch(/mean spread [\d.]+/);
    expect(spreadCard().textContent).toMatch(/widest/);
    expect(spreadCard().textContent).toMatch(/closest/);
    const comment = spreadCard().querySelector(".figure-comment")!.textContent!;
    expect(comment).toContain("disagree");
    expect(comment).toContain("not a calibrated interval");
    // horizon toggle recomputes the band and the footer
    fireEvent.click(screen.getByRole("button", { name: "7d" }));
    expect(spreadCard().textContent).toMatch(/8 models/);
    expect(spreadCard().textContent).toMatch(/mean spread [\d.]+/);
    // the band never dead-ends: it is present at every shipped horizon
    for (const horizon of ["14d", "28d"]) {
      fireEvent.click(screen.getByRole("button", { name: horizon }));
      expect(spreadCard().querySelectorAll("svg path[d]")).not.toHaveLength(0);
      expect(spreadCard().textContent).toMatch(/mean spread [\d.]+/);
    }
  });

  it("switches the spread card to per-day error bars when a single model is selected", () => {
    const windowFixture = {
      history: [1, 2],
      actual: [10, 12, 11, 13],
      curves: { seasonal_naive: [9, 12, 10, 14] },
      band: { lo: [9, 12, 10, 14], hi: [9, 12, 10, 14] },
      wape: {},
    };
    render(
      <ModelSpreadPanel
        window={windowFixture as never}
        modelsOn={["seasonal_naive"]}
        h={4}
        forecastDates={["2016-05-23", "2016-05-24", "2016-05-25", "2016-05-26"]}
      />,
    );
    // one model cannot disagree with itself: |error| view, band gone
    expect(screen.getByText(/1 model — \|error\| view/)).toBeInTheDocument();
    expect(screen.getByText(/mean \|err\| [\d.]+/)).toBeInTheDocument();
    expect(screen.getByText(/seasonal naive is visible|Only seasonal naive/)).toBeInTheDocument();
  });

  it("renders the verdict card as ordered horizontal WAPE bars — naive grey reference, best crowned, fixed scale label — and keeps bar widths pinned when models toggle", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    const verdictCard = () => screen.getByText("model verdict").closest(".wb-secondary-panel")!;
    // default selection: every candidate -> one bar per model
    const items = verdictCard().querySelectorAll(".fwb-verdict-item");
    expect(items).toHaveLength(8);
    for (const item of Array.from(items)) {
      // dot + name + tinted bar fill + value label at the bar end + peak-day MAE
      expect(item.querySelector(".fwb-dot")).not.toBeNull();
      expect(item.querySelector(".fwb-verdict-name")!.textContent).toMatch(
        /seasonal naive|AutoETS|LightGBM|tweedie|pooled|ensemble/,
      );
      expect(item.querySelector(".fwb-bar-fill")).not.toBeNull();
      expect(item.querySelector(".fwb-bar-value")!.textContent).toMatch(/^\d+\.\d{3}$/);
      expect(item.querySelector(".fwb-verdict-peak")!.textContent).toMatch(/^\d+\.\d$/);
      // the removed extras stay gone: no delta chips, micro-bars, weekstrip
      expect(item.querySelector(".chip")).toBeNull();
      expect(item.querySelector(".fwb-microbars")).toBeNull();
      expect(item.querySelector(".fwb-verdict-share")).toBeNull();
    }
    expect(verdictCard().querySelector(".fwb-verdict-head")).toBeNull();
    expect(verdictCard().querySelector(".fwb-weekstrip")).toBeNull();
    // bars share one FIXED scale and are ordered best-first (ascending WAPE)
    const values = () =>
      Array.from(verdictCard().querySelectorAll(".fwb-bar-value")).map((e) => Number(e.textContent));
    const fills = () => Array.from(verdictCard().querySelectorAll<HTMLElement>(".fwb-bar-fill"));
    const vals = values();
    for (let i = 1; i < vals.length; i++) {
      expect(vals[i]).toBeGreaterThanOrEqual(vals[i - 1]);
    }
    expect(fills()[0].style.width).not.toBe("");
    // the naive is the grey reference bar
    const naiveItem = Array.from(items).find((i) =>
      i.querySelector(".fwb-verdict-name")!.textContent!.includes("seasonal naive"),
    )!;
    expect((naiveItem.querySelector(".fwb-bar-fill") as HTMLElement).style.backgroundColor).toBe(
      "var(--chart-gray)",
    );
    // the best bar carries the crown
    expect(verdictCard().querySelector(".fwb-verdict-item.best .fwb-verdict-crown")).not.toBeNull();
    // the fixed common scale: printed axis label, derived from every payload
    // candidate, not the selected subset
    const scaleLabel = () => verdictCard().querySelector(".fwb-verdict-scale")!;
    expect(scaleLabel().textContent).toMatch(/wape@28d scale max 0\.\d{3} · 8 candidates/);
    const scaleBefore = scaleLabel().textContent;

    // toggle a subset OFF: another bar's width must be pixel-identical and
    // the scale label must persist unchanged
    const lightgbmRow = () =>
      Array.from(verdictCard().querySelectorAll(".fwb-verdict-item")).find((i) =>
        i.querySelector(".fwb-verdict-name")!.textContent!.includes("LightGBM"),
      )!;
    const widthBefore = (lightgbmRow().querySelector(".fwb-bar-fill") as HTMLElement).style.width;
    fireEvent.click(screen.getByRole("button", { name: "AutoETS" }));
    fireEvent.click(screen.getByRole("button", { name: "ensemble" }));
    expect(verdictCard().querySelectorAll(".fwb-verdict-item")).toHaveLength(6);
    expect((lightgbmRow().querySelector(".fwb-bar-fill") as HTMLElement).style.width).toBe(widthBefore);
    expect(scaleLabel().textContent).toBe(scaleBefore);
    // toggling back restores the full set at the same widths
    fireEvent.click(screen.getByRole("button", { name: "AutoETS" }));
    fireEvent.click(screen.getByRole("button", { name: "ensemble" }));
    expect(verdictCard().querySelectorAll(".fwb-verdict-item")).toHaveLength(8);
    expect((lightgbmRow().querySelector(".fwb-bar-fill") as HTMLElement).style.width).toBe(widthBefore);

    // bars and peak-day MAEs change with the horizon toggle
    const before = { vals: values(), peaks: peaksAt(verdictCard()) };
    fireEvent.click(screen.getByRole("button", { name: "7d" }));
    expect(values()).not.toEqual(before.vals);
    expect(peaksAt(verdictCard())).not.toEqual(before.peaks);
    // below the full scored horizon the committed pooled chip is not quoted
    expect(verdictCard().textContent).not.toMatch(/WRMSSE [−+][\d.]+ committed/);
    // …but the fixed-scale label follows the horizon
    expect(verdictCard().querySelector(".fwb-verdict-scale")!.textContent).toMatch(
      /wape@7d scale max 0\.\d{3}/,
    );
    // back at h=28 the pooled committed chip reappears
    fireEvent.click(screen.getByRole("button", { name: "28d" }));
    expect(verdictCard().textContent).toMatch(/pooled official WRMSSE −0\.2328 committed/);
    expect(verdictCard().textContent).toMatch(/h = 28/);
  });

  it("derives evidence and the chart origin label from the payload", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());

    const evidence = document.querySelector(".wb-evidence")!;
    expect(evidence.textContent).toContain(
      "ensemble 0.6161 vs the seasonal-naive floor 0.8929 (gap −31.0%)",
    );
    expect(evidence.textContent).toContain("scored once on the competition window (2016-05-22 →");
    expect(evidence.textContent).toContain("2,754 dense + 27,736 intermittent series, 8 candidates");
    expect(document.querySelector(".wb-canvas-slot .figure-comment")!.textContent).toContain(
      "from origin 2016-05-22",
    );
    // single-origin catalog: no origin chips anywhere
    expect(screen.queryByRole("button", { name: "2016-05-08" })).toBeNull();
  });

  it("pins the series picker controls above a scrollable store list", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument());
    const group = document.querySelector(".wb-group-series")!;
    // prev/next/surprise stay pinned at the top of the selector…
    const readouts = group.querySelector(".demo-readouts")!;
    expect(readouts.textContent).toMatch(/prev/);
    expect(readouts.textContent).toMatch(/next/);
    expect(readouts.textContent).toMatch(/surprise me/);
    // …outside the scroll region that holds the store-grouped chips
    const scroll = group.querySelector(".fwb-store-scroll")!;
    expect(scroll).not.toBeNull();
    expect(scroll.contains(readouts)).toBe(false);
    expect(scroll.querySelectorAll(".chip.demo-preset")).toHaveLength(4);
    // the scroll region is capped (max-height) so a long list cannot push
    // the layout — the rail and chart keep the churn demo's proportions
    expect(scroll.classList.contains("fwb-store-scroll")).toBe(true);
  });
});
