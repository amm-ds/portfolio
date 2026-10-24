import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import ForecastWorkbench from "../demos/forecast-workbench/ForecastWorkbench";
import type { CatalogSeries, ForecastPayload, OriginBlock } from "../demos/types";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** N days ending on `end` (inclusive), contiguous. */
function dateRange(end: string, n: number): string[] {
  const iso = (x: number) => String(x).padStart(2, "0");
  const d = new Date(`${end}T00:00:00`);
  const out: string[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const t = new Date(d);
    t.setDate(t.getDate() - i);
    out.push(`${t.getFullYear()}-${iso(t.getMonth() + 1)}-${iso(t.getDate())}`);
  }
  return out;
}

const ORIGIN_SPECS = {
  // history ends Saturday 2010-12-11, window 2010-12-12..25 (14 days)
  test: { origin: "2010-12-11", histN: 20, actual: 30, champion: 50, naive: 55, scale: 2 },
  // history ends Saturday 2010-06-05, window 2010-06-06..19
  early: { origin: "2010-06-05", histN: 20, actual: 40, champion: 60, naive: 70, scale: 4 },
  middle: { origin: "2010-09-04", histN: 20, actual: 30, champion: 45, naive: 50, scale: 1 },
} as const;
type OriginName = keyof typeof ORIGIN_SPECS;

const f14 = (fn: (i: number) => number) => Array.from({ length: 14 }, (_, i) => fn(i));

function makeOrigin(name: OriginName, over: Partial<OriginBlock> = {}): OriginBlock {
  const spec = ORIGIN_SPECS[name];
  const histDates = dateRange(spec.origin, spec.histN);
  const winStart =
    name === "test" ? "2010-12-12" : name === "early" ? "2010-06-06" : "2010-09-05";
  const actuals = dateRange(winStart, 14);
  const championMae = name === "test" ? 5 : name === "early" ? 10 : 4;
  const naiveMae = name === "test" ? 7 : name === "early" ? 11 : 8;
  const championMase = spec.scale > 0 ? championMae / spec.scale : null;
  const naiveMase = spec.scale > 0 ? naiveMae / spec.scale : null;
  return {
    origin_date: spec.origin,
    history: {
      dates: histDates,
      y: Array.from({ length: spec.histN }, (_, i) => i + 1),
    },
    actuals: { dates: actuals, y: Array.from({ length: 14 }, () => spec.actual) },
    scale: spec.scale,
    models: {
      champion: {
        y_pred: f14((i) => spec.champion + i),
        p10: f14((i) => spec.champion - 10 + i),
        p90: f14((i) => spec.champion + 10 + i),
        mae: championMae,
        mase: championMase,
        bias: 1,
        wape: 0.2,
      },
      challenger: {
        y_pred: f14((i) => spec.champion + 2 + i),
        mae: championMae + 1,
        mase: championMase === null ? null : championMase + 0.1,
        bias: -1,
        wape: 0.25,
      },
      naive: {
        y_pred: f14((i) => spec.naive + i),
        mae: naiveMae,
        mase: naiveMase,
        bias: 2,
        wape: 0.3,
      },
    },
    ...over,
  };
}

/** Zero-scale sparse origin: MASE undefined everywhere, zero errors. */
function makeSparseOrigin(name: OriginName): OriginBlock {
  const base = makeOrigin(name);
  return {
    ...base,
    scale: 0,
    actuals: { dates: base.actuals.dates, y: Array.from({ length: 14 }, () => 0) },
    models: {
      champion: { ...base.models.champion, y_pred: f14(() => 0), mae: 0, mase: null, bias: 0, wape: null },
      challenger: { ...base.models.challenger, y_pred: f14(() => 0), mae: 0, mase: null, bias: 0, wape: null },
      naive: { ...base.models.naive, y_pred: f14(() => 0), mae: 0, mase: null, bias: 0, wape: null },
    },
  };
}

function makeSeries(over: Partial<CatalogSeries> = {}): CatalogSeries {
  const test = makeOrigin("test");
  return {
    series_id: "United Kingdom|85123A",
    label: "United Kingdom · 85123A",
    demand_class: "smooth",
    history: {
      dates: dateRange("2010-12-25", 20),
      y: Array.from({ length: 20 }, (_, i) => i + 1),
    },
    forecast: {
      dates: test.actuals.dates,
      y_pred: test.models.champion.y_pred,
      p10: test.models.champion.p10!,
      p90: test.models.champion.p90!,
      naive: test.models.naive.y_pred,
    },
    errors: {
      scale: 2,
      champion: { mae: f14(() => 5), mase: f14(() => 0.8) },
      naive: { mae: f14(() => 7), mase: f14(() => 1.2) },
    },
    origins: {
      early: makeOrigin("early"),
      middle: makeOrigin("middle"),
      test,
    },
    ...over,
  };
}

const SMOOTH = makeSeries({});
const INTERMITTENT = makeSeries({
  series_id: "France|85123A",
  label: "France · 85123A",
  demand_class: "intermittent",
});
const SPARSE = makeSeries({
  series_id: "Denmark|37410",
  label: "Denmark · 37410",
  demand_class: "sparse",
  origins: {
    early: makeSparseOrigin("early"),
    middle: makeSparseOrigin("middle"),
    test: makeSparseOrigin("test"),
  },
});

const PAYLOAD: ForecastPayload = {
  schema_version: 2,
  demo: "forecast-workbench",
  project: "02-demand-forecasting",
  track: "uci",
  catalog: [SMOOTH, INTERMITTENT, SPARSE],
  scalars: {
    headline: {
      claim:
        "no run dips below MASE 1.0 on the frozen test window (the naive floor itself scores 1.310 there — the scale is its in-sample error from a quieter period); lgbm_tuned is closest at MASE 1.076",
      champion: "hgb_tuned",
      challenger: "hgb",
      champion_mase: 1.0784,
      champion_mae: 9.545,
      naive_mase: 1.3096,
      strongest_naive: "seasonal_naive",
      strongest_naive_mae: 11.323,
      champion_mae_edge_vs_strongest_naive_pct: 15.7,
      only_champion_below_mase_1: false,
      runs_below_mase_1: [],
      mase_by_model: {
        seasonal_naive: 1.3096,
        hgb_tuned: 1.0784,
        hgb: 1.11,
        lgbm_tuned: 1.076,
      },
    },
    band: {
      target_coverage: 0.8,
      quantile_coverage_pooled: 0.91933,
      split_conformal_coverage_last_fold: 0.85843,
      calibration_verdict: "conservative",
      horizon_coverage: Array.from({ length: 14 }, () => 0.85),
      horizon_avg_width: Array.from({ length: 14 }, () => 0),
      note: "coverages are empirical out-of-fold",
    },
    models: {
      champion: "hgb_tuned",
      challenger: "hgb",
      global: "hgb_tuned",
      naive: "seasonal_naive",
      selection_rule: "champion = committed _meta.best_model — selected on the selection folds only",
    },
    feature_schema: {
      calendar: ["t", "dow", "is_weekend", "month", "week", "doy_sin", "doy_cos"],
      lags: ["lag_1", "lag_7", "lag_14"],
      series: "one-hot series_id",
      note: "calendar + lag features only",
    },
    catalog_summary: {
      n_series: 3,
      by_class: { smooth: 1, intermittent: 1, sparse: 1 },
      history_days: 20,
      horizon_days: 14,
      forecast_window: ["2010-12-12", "2010-12-25"],
      class_thresholds: { zero_frac_smooth_max: 0.35, zero_frac_intermittent_max: 0.9 },
      origins: {
        early: { origin: 1, fold_index: 0, origin_date: "2010-06-05", horizon_window: ["2010-06-06", "2010-06-19"], history_days: 20 },
        middle: { origin: 2, fold_index: 1, origin_date: "2010-09-04", horizon_window: ["2010-09-05", "2010-09-18"], history_days: 20 },
        test: { origin: 4, fold_index: 3, origin_date: "2010-12-11", horizon_window: ["2010-12-12", "2010-12-25"], history_days: 20 },
      },
    },
  },
  origins_meta: {
    origins: [
      { label: "early", origin: 1, fold_index: 0, origin_date: "2010-06-05", horizon_window: ["2010-06-06", "2010-06-19"] },
      { label: "middle", origin: 2, fold_index: 1, origin_date: "2010-09-04", horizon_window: ["2010-09-05", "2010-09-18"] },
      { label: "test", origin: 4, fold_index: 3, origin_date: "2010-12-11", horizon_window: ["2010-12-12", "2010-12-25"], holdout: "test" },
    ],
    selection_used_origins: [1, 2, 3],
    horizon_days: 14,
  },
  evaluation_metadata: {
    protocol: "rolling_origin_holdout_v1",
    rolling_origin: {
      n_origins: 4,
      origin_spacing_days: 70,
      horizon_days: 14,
      embargo_gap_days: 0,
      min_train_size_dates: 730,
      test_window: { origin: 4, start: "2010-12-12", end: "2010-12-25", n_days: 14 },
    },
    holdout_designation: "test",
    selection_used_origins: [1, 2, 3],
    test_origin: 4,
    selection_rule: "lowest pooled MAE over the selection folds",
    preprocessing_statement: "x",
    metric_definitions: {
      mae: "mean absolute error",
      mase: "mae over the seasonal-naive scale",
      bias: "mean signed error",
      wape: "weighted absolute percentage error",
    },
    best_model: "hgb_tuned",
    strongest_naive: "seasonal_naive",
    target_definition: "The forecast target is the next 14 days of daily units per series.",
  },
  dataset_metadata: {
    dataset: "UCI Online Retail II",
    source: { url: "https://example", sha256: "abc", sheet: "x", license: "CC BY 4.0" },
    cancellation_filtering: "cancellations removed",
    quantity_handling: "quantities summed",
    geography: "top countries",
    products: "top products",
    daily_aggregation: "daily",
    observed_panel: {
      date_start: "2010-01-01",
      date_end: "2010-12-31",
      n_days: 365,
      n_rows: 1000,
      n_series: 3,
      zero_share: 0.5,
    },
    zero_sales_caveat: "Zero-sales days may be missing rather than true zero demand.",
    target_definition: "next 14 days of daily units",
  },
};

/** Manifest fixture mirroring projects/02-demand-forecasting/demo.yaml. */
const MANIFEST = {
  id: "forecast-workbench",
  title: "demand forecast workbench",
  hook: "Pick a store-product series, pick a rolling origin — early, middle, or the frozen test window — stretch the horizon, and stress the recent demand.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["time series forecasting", "prediction intervals", "demand classification"],
  modes: ["browser", "live"],
  hero: {
    label: "frozen test-window MAE (origin-4 holdout), champion vs strongest floor",
    value: "9.54 vs 11.32 seasonal-naive (-15.7%)",
    ci: "no run clears MASE 1 on the frozen test window",
  },
  scenarios: [
    { name: "base", controls: { series: "United Kingdom|85123A", origin: "test", horizon: 7, spike: 1.0 } },
    { name: "early-origin", controls: { series: "United Kingdom|85123A", origin: "early", horizon: 7, spike: 1.0 } },
    { name: "spike", controls: { series: "United Kingdom|85123A", origin: "test", horizon: 7, spike: 1.5 } },
  ],
  live_endpoints: [
    {
      method: "POST",
      path: "/projects/02-demand-forecasting/forecast",
      label: "live what-if scoring",
      cost: "free-local",
    },
  ],
  payload: {
    path: "reports/demo_payload.json",
    schema_version: 2,
    required_keys: ["demo", "project", "track", "catalog", "scalars", "origins_meta", "evaluation_metadata", "dataset_metadata"],
  },
};

function mockFetch(handler: (path: string, init?: RequestInit) => Response | Promise<Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      return Promise.resolve(handler(url, init));
    }),
  );
}

function payloadFetch() {
  return (path: string) => {
    if (path.endsWith("/demos/forecast-workbench/manifest")) return jsonResponse(MANIFEST);
    if (path.endsWith("/demos/forecast-workbench/payload")) return jsonResponse(PAYLOAD);
    return jsonResponse({}, 404);
  };
}

function renderDemo() {
  return render(
    <MemoryRouter>
      <ForecastWorkbench />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  // the demos serialize state to window.location — reset it so a test's
  // query params never leak into the next mount
  window.history.replaceState(null, "", "/");
});

describe("ForecastWorkbench", () => {
  it("shows a loading state then the title, readouts, and KPIs", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    expect(screen.getByText("loading demo…")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "demand forecast workbench" }),
      ).toBeInTheDocument(),
    );
    // readout chips for the default (smooth) series at the test origin, h=7
    expect(screen.getAllByText("United Kingdom · 85123A").length).toBeGreaterThan(0);
    expect(screen.getByText("horizon 7d")).toBeInTheDocument();
    expect(screen.getByText("spike ×1.0")).toBeInTheDocument();
    expect(screen.getByText("origin Dec 11")).toBeInTheDocument();
    // day-7 MASE: champion |56−30|/2 = 13.00, naive |61−30|/2 = 15.50
    expect(screen.getByText("MASE 13.00 — trails naive (15.50)")).toBeInTheDocument();
    // KPI band: MASE, bias (mean signed err days 1..7 = 23), WAPE (161/210), coverage
    expect(screen.getByText("13.00 vs 15.50")).toBeInTheDocument();
    expect(screen.getByText("+23.0")).toBeInTheDocument();
    expect(screen.getByText("76.7%")).toBeInTheDocument();
    expect(screen.getByText("91.9%")).toBeInTheDocument();
    // evidence drawer
    const drawer = document.querySelector(".wb-evidence")!;
    expect(drawer.textContent).toContain("hgb_tuned");
    expect(drawer.textContent).toContain("rolling_origin_holdout_v1");
    expect(drawer.textContent).toContain("15.7% vs floor");
    expect(drawer.textContent).toContain("No run clears");
  });

  it("renders two capitalized notice tiles with the per-origin verdicts", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    const tiles = document.querySelectorAll(".wb-notice-strip .wb-notice");
    expect(tiles).toHaveLength(2);
    // origin context: early edge = (11−10)/11 ≈ 9%; test edge = (7−5)/7 ≈ 29%
    expect(tiles[0].textContent).toContain("At the early origin the champion wins by 9% MAE");
    expect(tiles[0].textContent).toContain("widens to 29% vs a much harder seasonal floor");
    // model verdict: champion beats naive by 29% at the test origin (MASE 2.50)
    expect(tiles[1].textContent).toContain("Champion beats naive by 29%");
    expect(tiles[1].textContent).toContain("MASE 2.50");
    for (const tile of Array.from(tiles)) {
      expect(tile.textContent!.replace("▸", "").trim()[0]).toMatch(/[A-Z]/);
    }
  });

  it("marks the test origin as the frozen test window", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    expect(screen.getAllByText("frozen test window").length).toBeGreaterThan(0);
    expect(screen.getByText(/% through history/)).toBeInTheDocument();
  });

  it("filters the picker by demand class and search", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    const list = screen.getByRole("list", { name: "Series list" });
    expect(list.querySelectorAll(".wb-series-row")).toHaveLength(3);
    // class filter → sparse only
    fireEvent.click(screen.getByRole("button", { name: "sparse" }));
    const sparseRows = list.querySelectorAll(".wb-series-row");
    expect(sparseRows).toHaveLength(1);
    expect(sparseRows[0].textContent).toContain("Denmark · 37410");
    // back to all + search narrows
    fireEvent.click(screen.getByRole("button", { name: "all" }));
    fireEvent.change(screen.getByLabelText("Search series"), { target: { value: "france" } });
    const franceRows = list.querySelectorAll(".wb-series-row");
    expect(franceRows).toHaveLength(1);
    expect(franceRows[0].textContent).toContain("France · 85123A");
    // no match → empty entry
    fireEvent.change(screen.getByLabelText("Search series"), { target: { value: "zzz" } });
    expect(list.querySelectorAll(".wb-series-row")).toHaveLength(0);
    expect(screen.getByText("no series matches")).toBeInTheDocument();
  });

  it("replays the committed curves when the origin slider moves", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    // default: test origin (Dec 11), day-7 champion MASE 13.00
    expect(screen.getByText("13.00 vs 15.50")).toBeInTheDocument();
    const originSlider = screen.getByLabelText("Forecast origin", { selector: "input" });
    fireEvent.change(originSlider, { target: { value: "0" } }); // early
    expect(screen.getByText(/early · Jun 5/)).toBeInTheDocument();
    expect(screen.getByText("origin Jun 5")).toBeInTheDocument();
    // early day-7 MASE: champion |66−40|/4 = 6.50, naive |76−40|/4 = 9.00
    expect(screen.getByText("6.50 vs 9.00")).toBeInTheDocument();
    expect(screen.getByText("MASE 6.50 — trails naive (9.00)")).toBeInTheDocument();
    // the comparison table still grades all three origins
    expect(screen.getByText("model")).toBeInTheDocument();
    expect(screen.getByText(/identical origins and horizons/)).toBeInTheDocument();
  });

  it("switches the fan when the model chip changes", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    // champion: the committed p10–p90 band overlay is present
    expect(document.querySelector(".wb-fan-band path")).not.toBeNull();
    // the rail chip (the comparison table also carries a "naive" row button)
    const rail = document.querySelector(".wb-controls")!;
    fireEvent.click(within(rail as HTMLElement).getByRole("button", { name: "naive" }));
    // naive: point-only dashed — no band path, and the readout chip follows
    expect(document.querySelector(".wb-fan-band path")).toBeNull();
    expect(screen.getByText("MASE 15.50 — trails naive (15.50)")).toBeInTheDocument();
    fireEvent.click(within(rail as HTMLElement).getByRole("button", { name: "challenger" }));
    expect(screen.getByText("MASE 14.00 — trails naive (15.50)")).toBeInTheDocument();
    // the verdict tile names the selected model
    const tiles = document.querySelectorAll(".wb-notice-strip .wb-notice");
    expect(tiles[1].textContent).toContain("Challenger");
  });

  it("sets the model chip from a comparison-table row", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    // default tab is model comparison, naive first (early naive MASE 11/4 = 2.75)
    const table = document.querySelector(".wb-cmp-table")!;
    const rows = table.querySelectorAll("tbody tr");
    expect(rows[0].textContent).toContain("naive");
    expect(rows[0].textContent).toContain("MASE 2.75");
    fireEvent.click(within(table as HTMLElement).getAllByRole("button", { name: "naive" })[0]);
    expect(screen.getByText("MASE 15.50 — trails naive (15.50)")).toBeInTheDocument();
  });

  it("extends the committed fan when the horizon slider moves", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    const svg = screen.getByRole("img", { name: "as-of-origin demand history with forecast fan and ghost actuals" });
    // series order: history (1 run), model fan, ghost actuals
    const fan = svg.querySelectorAll("polyline")[1];
    const runLen = (el: Element) => el.getAttribute("points")!.trim().split(" ").length;
    expect(runLen(fan)).toBe(7);
    const slider = screen.getByLabelText("Forecast horizon", { selector: "input" });
    fireEvent.change(slider, { target: { value: "14" } });
    // readout chip (the evidence drawer also tags the committed horizon)
    expect(screen.getAllByText("horizon 14d").length).toBeGreaterThan(0);
    expect(runLen(fan)).toBe(14);
    // filled track follows the slider
    expect(slider.style.getPropertyValue("--fill")).toBe("100%");
  });

  it("highlights a canvas day when an error-analysis bar is clicked", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    fireEvent.click(screen.getByRole("tab", { name: "error analysis" }));
    const viz = screen.getByRole("img", { name: "absolute error by horizon day, colored by sign" });
    const bars = viz.querySelectorAll("rect");
    expect(bars).toHaveLength(14);
    // day 14 carries the largest error (63−30 = 33) and is annotated "worst"
    fireEvent.click(bars[13]);
    expect(screen.getByText("error day h=14")).toBeInTheDocument();
    // the marker line in the canvas AND the "worst h=14" note in the summary
    expect(screen.getAllByText("h=14").length).toBeGreaterThanOrEqual(2);
    // over/under split summary (all champion days over-forecast the flat 30)
    expect(screen.getByText(/over on/)).toBeInTheDocument();
    // clicking the same bar again clears the highlight
    fireEvent.click(bars[13]);
    expect(screen.queryByText("error day h=14")).toBeNull();
  });

  it("shows the calibration verdict chip in the reliability view", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    fireEvent.click(screen.getByRole("tab", { name: "uncertainty & reliability" }));
    expect(
      screen.getByText("conservative — but degenerate: the band collapses to zero width on zero-demand days"),
    ).toBeInTheDocument();
    expect(screen.getByText(/coverage and width, never looks/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "per-horizon coverage vs target and interval width trend" })).toBeInTheDocument();
  });

  it("degrades to n/a on a zero-scale sparse series", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    fireEvent.click(within(screen.getByRole("list", { name: "Series list" })).getByRole("button", { name: /Denmark · 37410/ }));
    expect(screen.getByText("MASE n/a — zero-scale window")).toBeInTheDocument();
    expect(screen.getByText("(zero-scale window)")).toBeInTheDocument();
    const tiles = document.querySelectorAll(".wb-notice-strip .wb-notice");
    expect(tiles[0].textContent).toContain("zero seasonal scale");
  });

  it("re-scores live through three bounded calls when the spike moves", async () => {
    const posts: Array<{ series_id: string; features: Record<string, number> }> = [];
    mockFetch((path, init) => {
      if (path.endsWith("/demos/forecast-workbench/manifest")) return jsonResponse(MANIFEST);
      if (path.endsWith("/demos/forecast-workbench/payload")) return jsonResponse(PAYLOAD);
      if (path.endsWith("/projects/02-demand-forecasting/forecast")) {
        expect(init?.method).toBe("POST");
        posts.push(JSON.parse(String(init?.body)));
        return jsonResponse({ forecast: 120, model: "hgb_tuned" });
      }
      return jsonResponse({}, 404);
    });
    renderDemo();
    await screen.findByText("horizon 7d");
    fireEvent.change(screen.getByLabelText("Recent demand spike", { selector: "input" }), { target: { value: "1.5" } });
    // one call per horizon, h=1..3, lag-scaled features off the origin history
    await waitFor(() => expect(posts).toHaveLength(3), { timeout: 3000 });
    expect(posts.map((p) => p.features.t)).toEqual([20, 21, 22]);
    expect(posts[0].features.lag_1).toBeCloseTo(30, 6); // last actual 20 × 1.5
    expect(posts[0].features.lag_7).toBeCloseTo(21, 6); // 14 × 1.5 — hot week
    expect(posts[0].features.lag_14).toBe(7); // committed — older than the hot week
    expect(posts[0].features.dow).toBe(7); // 2010-12-12 is a Sunday
    expect(posts[0].series_id).toBe("United Kingdom|85123A");
    // the amber fan + spike notice arrive
    await waitFor(() =>
      expect(
        screen.getByText(/amber fan: live re-score/),
      ).toBeInTheDocument(),
    );
    const tiles = document.querySelectorAll(".wb-notice-strip .wb-notice");
    // the verdict tile stays dynamic; the hint carries the live note
    expect(screen.getByText("spike ×1.5")).toBeInTheDocument();
    expect(tiles.length).toBe(2);
  });

  it("disables the spike lever gracefully when live scoring returns 503", async () => {
    mockFetch((path) => {
      if (path.endsWith("/demos/forecast-workbench/manifest")) return jsonResponse(MANIFEST);
      if (path.endsWith("/demos/forecast-workbench/payload")) return jsonResponse(PAYLOAD);
      if (path.endsWith("/forecast")) return jsonResponse({ detail: "serving artifacts not built" }, 503);
      return jsonResponse({}, 404);
    });
    renderDemo();
    await screen.findByText("horizon 7d");
    const slider = screen.getByLabelText("Recent demand spike", { selector: "input" }) as HTMLInputElement;
    fireEvent.change(slider, { target: { value: "1.4" } });
    await waitFor(
      () =>
        expect(
          screen.getByText(/Live re-scoring unavailable — spike lever disabled/i),
        ).toBeInTheDocument(),
      { timeout: 3000 },
    );
    expect(slider.disabled).toBe(true);
    // spike reset to 1.0
    expect(screen.getByText("spike ×1.0")).toBeInTheDocument();
  });

  it("renders the tabbed secondary band with full commentary, no fig ids", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    const panel = document.querySelector(".wb-secondary-wide")!;
    expect(panel).not.toBeNull();
    // three tabs, model comparison active by default
    const tabs = within(panel as HTMLElement).getAllByRole("tab");
    expect(tabs).toHaveLength(3);
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    for (const tab of ["error analysis", "uncertainty & reliability"]) {
      fireEvent.click(screen.getByRole("tab", { name: tab }));
      const band = panel.querySelector("footer.figure-card-band")!;
      expect(band).not.toBeNull();
      expect(band.querySelector(".figure-id")).toBeNull();
      const comment = band.querySelector(".figure-comment")!;
      expect(comment.textContent!.length).toBeGreaterThan(40);
      expect(comment.className).not.toContain("line-clamp");
    }
  });

  it("serializes the string controls into the query string", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    const rail = document.querySelector(".wb-controls")!;
    fireEvent.click(within(rail as HTMLElement).getByRole("button", { name: "naive" }));
    fireEvent.change(screen.getByLabelText("Forecast origin", { selector: "input" }), { target: { value: "0" } });
    const params = new URLSearchParams(window.location.search);
    expect(params.get("model")).toBe("naive");
    expect(params.get("origin")).toBe("early");
  });

  it("shows an error state when the payload cannot be loaded", async () => {
    mockFetch(() => jsonResponse({ detail: "no payload" }, 404));
    renderDemo();
    await waitFor(() =>
      expect(screen.getByText(/could not load the demo payload/i)).toBeInTheDocument(),
    );
  });
});

describe("forecast workbench routing", () => {
  it("renders the demo at /demos/forecast-workbench inside App", async () => {
    mockFetch(payloadFetch());
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
    const experimentLinks = screen.getAllByRole("link", { name: "02-demand-forecasting" });
    expect(experimentLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of experimentLinks) {
      expect(link).toHaveAttribute("href", "/projects/02-demand-forecasting");
    }
  });

  it("404s the retired /demos/uplift-simulator route", async () => {
    mockFetch(payloadFetch());
    render(
      <MemoryRouter initialEntries={["/demos/uplift-simulator"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/\$ 404 — page not found/)).toBeInTheDocument(),
    );
  });
});
