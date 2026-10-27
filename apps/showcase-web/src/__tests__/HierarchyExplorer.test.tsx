import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import HierarchyExplorer from "../demos/hierarchy-explorer/HierarchyExplorer";
import {
  groupNodes,
  horizonMae,
  maeByVariant,
  nodeOrigin,
  originDates,
} from "../demos/hierarchy-explorer/kpis";
import type { DemoManifest, HierarchyPayload } from "../demos/types";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** The REAL committed payload — the contract the explorer renders. */
const PAYLOAD = JSON.parse(
  readFileSync("../../projects/02-demand-forecasting/reports/hier_demo_payload.json", "utf8"),
) as HierarchyPayload;

/** Manifest fixture mirroring projects/02-demand-forecasting/demos/hierarchy-explorer.yaml.
 * The hero numbers derive from the payload so a regeneration never leaves the
 * fixture stale. */
const MANIFEST: DemoManifest = {
  id: "hierarchy-explorer",
  title: "hierarchy explorer",
  hook: "Pick a node in the Labour or TourismSmall hierarchy and watch MinT snap the curves back into a coherent tree.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["hierarchical time series", "forecast reconciliation", "MinT"],
  modes: ["browser"],
  hero: {
    label: "total-level rmae, lgbm_global+MinT vs seasonal naive",
    value: `Labour ${PAYLOAD.groups.Labour.headline.total.rmae.toFixed(3)}, TourismSmall ${PAYLOAD.groups.TourismSmall.headline.total.rmae.toFixed(3)}`,
    ci: "committed wave-23a hierarchical track",
  },
  scenarios: [
    { name: "base", controls: { group: "Labour", node: "['Total']", origin: "2019-04-01" } },
  ],
  live_endpoints: [],
  payload: {
    path: "reports/hier_demo_payload.json",
    schema_version: 1,
    required_keys: ["demo", "project", "groups", "catalog", "evaluation_metadata"],
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
    if (path.endsWith("/demos/hierarchy-explorer/manifest")) return jsonResponse(MANIFEST);
    if (path.endsWith("/demos/hierarchy-explorer/payload")) return jsonResponse(PAYLOAD);
    return jsonResponse({}, 404);
  };
}

function renderDemo() {
  return render(
    <MemoryRouter>
      <HierarchyExplorer />
    </MemoryRouter>,
  );
}

function nodeList(): HTMLElement {
  return screen.getByRole("list", { name: "Node list" });
}

/** The default selection: Labour's first node (total) at the latest origin. */
function defaultSelection() {
  const node = groupNodes(PAYLOAD, "Labour")[0];
  const originDate = originDates(PAYLOAD, "Labour").at(-1)!;
  const origin = nodeOrigin(node, originDate)!;
  return { node, originDate, origin, mae: maeByVariant(origin) };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  // the demos serialize state to window.location — reset it so a test's
  // query params never leak into the next mount
  window.history.replaceState(null, "", "/");
});

describe("HierarchyExplorer (schema v1)", () => {
  it("shows a loading state then the title, node selector, and KPI band", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    expect(screen.getByText("loading demo…")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "hierarchy explorer" }),
      ).toBeInTheDocument(),
    );
    // node selector lists exactly the 6 Labour nodes with level badges
    const rows = within(nodeList()).getAllByRole("button");
    expect(rows).toHaveLength(6);
    expect(within(nodeList()).getByText("total · Total")).toBeInTheDocument();
    expect(within(nodeList()).getByText("Country/Region · New South Wales")).toBeInTheDocument();
    // KPI band: the four tiles render
    expect(screen.getByText("Horizon MAE — MinT vs raw")).toBeInTheDocument();
    expect(screen.getByText("Horizon MAE — other variants")).toBeInTheDocument();
    expect(screen.getByText("Coherence — MinT vs raw")).toBeInTheDocument();
    expect(screen.getByText("Total rmae (committed)")).toBeInTheDocument();
    // evidence drawer quotes both committed headline claims
    const drawer = document.querySelector(".wb-evidence")!;
    expect(drawer.textContent).toContain(PAYLOAD.groups.Labour.headline.claim);
    expect(drawer.textContent).toContain(PAYLOAD.groups.TourismSmall.headline.claim);
    expect(drawer.textContent).toContain("hierarchical_rolling_v1");
  });

  it("KPI MAE tiles are computed client-side from the payload curves", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("Horizon MAE — MinT vs raw");
    const { origin, mae } = defaultSelection();
    const expectedMae = horizonMae(
      origin.models["lgbm_global+mint_shrink"].y_pred,
      origin.actuals.y,
    )!;
    expect(expectedMae).toBeCloseTo(mae["lgbm_global+mint_shrink"]!, 12);
    // the tile value next to the label carries the same rounded numbers
    const tile = screen.getByText("Horizon MAE — MinT vs raw").nextElementSibling!.textContent!;
    expect(tile).toContain(mae["lgbm_global+mint_shrink"]!.toFixed(1));
    expect(tile).toContain(mae.lgbm_global!.toFixed(1));
    const other = screen
      .getByText("Horizon MAE — other variants")
      .nextElementSibling!.textContent!;
    expect(other).toContain(mae.seasonal_naive!.toFixed(1));
    expect(other).toContain(mae.auto_ets!.toFixed(1));
    expect(other).toContain(mae["lgbm_global+bottom_up"]!.toFixed(1));
    // committed group-level tile quotes the headline rmae
    const rmaeTile = screen.getByText("Total rmae (committed)").nextElementSibling!.textContent!;
    expect(rmaeTile).toContain(PAYLOAD.groups.Labour.headline.total.rmae.toFixed(3));
  });

  it("a parent node shows the coherence tile quoting raw vs MinT incoherence", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("Coherence — MinT vs raw");
    const tile = screen.getByText("Coherence — MinT vs raw").nextElementSibling!.textContent!;
    expect(tile).toContain(PAYLOAD.groups.Labour.coherence["lgbm_global"].toFixed(3));
    expect(tile).toContain("0.000");
    // the bottom-node tile is not shown on a parent
    expect(screen.queryByText("Coherence — bottom leaves")).toBeNull();
    // the notice narrates the raw-vs-MinT MAE gap
    const notice = document.querySelector(".wb-notice-strip")!;
    expect(notice.textContent).toContain("incoherence");
  });

  it("selecting a bottom node swaps the coherence tile for the BottomUp note", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("Coherence — MinT vs raw");
    const bottom = groupNodes(PAYLOAD, "Labour").find((n) => n.level === "bottom")!;
    const bottomRow = within(nodeList())
      .getAllByRole("button")
      .find((b) => b.textContent!.includes("bottom"))!;
    fireEvent.click(bottomRow);
    expect(screen.queryByText("Coherence — MinT vs raw")).toBeNull();
    expect(screen.getByText("Coherence — bottom leaves")).toBeInTheDocument();
    // the chart commentary carries the BottomUp note
    expect(
      screen.getAllByText(/reconciliation leaves bottom series unchanged/).length,
    ).toBeGreaterThan(0);
    expect(new URLSearchParams(window.location.search).get("node")).toBe(bottom.node);
  });

  it("switching to TourismSmall repopulates the node list and the group tile", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("Total rmae (committed)");
    fireEvent.click(screen.getByRole("button", { name: "TourismSmall" }));
    const rows = within(nodeList()).getAllByRole("button");
    expect(rows).toHaveLength(6);
    expect(within(nodeList()).getByText("total · total")).toBeInTheDocument();
    expect(within(nodeList()).getByText("Country/Purpose · hol")).toBeInTheDocument();
    const rmaeTile = screen.getByText("Total rmae (committed)").nextElementSibling!.textContent!;
    expect(rmaeTile).toContain(PAYLOAD.groups.TourismSmall.headline.total.rmae.toFixed(3));
    // the coherence tile quotes TourismSmall's raw incoherence (0.102…)
    const cohTile = screen.getByText("Coherence — MinT vs raw").nextElementSibling!.textContent!;
    expect(cohTile).toContain(PAYLOAD.groups.TourismSmall.coherence["lgbm_global"].toFixed(3));
    expect(new URLSearchParams(window.location.search).get("group")).toBe("TourismSmall");
  });

  it("the origin chips switch the selected origin and serialize to the query string", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("Horizon MAE — MinT vs raw");
    const dates = originDates(PAYLOAD, "Labour");
    // the latest origin IS the default — clicking it drops the param by design
    fireEvent.click(screen.getByRole("button", { name: /Apr 1 · latest/ }));
    expect(new URLSearchParams(window.location.search).get("origin")).toBeNull();
    const before = screen.getByText("Horizon MAE — MinT vs raw").nextElementSibling!.textContent!;
    fireEvent.click(screen.getByRole("button", { name: "Feb 1" }));
    expect(new URLSearchParams(window.location.search).get("origin")).toBe(dates[0]);
    const after = screen.getByText("Horizon MAE — MinT vs raw").nextElementSibling!.textContent!;
    expect(after).not.toBe(before);
  });

  it("shows an error state when the payload cannot be loaded", async () => {
    mockFetch(() => jsonResponse({ detail: "no payload" }, 404));
    renderDemo();
    await waitFor(() =>
      expect(screen.getByText(/could not load the demo payload/i)).toBeInTheDocument(),
    );
  });
});

describe("hierarchy explorer routing", () => {
  it("renders the demo at /demos/hierarchy-explorer inside App", async () => {
    mockFetch(payloadFetch());
    render(
      <MemoryRouter initialEntries={["/demos/hierarchy-explorer"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "hierarchy explorer" }),
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
});
