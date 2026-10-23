import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import ForecastWorkbench from "../demos/forecast-workbench/ForecastWorkbench";
import type { CatalogSeries, ForecastPayload } from "../demos/types";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const N = 20;
const DATES = Array.from({ length: N }, (_, i) => {
  const d = new Date(2010, 11, 11);
  d.setDate(d.getDate() - (N - 1 - i));
  const iso = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${iso(d.getMonth() + 1)}-${iso(d.getDate())}`;
});
const FC_DATES = Array.from({ length: 14 }, (_, i) => {
  const d = new Date(2010, 11, 11);
  d.setDate(d.getDate() + 1 + i);
  const iso = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${iso(d.getMonth() + 1)}-${iso(d.getDate())}`;
});

function series(over: Partial<CatalogSeries>): CatalogSeries {
  return {
    series_id: "United Kingdom|85123A",
    label: "United Kingdom · 85123A",
    demand_class: "smooth",
    history: { dates: DATES, y: Array.from({ length: N }, (_, i) => i + 1) },
    forecast: {
      dates: FC_DATES,
      y_pred: Array.from({ length: 14 }, (_, i) => 50 + i),
      p10: Array.from({ length: 14 }, (_, i) => 40 + i),
      p90: Array.from({ length: 14 }, (_, i) => 60 + i),
      naive: Array.from({ length: 14 }, (_, i) => 55 + i),
    },
    errors: {
      scale: 2,
      champion: {
        mae: Array.from({ length: 14 }, (_, i) => 5 + i * 0.5),
        mase: Array.from({ length: 14 }, () => 0.8),
      },
      naive: {
        mae: Array.from({ length: 14 }, (_, i) => 7 + i * 0.5),
        mase: Array.from({ length: 14 }, () => 1.2),
      },
    },
    ...over,
  };
}

const SMOOTH = series({});
const INTERMITTENT = series({
  series_id: "France|85123A",
  label: "France · 85123A",
  demand_class: "intermittent",
  errors: {
    scale: 1,
    champion: {
      mae: Array.from({ length: 14 }, () => 6),
      mase: Array.from({ length: 14 }, () => 1.1),
    },
    naive: {
      mae: Array.from({ length: 14 }, () => 5.5),
      mase: Array.from({ length: 14 }, () => 1.05),
    },
  },
});
const SPARSE = series({
  series_id: "Denmark|37410",
  label: "Denmark · 37410",
  demand_class: "sparse",
  errors: {
    scale: 0,
    champion: {
      mae: Array.from({ length: 14 }, () => 0),
      mase: Array.from({ length: 14 }, () => null),
    },
    naive: {
      mae: Array.from({ length: 14 }, () => 0),
      mase: Array.from({ length: 14 }, () => null),
    },
  },
});

const PAYLOAD: ForecastPayload = {
  schema_version: 1,
  demo: "forecast-workbench",
  project: "02-demand-forecasting",
  track: "uci",
  catalog: [SMOOTH, INTERMITTENT, SPARSE],
  scalars: {
    headline: {
      claim: "only hgb_tuned clears MASE 1.0 — seasonal-naive parity — on real intermittent demand",
      champion: "hgb_tuned",
      champion_mase: 0.9802,
      champion_mae: 8.9892,
      naive_mase: 1.117,
      only_champion_below_mase_1: true,
      mase_by_model: {
        seasonal_naive: 1.117,
        hgb_tuned: 0.9802,
      },
    },
    band: {
      target_coverage: 0.8,
      quantile_coverage_pooled: 0.9193,
      split_conformal_coverage_last_fold: 0.8584,
      note: "coverages are empirical out-of-fold",
    },
    models: {
      champion: "hgb_tuned",
      global: "hgb_tuned",
      naive: "seasonal_naive",
      selection_rule: "champion = lowest pooled out-of-fold MAE",
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
      history_days: N,
      horizon_days: 14,
      forecast_window: [FC_DATES[0], FC_DATES[13]],
      class_thresholds: { zero_frac_smooth_max: 0.35, zero_frac_intermittent_max: 0.9 },
    },
  },
};

/** Manifest fixture mirroring projects/02-demand-forecasting/demo.yaml. */
const MANIFEST = {
  id: "forecast-workbench",
  title: "demand forecast workbench",
  hook: "Pick a store-product series, stretch the horizon, and stress the recent demand.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["time series forecasting", "prediction intervals", "demand classification"],
  modes: ["browser", "live"],
  hero: {
    label: "MASE on real intermittent demand (1.0 = seasonal-naive parity)",
    value: "0.980 vs 1.117 naive",
    ci: "only the tuned HGB clears MASE 1",
  },
  scenarios: [
    { name: "base", controls: { series: "United Kingdom|85123A", horizon: 7, spike: 1.0 } },
    { name: "spike", controls: { series: "United Kingdom|85123A", horizon: 7, spike: 1.5 } },
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
    schema_version: 1,
    required_keys: ["demo", "project", "track", "catalog", "scalars"],
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
  // ?series= pick never leaks into the next mount
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
    // readout chips for the default (smooth) series at horizon 7
    expect(screen.getAllByText("United Kingdom · 85123A").length).toBeGreaterThan(0);
    expect(screen.getByText("horizon 7d")).toBeInTheDocument();
    expect(screen.getByText("spike ×1.0")).toBeInTheDocument();
    expect(screen.getByText("MASE 0.80 — beats naive (1.20)")).toBeInTheDocument();
    // KPI band (MAE at h=7: champion 5+6·0.5 = 8.0, naive 7+6·0.5 = 10.0)
    expect(screen.getByText("0.80 vs 1.20")).toBeInTheDocument();
    expect(screen.getByText("8.0 vs 10.0")).toBeInTheDocument();
    expect(screen.getByText("91.9%")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument(); // history peak
    // evidence drawer
    const drawer = document.querySelector(".wb-evidence")!;
    expect(drawer.textContent).toContain("hgb_tuned");
    expect(drawer.textContent).toContain("pooled mase 0.9802");
  });

  it("renders two capitalized notice tiles for the default series", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    const tiles = document.querySelectorAll(".wb-notice-strip .wb-notice");
    expect(tiles).toHaveLength(2);
    expect(tiles[0].textContent).toContain(
      "Smooth series — the champion beats the weekly pattern by 20% (MASE 0.80)",
    );
    expect(tiles[1].textContent).toContain("No recent spike applied");
    for (const tile of Array.from(tiles)) {
      expect(tile.textContent!.replace("▸", "").trim()[0]).toMatch(/[A-Z]/);
    }
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

  it("switches every panel when the picker selection changes", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    const list = screen.getByRole("list", { name: "Series list" });
    // smooth → intermittent: the MASE chip flips to bad (row click, inside
    // the picker — the class explorer tile carries the same label)
    fireEvent.click(within(list).getByRole("button", { name: /France · 85123A/ }));
    expect(screen.getByText("MASE 1.10 — trails naive (1.05)")).toBeInTheDocument();
    expect(screen.getByText("1.10 vs 1.05")).toBeInTheDocument();
    const tiles = document.querySelectorAll(".wb-notice-strip .wb-notice");
    expect(tiles[0].textContent).toContain("Intermittent — the naive baseline is the one to beat");
    expect(tiles[0].textContent).toContain("cannot clear MASE 1 here (MASE 1.10)");
    // class tile for intermittent marks active
    expect(document.querySelector(".wb-class-tile.active")!.textContent).toContain("intermittent");
    // → sparse: MASE is undefined, everything degrades to n/a
    fireEvent.click(within(list).getByRole("button", { name: /Denmark · 37410/ }));
    expect(screen.getByText("MASE n/a — zero-scale series")).toBeInTheDocument();
    expect(screen.getByText("(zero-demand series)")).toBeInTheDocument();
    expect(tiles[0].textContent).toContain("MASE is undefined on a zero seasonal scale");
    // the selected row follows the switch
    expect(list.querySelector(".wb-series-row.active")!.textContent).toContain("Denmark");
  });

  it("extends the committed fan when the horizon slider moves", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    const svg = screen.getByRole("img", { name: "daily demand with forecast fan" });
    const champion = svg.querySelectorAll("polyline")[0];
    // the champion forecast is one contiguous run starting at the origin:
    // origin + 7 horizon points at h=7
    const runLen = (el: Element) =>
      el.getAttribute("points")!.trim().split(" ").length;
    expect(runLen(champion)).toBe(8);
    const slider = screen.getByLabelText("Forecast horizon", { selector: "input" });
    fireEvent.change(slider, { target: { value: "14" } });
    expect(screen.getByText("horizon 14d")).toBeInTheDocument();
    expect(screen.getByText("champion vs seasonal-naive · h=14d")).toBeInTheDocument();
    // horizon 14 uses the whole window: origin + 14 points
    expect(runLen(champion)).toBe(15);
    // filled track follows the slider
    expect(slider.style.getPropertyValue("--fill")).toBe("100%");
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
    // one call per horizon, h=1..3, lag-scaled features
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
        screen.getByText("amber fan: live re-score (h=1–3); band shows the committed backtest"),
      ).toBeInTheDocument(),
    );
    const tiles = document.querySelectorAll(".wb-notice-strip .wb-notice");
    expect(tiles[1].textContent).toContain(
      "A ×1.5 recent spike lifts the next-day forecast from 50 to 120 units (+140%)",
    );
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
    // spike reset to 1.0 and the notice tile carries the graceful note
    expect(screen.getByText("spike ×1.0")).toBeInTheDocument();
    const tiles = document.querySelectorAll(".wb-notice-strip .wb-notice");
    expect(tiles[1].textContent).toContain("the spike lever is off");
  });

  it("renders the secondary band with three panels and full commentary, no fig ids", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    const panels = document.querySelectorAll(".wb-secondary-panel");
    expect(panels).toHaveLength(3);
    for (const panel of Array.from(panels)) {
      const band = panel.querySelector("footer.figure-card-band");
      expect(band).not.toBeNull();
      expect(band!.querySelector(".figure-id")).toBeNull();
      const comment = band!.querySelector(".figure-comment")!;
      expect(comment.textContent!.length).toBeGreaterThan(40);
      expect(comment.className).not.toContain("line-clamp");
    }
    expect(screen.getByText("error by horizon")).toBeInTheDocument();
    expect(screen.getByText("champion vs naive by class")).toBeInTheDocument();
    expect(screen.getByText("class explorer")).toBeInTheDocument();
  });

  it("picks a representative series from the class explorer", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("horizon 7d");
    const tiles = document.querySelectorAll(".wb-class-tile");
    expect(tiles).toHaveLength(3);
    fireEvent.click(tiles[2]); // sparse tile
    expect(screen.getByText("MASE n/a — zero-scale series")).toBeInTheDocument();
    expect(document.querySelector(".wb-class-tile.active")!.textContent).toContain("sparse");
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
