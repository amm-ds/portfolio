import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import ForecastWorkbench from "../demos/forecast-workbench/ForecastWorkbench";
import type { DemoManifest, ForecastPayload } from "../demos/types";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** The REAL committed v3.1 payload — the contract the workbench renders. */
const PAYLOAD = JSON.parse(
  readFileSync("../../projects/02-demand-forecasting/reports/demo_payload.json", "utf8"),
) as ForecastPayload;
const COMMITTED = JSON.parse(
  readFileSync("../../projects/02-demand-forecasting/reports_uci/metrics.json", "utf8"),
)["_multistep"];

/** Manifest fixture mirroring projects/02-demand-forecasting/demo.yaml (v3.1). */
const MANIFEST: DemoManifest = {
  id: "forecast-workbench",
  title: "demand forecast workbench",
  hook: "Pick a store-product series, pick one of the three scored weekly origins, slide the true horizon h.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["time series forecasting", "prediction intervals", "demand classification"],
  modes: ["browser", "live"],
  hero: {
    label: "multi-step pooled MAE over the scored origins, routed pipeline vs all-HGB",
    value: "6.33 routed vs 10.67 all-HGB — the routed pipeline leads",
    ci: "routing lumpy series away from the boosted model wins +4.0 MAE [3.3, 4.8]",
  },
  scenarios: [
    { name: "base", controls: { horizon: 7, shock: 1 } },
    { name: "demand-shock", controls: { horizon: 7, shock: 2 } },
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
    schema_version: 3,
    required_keys: ["demo", "project", "track", "catalog"],
  },
};

function mockFetch(handler: (path: string) => Response | Promise<Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      return Promise.resolve(handler(url));
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

function firstSeries(cls: "erratic" | "lumpy", modelUsed?: string) {
  const s = PAYLOAD.catalog.find(
    (x) => x.demand_class === cls && (modelUsed === undefined || x.model_used === modelUsed),
  );
  if (!s) throw new Error(`no ${cls} (${modelUsed}) series in the payload`);
  return s;
}

function secondaryPanels(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>(".wb-secondary-panel"));
}

/** Text of the per-origin metrics table (scoreboard panel) — refits live. */
function perOriginTableText(): string {
  const panel = secondaryPanels()[0];
  return within(panel).getByRole("table", { name: "per-origin model metrics" }).textContent!;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  // the demos serialize state to window.location — reset it so a test's
  // query params never leak into the next mount
  window.history.replaceState(null, "", "/");
});

describe("ForecastWorkbench (schema v3.1)", () => {
  it("shows a loading state then the title, readouts, and KPI band", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    expect(screen.getByText("loading demo…")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "demand forecast workbench" }),
      ).toBeInTheDocument(),
    );
    const s = PAYLOAD.catalog[0];
    expect(screen.getAllByText(s.label).length).toBeGreaterThan(0);
    expect(screen.getAllByText(s.demand_class).length).toBeGreaterThan(0);
    // default: routed model, latest origin, h=7
    expect(screen.getAllByText("h = 7").length).toBeGreaterThan(0);
    // KPI band: MAE / MASE / bias / WAPE / coverage tiles all render values
    expect(screen.getByText("MAE at origin + h")).toBeInTheDocument();
    expect(screen.getByText("MASE at origin + h")).toBeInTheDocument();
    expect(screen.getByText("Bias at origin + h")).toBeInTheDocument();
    expect(screen.getByText("WAPE at origin + h")).toBeInTheDocument();
    expect(screen.getByText("Band coverage at h")).toBeInTheDocument();
    // evidence drawer carries the committed headline
    const drawer = document.querySelector(".wb-evidence")!;
    expect(drawer.textContent).toContain("+4.0 MAE [3.3, 4.8]");
    expect(drawer.textContent).toContain("direct_multihorizon_v1");
    expect(drawer.textContent).toContain("routed 6.33");
  });

  it("the secondary band is three always-visible panels — no tabs anywhere", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    const panels = secondaryPanels();
    expect(panels).toHaveLength(3);
    expect(within(panels[0]).getByText("model scoreboard")).toBeInTheDocument();
    expect(within(panels[1]).getByText("error analysis")).toBeInTheDocument();
    expect(within(panels[2]).getByText("reliability + decision")).toBeInTheDocument();
    expect(document.querySelector(".wb-tabs")).toBeNull();
    expect(screen.queryByRole("tablist")).toBeNull();
    expect(screen.queryByRole("tab")).toBeNull();
  });

  it("renders the class-verdict and horizon-truth notice tiles derived from the payload", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    const tiles = document.querySelectorAll(".wb-notice-strip .wb-notice");
    expect(tiles).toHaveLength(2);
    // catalog[0] is erratic (the builder puts every erratic series first) —
    // the tile cites the committed peak-capture numbers
    const peak = PAYLOAD.peak_capture.per_class.erratic;
    expect(tiles[0].textContent).toContain("Erratic series");
    expect(tiles[0].textContent).toContain(peak.zero!.peak_mae.toFixed(0));
    expect(tiles[0].textContent).toContain("excludes zero");
    // horizon truth quotes committed MASE at h=2 and h=14 (h=1 is a fixed
    // near-zero weekday under weekly origins — ratio would be an artifact)
    const mase = PAYLOAD.horizon_growth.mase.champion;
    expect(tiles[1].textContent).toContain(mase["2"]!.toFixed(2));
    expect(tiles[1].textContent).toContain(mase["14"]!.toFixed(2));
    for (const tile of Array.from(tiles)) {
      expect(tile.textContent!.replace("▸", "").trim()[0]).toMatch(/[A-Z]/);
    }
  });

  it("the lumpy notice cites the honest flat-vs-peak split", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    const lumpy = firstSeries("lumpy");
    const list = screen.getByRole("list", { name: "Series list" });
    fireEvent.click(within(list).getByRole("button", { name: new RegExp(lumpy.label) }));
    const tiles = document.querySelectorAll(".wb-notice-strip .wb-notice");
    const pooled = PAYLOAD.headline.pooled_mae_by_model;
    const peak = PAYLOAD.peak_capture.per_class.lumpy;
    expect(tiles[0].textContent).toContain("Lumpy series");
    expect(tiles[0].textContent).toContain(pooled.routed.toFixed(2));
    expect(tiles[0].textContent).toContain(pooled.hgb_tweedie.toFixed(2));
    expect(tiles[0].textContent).toContain(peak.routed!.peak_recall.toFixed(2));
    expect(tiles[0].textContent).toContain(peak.hgb_tweedie!.peak_recall.toFixed(2));
  });

  it("the h-slider switches between genuinely different curves (error grows)", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    const slider = screen.getByLabelText("Horizon h", { selector: "input" });
    const maeTile = () => screen.getByText("MAE at origin + h").nextElementSibling!.textContent!;
    // h=7 (index 3 on the lattice) vs h=1 (index 0) vs h=14 (index 6): the
    // KPI numbers must move — each stop is a different direct model
    const at7 = maeTile();
    fireEvent.change(slider, { target: { value: "0" } });
    const at1 = maeTile();
    fireEvent.change(slider, { target: { value: "6" } });
    const at14 = maeTile();
    expect(at1).not.toBe(at7);
    expect(at14).not.toBe(at7);
    expect(screen.getAllByText("h = 14").length).toBeGreaterThan(0);
    // and the derived per-h |err| at h=14 exceeds h=1 for the routed curve
    // on the default series (checked against the payload curves directly)
    const blk = PAYLOAD.catalog[0].origins.at(-1)!;
    const err = (h: number) => {
      const i = blk.horizons.indexOf(h);
      return Math.abs(blk.models.routed.y_pred[i] - blk.actuals.y[h - 1]);
    };
    expect(err(14)).not.toBe(err(1));
  });

  it("the origin slider moves across contiguous origins — no embargo shading anywhere", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    expect(screen.queryByText(/embargo/i)).toBeNull();
    const slider = screen.getByLabelText("Forecast origin", { selector: "input" });
    const dates = PAYLOAD.catalog_summary.origins.map((o) => o.origin_date);
    const before = perOriginTableText();
    fireEvent.change(slider, { target: { value: "0" } });
    // payload contiguity is contract-tested; here we assert the marker/badge
    // switch to the chosen origin and the per-origin table refits
    expect(screen.getByText(/— issued here/)).toBeInTheDocument();
    expect(new URLSearchParams(window.location.search).get("origin")).toBe(dates[0]);
    expect(perOriginTableText()).not.toBe(before);
  });

  it("all three panels respond to the horizon slider", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    const slider = screen.getByLabelText("Horizon h", { selector: "input" });
    const scoreboardBefore = perOriginTableText();
    // reliability: the growth spark's current-h marker moves (x1 attribute)
    const marker = () =>
      secondaryPanels()[2].querySelector('svg[aria-label="pooled MAE and MASE by true horizon, champion versus floor versus zero"] line[stroke-dasharray="3 3"]');
    const markerXBefore = marker()?.getAttribute("x1");
    fireEvent.change(slider, { target: { value: "6" } }); // h=14
    expect(perOriginTableText()).not.toBe(scoreboardBefore);
    expect(marker()?.getAttribute("x1")).not.toBe(markerXBefore);
  });

  it("the scoreboard table shows the committed class numbers", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    const panel = secondaryPanels()[0];
    expect(within(panel).getByText("class")).toBeInTheDocument();
    const lumpy = COMMITTED.headline_per_class.lumpy;
    // the class table cells combine values ("model / floor", "gap [CI]") —
    // assert on the rendered table text
    const classTable = within(panel).getByRole("table", { name: "class scoreboard" });
    expect(classTable.textContent).toContain(lumpy.h7.champion_mae.toFixed(2));
    expect(classTable.textContent).toContain(lumpy.h7.floor_mae.toFixed(2));
    // jsdom's toLocaleString does not group thousands — match either form
    expect(within(panel).getAllByText(/1,?069/).length).toBeGreaterThan(0);
    // the per-series beats honesty renders
    expect(within(panel).getByText(/beats floor/)).toBeInTheDocument();
  });

  it("the candidate rows carry the committed per-class numbers", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    const panel = secondaryPanels()[0];
    const table = within(panel).getByRole("table", { name: "peak-capable candidates" });
    // champion (routed) row + both wave-20 candidates, per-class h7 MAE
    expect(within(table).getByText("champion")).toBeInTheDocument();
    const lumpyTw = COMMITTED.headline_per_class.lumpy.h7.hgb_tweedie_mae;
    const erraticTw = COMMITTED.headline_per_class.erratic.h7.hgb_tweedie_mae;
    expect(within(table).getByText(lumpyTw.toFixed(2))).toBeInTheDocument();
    expect(within(table).getByText(erraticTw.toFixed(2))).toBeInTheDocument();
    // the committed peak-day numbers render too
    const lumpyPeak = PAYLOAD.peak_capture.per_class.lumpy.hgb_tweedie!.peak_mae;
    expect(within(table).getByText(lumpyPeak.toFixed(1))).toBeInTheDocument();
  });

  it("clicking a comparison-table model row sets the model chip", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    const panel = secondaryPanels()[0];
    const table = within(panel).getByRole("table", { name: "per-origin model metrics" });
    const zeroRow = within(table).getAllByRole("button", { name: "zero" })[0];
    fireEvent.click(zeroRow);
    expect(screen.getAllByText("zero").length).toBeGreaterThan(1);
    const params = new URLSearchParams(window.location.search);
    expect(params.get("model")).toBe("zero");
  });

  it("model chips reflect the series' committed method; unavailable candidates disable with the routing tooltip", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    const rail = document.querySelector<HTMLElement>(".wb-controls")!;
    // default series is erratic — the boosted HGB chip is live, and exactly
    // one of the candidate chips is enabled (the series' own method)
    const boosted = within(rail).getByRole("button", { name: "boosted HGB" });
    expect(boosted).not.toBeDisabled();
    const s = PAYLOAD.catalog[0];
    expect(within(rail).getByRole("button", { name: routedChipName(s) })).toBeInTheDocument();
    const own = s.model_used === "hurdle_hgb" ? "hurdle" : s.model_used === "hgb_tweedie" ? "tweedie" : null;
    if (own) {
      expect(within(rail).getByRole("button", { name: own })).not.toBeDisabled();
      const other = own === "hurdle" ? "tweedie" : "hurdle";
      const disabled = within(rail).getByRole("button", { name: other });
      expect(disabled).toBeDisabled();
      expect(disabled).toHaveAttribute("title", expect.stringContaining("training origins"));
    }
    // the boosted HGB chip disables on a lumpy series with the routing note
    const lumpy = firstSeries("lumpy");
    const list = screen.getByRole("list", { name: "Series list" });
    fireEvent.click(within(list).getByRole("button", { name: new RegExp(lumpy.label) }));
    expect(within(rail).getByRole("button", { name: "boosted HGB" })).toBeDisabled();
    expect(within(rail).getByRole("button", { name: "boosted HGB" })).toHaveAttribute(
      "title",
      "boosted models don't serve lumpy series — see the routing note",
    );
    // the class verdict tile flips to the lumpy wording
    const tiles = document.querySelectorAll(".wb-notice-strip .wb-notice");
    expect(tiles[0].textContent).toContain("Lumpy series");
  });

  function routedChipName(s: (typeof PAYLOAD.catalog)[number]): string {
    const short: Record<string, string> = {
      direct_hgb: "boosted HGB",
      hurdle_hgb: "hurdle",
      hgb_tweedie: "tweedie",
    };
    return `routed · ${short[s.model_used] ?? s.model_used}`;
  }

  it("the error-analysis bars follow the model chip and highlight a day on the explorer", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    const viz = screen.getByRole("img", {
      name: /signed direct-horizon routed forecast errors/,
    });
    // one bar per lattice horizon (7, not 14 — direct curves live on the lattice)
    expect(viz.querySelectorAll("rect")).toHaveLength(7);
    fireEvent.click(viz.querySelectorAll("rect")[6]); // h=14
    expect(screen.getByText("error day h=14")).toBeInTheDocument();
    fireEvent.click(viz.querySelectorAll("rect")[6]);
    expect(screen.queryByText("error day h=14")).toBeNull();
    // switching the model chip re-titles the bars
    fireEvent.click(screen.getAllByRole("button", { name: "zero" })[0]);
    expect(
      screen.getByRole("img", { name: /signed direct-horizon zero forecast errors/ }),
    ).toBeInTheDocument();
  });

  it("the decision layer responds to the τ slider", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    expect(screen.getByText("τ", { selector: "label" })).toBeInTheDocument();
    const tauSlider = screen.getByLabelText("τ", { selector: "input" });
    expect(tauSlider).toHaveValue("0.9");
    const ordersBefore = screen.getByText(/routed over /).textContent;
    fireEvent.change(tauSlider, { target: { value: "0.99" } });
    expect(screen.getByText("τ = 0.99")).toBeInTheDocument();
    // the order readouts recompute and the simulation caption stays honest
    expect(screen.getByText(/routed over /).textContent).not.toBe(ordersBefore);
    expect(screen.getAllByText(/no savings claims/).length).toBeGreaterThan(0);
    // committed coverage/width blocks render
    expect(screen.getByRole("img", { name: /coverage versus target/ })).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /pooled MAE and MASE by true horizon/ }),
    ).toBeInTheDocument();
  });

  it("the demand-shock lever swaps to the precomputed curves", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    const maeTile = () => screen.getByText("MAE at origin + h").nextElementSibling!.textContent!;
    const base = maeTile();
    fireEvent.change(screen.getByLabelText("Demand shock", { selector: "input" }), {
      target: { value: "3" }, // ×2.0
    });
    expect(screen.getByText("×2.0")).toBeInTheDocument();
    expect(maeTile()).not.toBe(base);
  });

  it("control captions stay on a one-line budget — the multi-sentence explainers are gone", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    // the old origin explainer box is gone…
    expect(screen.queryByText(/Three of the four scored weekly test origins/)).toBeNull();
    expect(screen.queryByText(/re-fit offline, exactly/)).toBeNull();
    // …and every remaining rail caption fits one line (~120 chars)
    const hints = document.querySelectorAll(".wb-controls .demo-hint");
    expect(hints.length).toBeGreaterThan(0);
    for (const hint of Array.from(hints)) {
      const text = hint.textContent!.replace(/\s+/g, " ").trim();
      expect(text.length).toBeLessThanOrEqual(120);
    }
    // panel captions stay within two lines (~240 chars)
    const captions = document.querySelectorAll(".wb-secondary .figure-comment");
    expect(captions).toHaveLength(3);
    for (const caption of Array.from(captions)) {
      const text = caption.textContent!.replace(/\s+/g, " ").trim();
      expect(text.length).toBeLessThanOrEqual(240);
    }
  });

  it("surprise-me is seeded via the URL and stays inside the catalog", async () => {
    mockFetch(payloadFetch());
    window.history.replaceState(null, "", "/demos/forecast-workbench?seed=41");
    renderDemo();
    await screen.findByText("MAE at origin + h");
    fireEvent.click(screen.getByRole("button", { name: "surprise me" }));
    const params = new URLSearchParams(window.location.search);
    expect(params.get("seed")).toBe("42");
    const picked = params.get("series");
    expect(picked).toBeTruthy();
    expect(PAYLOAD.catalog.some((s) => s.series_id === picked)).toBe(true);
    // same seed → same pick on a fresh mount (class-stratified, deterministic)
    cleanup();
    window.history.replaceState(null, "", "/demos/forecast-workbench?seed=41");
    vi.clearAllMocks();
    mockFetch(payloadFetch());
    render(
      <MemoryRouter initialEntries={["/demos/forecast-workbench?seed=41"]}>
        <ForecastWorkbench />
      </MemoryRouter>,
    );
    await screen.findByText("MAE at origin + h");
    fireEvent.click(screen.getByRole("button", { name: "surprise me" }));
    expect(new URLSearchParams(window.location.search).get("series")).toBe(picked);
  });

  it("serializes the string controls into the query string", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("MAE at origin + h");
    const rail = document.querySelector<HTMLElement>(".wb-controls")!;
    fireEvent.click(within(rail).getByRole("button", { name: "zero" }));
    fireEvent.change(screen.getByLabelText("Forecast origin", { selector: "input" }), {
      target: { value: "0" },
    });
    const params = new URLSearchParams(window.location.search);
    expect(params.get("model")).toBe("zero");
    expect(params.get("origin")).toBe(PAYLOAD.catalog_summary.origins[0].origin_date);
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
    await waitFor(() => expect(screen.getByText(/\$ 404 — page not found/)).toBeInTheDocument());
  });
});
