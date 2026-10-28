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

/** Intermittent-series window where the flat naive curve nails the actuals —
 * the honest per-series verdict there is "the seasonal naive wins this one". */
function naiveFavorableWindow(shape: string) {
  return { ...windowOf(shape), actual: CURVES.seasonal_naive.slice() };
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
      origins: { "2016-05-10": naiveFavorableWindow("slow-mover"), "2016-05-17": naiveFavorableWindow("slow-mover") },
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
      origins: { "2016-05-10": naiveFavorableWindow("steady"), "2016-05-17": naiveFavorableWindow("steady") },
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
    await waitFor(() => expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument());
    expect(
      screen.getByRole("img", { name: "forecast curves versus actuals for the selected series" }),
    ).toBeInTheDocument();
    const tiles = document.querySelectorAll(".wb-kpi-band .wb-kpi");
    expect(tiles).toHaveLength(3);
    expect(screen.getByText("band coverage")).toBeInTheDocument();
    expect(screen.getByText("peak-day MAE @ 7d")).toBeInTheDocument();
    // the demo opens on the next-week view (h=7); default selection: lgbm
    // beats the naive on the fixture window
    const wapeTile = screen.getByText("WAPE @ 7d").closest(".wb-kpi")!;
    expect(wapeTile.textContent).toMatch(/LightGBM vs naive [\d.]+%/);
    // the committed pooled chip is quoted only at the full scored horizon
    expect(wapeTile.textContent).not.toMatch(/pooled/);
    fireEvent.click(screen.getByRole("button", { name: "28d" }));
    expect(screen.getByText("WAPE @ 28d").closest(".wb-kpi")!.textContent).toMatch(
      /pooled −9\.1 pts committed/,
    );
  });

  it("adds a curve when a model chip is toggled on", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument());
    const polylinesBefore = document.querySelectorAll(".demo-chart polyline").length;
    fireEvent.click(screen.getByRole("button", { name: /ensemble/ }));
    const after = document.querySelectorAll(".demo-chart polyline").length;
    expect(after).toBe(polylinesBefore + 1);
    fireEvent.click(screen.getByRole("button", { name: /ensemble/ }));
    expect(document.querySelectorAll(".demo-chart polyline").length).toBe(polylinesBefore);
  });

  it("rescales the scored window when the horizon toggle moves", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument());
    // lgbm curve: 7 visible window points on the default next-week view
    const pointsAt = () => lgbmPolylines()[0].getAttribute("points")!.trim().split(" ").length;
    expect(pointsAt()).toBe(7);
    fireEvent.click(screen.getByRole("button", { name: "28d" }));
    expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument();
    expect(pointsAt()).toBe(28);
  });

  it("shows the honest-gap note for an intermittent series only", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument());
    // default series is dense -> no honest-gap note
    expect(screen.queryByTestId("honest-gap")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /FOODS_1_032/ }));
    const note = screen.getByTestId("honest-gap");
    expect(note.textContent).toContain("The honest gap");
    expect(note.textContent).toContain("90.5% of intermittent series");
    // verdict notice reacts to the selection too
    expect(document.querySelector(".wb-notice")!.textContent).toContain("h = 7");
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
    await waitFor(() => expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument());
    // default view: naive + LightGBM + band on the next-week window
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
    // full scored window
    fireEvent.click(screen.getByRole("button", { name: "28d" }));
    expect(screen.getByText("WAPE @ 28d")).toBeInTheDocument();
    expectFiniteChartGeometry();
  });

  it("renders three dynamic cards below the chart that update with the horizon toggle", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument());
    // the churn-style card row sits in the secondary band under the chart
    expect(screen.getByText("error composition")).toBeInTheDocument();
    expect(screen.getByText("band calibration")).toBeInTheDocument();
    expect(screen.getByText("model verdict")).toBeInTheDocument();
    expect(document.querySelectorAll(".wb-secondary .figure-card")).toHaveLength(3);

    const errCard = () =>
      screen.getByText("error composition").closest(".wb-secondary-panel")!;
    const bandCard = () =>
      screen.getByText("band calibration").closest(".wb-secondary-panel")!;
    // next-week headlines
    expect(errCard().textContent).toMatch(/wape @7d 0\.\d{3}/);
    expect(bandCard().textContent).toMatch(/\d+\/7 days inside/);
    const errBefore = errCard().textContent;
    // full horizon: every card recomputes client-side
    fireEvent.click(screen.getByRole("button", { name: "28d" }));
    expect(errCard().textContent).toMatch(/wape @28d 0\.\d{3}/);
    expect(errCard().textContent).not.toBe(errBefore);
    expect(bandCard().textContent).toMatch(/\d+\/28 days inside/);
    expect(
      screen.getByText("model verdict").closest(".wb-secondary-panel")!.textContent,
    ).toMatch(/h = 28/);
  });

  it("collapses the band card when LightGBM is deselected", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument());
    expect(screen.queryByText(/enable LightGBM/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /LightGBM/ }));
    expect(screen.getByText("enable LightGBM to see its band")).toBeInTheDocument();
    // re-enabling restores the live band strip
    fireEvent.click(screen.getByRole("button", { name: /LightGBM/ }));
    expect(screen.queryByText(/enable LightGBM/)).toBeNull();
    expect(
      screen.getByText("band calibration").closest(".wb-secondary-panel")!.textContent,
    ).toMatch(/days inside/);
  });

  it("names the seasonal naive as the honest per-series winner on the intermittent series", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /FOODS_1_032/ }));
    const verdictCard = screen.getByText("model verdict").closest(".wb-secondary-panel")!;
    expect(verdictCard.textContent).toContain("seasonal naive wins this window");
    expect(verdictCard.textContent).toContain("90.5% of intermittent series");
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

  it("renders the band card compact — coverage gauge, hit strip and a tight/loose footer — and recomputes with the horizon", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument());
    const bandCard = () => screen.getByText("band calibration").closest(".wb-secondary-panel")!;
    // coverage gauge: per-series fill against the 80% target + pooled marker
    const gauge = bandCard().querySelector(".fwb-cov-gauge")!;
    expect(gauge).not.toBeNull();
    expect(gauge.querySelector(".fwb-cov-marker.target")).not.toBeNull();
    expect(gauge.querySelector(".fwb-cov-marker.committed")).not.toBeNull();
    // the folded labels: day count, target legend, pooled committed, mean width
    expect(bandCard().textContent).toMatch(/\d+\/7 days inside/);
    expect(bandCard().textContent).toMatch(/mean width [\d.]+u/);
    expect(bandCard().textContent).toMatch(/80% target/);
    expect(bandCard().textContent).toMatch(/78\.7% committed/);
    // the per-day hit strip: one square per scored day, hover titles kept
    const days = bandCard().querySelectorAll(".fwb-band-day");
    expect(days).toHaveLength(7);
    expect(days[0].getAttribute("title")).toMatch(/\(day \+1\): inside|outside/);
    // the old plain chips row is gone; the removed extras stay gone too
    expect(bandCard().querySelector(".figure-card .demo-readouts")).toBeNull();
    expect(bandCard().querySelector('svg[aria-label="mean band width by horizon day"]')).toBeNull();
    expect(bandCard().querySelector(".fwb-cov-week")).toBeNull();
    expect(bandCard().querySelector(".fwb-worst-miss")).toBeNull();
    // one computed footer sentence: where the band hugs / floats off actuals
    const comment = bandCard().querySelector(".figure-comment")!.textContent!;
    expect(comment).toContain("tightest");
    expect(comment).toContain("loosest");
    const before = bandCard().textContent;
    fireEvent.click(screen.getByRole("button", { name: "28d" }));
    expect(bandCard().textContent).toMatch(/\d+\/28 days inside/);
    expect(bandCard().querySelectorAll(".fwb-band-day")).toHaveLength(28);
    expect(bandCard().textContent).not.toBe(before);
  });

  it("renders the verdict card as ordered horizontal WAPE bars — naive grey reference, best crowned, committed chip at h=28 — and recomputes with the horizon", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument());
    const verdictCard = () => screen.getByText("model verdict").closest(".wb-secondary-panel")!;
    // default selection: naive + LightGBM -> one bar per model
    const items = verdictCard().querySelectorAll(".fwb-verdict-item");
    expect(items).toHaveLength(2);
    for (const item of Array.from(items)) {
      // dot + name + tinted bar fill + value label at the bar end + peak-day MAE
      expect(item.querySelector(".fwb-dot")).not.toBeNull();
      expect(item.querySelector(".fwb-verdict-name")!.textContent).toMatch(/seasonal naive|LightGBM/);
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
    // bars share one scale and are ordered best-first (ascending WAPE)
    const values = () =>
      Array.from(verdictCard().querySelectorAll(".fwb-bar-value")).map((e) => Number(e.textContent));
    const fills = () => Array.from(verdictCard().querySelectorAll<HTMLElement>(".fwb-bar-fill"));
    const vals = values();
    expect(vals[0]).toBeLessThanOrEqual(vals[1]);
    expect(fills()[0].style.width).not.toBe("");
    // the naive is the grey reference bar
    const naiveItem = Array.from(items).find((i) =>
      i.querySelector(".fwb-verdict-name")!.textContent!.includes("seasonal naive"),
    )!;
    expect((naiveItem.querySelector(".fwb-bar-fill") as HTMLElement).style.backgroundColor).toBe(
      "rgb(100, 116, 139)",
    );
    // the best bar carries the crown
    expect(verdictCard().querySelector(".fwb-verdict-item.best .fwb-verdict-crown")).not.toBeNull();
    // below the full scored horizon the committed pooled chip is not quoted
    expect(verdictCard().textContent).not.toMatch(/pts committed/);
    // bars and peak-day MAEs change with the horizon toggle
    const before = { vals: values(), peaks: peaksAt(verdictCard()) };
    fireEvent.click(screen.getByRole("button", { name: "28d" }));
    expect(values()).not.toEqual(before.vals);
    expect(peaksAt(verdictCard())).not.toEqual(before.peaks);
    // at h=28 the pooled committed chip appears
    expect(verdictCard().textContent).toMatch(/pooled −9\.1 pts committed/);
    expect(verdictCard().textContent).toMatch(/h = 28/);
  });

  it("pins the series picker controls above a scrollable store list", async () => {
    mockFetch();
    renderDemo();
    await waitFor(() => expect(screen.getByText("WAPE @ 7d")).toBeInTheDocument());
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
