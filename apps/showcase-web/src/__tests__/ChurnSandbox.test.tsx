import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Project } from "../api";
import { App } from "../App";
import ChurnSandbox from "../demos/churn-sandbox/ChurnSandbox";
import type { ChurnPayload } from "../demos/types";
import { ProjectDetail } from "../pages/ProjectDetail";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** 5-threshold fixture, holdout n = 1,000 so per-1,000 counts are the raw counts. */
const THRESHOLDS = [0.1, 0.3, 0.5, 0.7, 0.9];
const OVERALL = [
  { t: 0.1, tn: 600, fp: 300, fn: 10, tp: 90 },
  { t: 0.3, tn: 690, fp: 210, fn: 25, tp: 75 },
  { t: 0.5, tn: 760, fp: 140, fn: 45, tp: 55 },
  { t: 0.7, tn: 820, fp: 80, fn: 65, tp: 35 },
  { t: 0.9, tn: 870, fp: 30, fn: 85, tp: 15 },
];

/** Manifest fixture mirroring projects/05-ml-pipeline-churn/demo.yaml. */
const MANIFEST = {
  id: "churn-sandbox",
  title: "churn threshold sandbox",
  hook: "Move the alarm threshold and the missed-churner cost — watch the saved budget change.",
  project: "05-ml-pipeline-churn",
  group: "retain customers",
  skills: ["classification economics", "calibration", "decision science"],
  modes: ["browser", "live"],
  hero: null,
  scenarios: [
    { name: "base", controls: { fn_ratio: 5, threshold: 0.175 } },
    { name: "high-cost-miss", controls: { fn_ratio: 9, threshold: 0.12 } },
  ],
  live_endpoints: [
    {
      method: "POST",
      path: "/projects/05-ml-pipeline-churn/score",
      label: "live customer scoring",
      cost: "free-local",
    },
  ],
  payload: {
    path: "reports/demo_payload.json",
    schema_version: 1,
    required_keys: ["demo", "project", "holdout_n", "model", "cost_model", "headline", "thresholds", "overall", "slices", "calibration", "customers", "feature_domains", "roc_auc"],
  },
};

/** Registry entry for the demo CTA tests (fixed /demos contract). */
const CHURN_DEMO_ENTRY = {
  id: "churn-sandbox",
  title: "churn threshold sandbox",
  hook: "Move the alarm threshold — watch the saved budget change.",
  group: "retain customers",
  href: "/demos/churn-sandbox",
  project: "05-ml-pipeline-churn",
  status: "live",
  hero: null,
};

const PAYLOAD: ChurnPayload = {
  demo: "churn-threshold-sandbox",
  project: "05-ml-pipeline-churn",
  holdout_n: 1000,
  model: {
    name: "selected_model_calibrated",
    roc_auc: 0.83,
    ece: 0.02,
    threshold_default: 0.5,
    threshold_selected: 0.3,
  },
  cost_model: { fp_cost: 1, fn_cost: 5, note: "cost = fp_cost·FP + fn_cost·FN per 1,000-customer holdout" },
  headline: {
    cost_naive: 365,
    cost_selected: 335,
    delta_ci: { point: -30, lo: -40, hi: -20, significant_95: true },
  },
  thresholds: THRESHOLDS,
  overall: OVERALL,
  slices: {
    contract: {
      "month-to-month": OVERALL.map((r) => ({
        ...r,
        fp: r.fp + 40,
        tn: r.tn - 40,
      })),
      "two-year": OVERALL.map((r) => ({
        ...r,
        fp: Math.max(r.fp - 30, 0),
        tn: r.tn + 30,
        fn: Math.max(r.fn - 15, 0),
        tp: r.tp + 15,
      })),
    },
  },
  calibration: [
    { bin_lo: 0.0, bin_hi: 0.5, n: 400, mean_predicted: 0.2, observed: 0.18 },
    { bin_lo: 0.5, bin_hi: 1.0, n: 100, mean_predicted: 0.8, observed: 0.76 },
  ],
  customers: [
    {
      label: "at-risk fiber customer",
      features: { tenure_months: 3, monthly_charges: 95, contract: "month-to-month", internet_service: "fiber-optic" },
      churn_probability: 0.72,
    },
    {
      label: "sticky dsl customer",
      features: { tenure_months: 58, monthly_charges: 40, contract: "two-year", internet_service: "DSL" },
      churn_probability: 0.11,
    },
  ],
  feature_domains: {
    tenure_months: { min: 1, max: 72 },
    monthly_charges: { min: 18, max: 120 },
    contract: ["month-to-month", "one-year", "two-year"],
    internet_service: ["DSL", "fiber-optic", "no"],
  },
  roc_auc: 0.83,
};

const CHURN_PROJECT: Project = {
  id: "05-ml-pipeline-churn",
  title: "Churn",
  domain: "ML Systems",
  topic: "ML Systems & Decisioning",
  techniques: ["sklearn"],
  data: "telco",
  status: "flagship",
  order: 5,
};

function mockFetch(handler: (path: string, init?: RequestInit) => Response | Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    return Promise.resolve(handler(url, init));
  }));
}

function payloadFetch() {
  return (path: string) => {
    if (path.endsWith("/demos/churn-sandbox/manifest")) return jsonResponse(MANIFEST);
    if (path.endsWith("/demos/churn-sandbox/payload")) return jsonResponse(PAYLOAD);
    return jsonResponse({}, 404);
  };
}

function renderDemo() {
  return render(
    <MemoryRouter>
      <ChurnSandbox />
    </MemoryRouter>,
  );
}

/** Stub layout so pointer math works: svg viewBox 720px maps 1:1 to client coords. */
function stubSvgRect() {
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockReturnValue({
    left: 0,
    top: 0,
    width: 720,
    height: 280,
    right: 720,
    bottom: 280,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  } as DOMRect);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ChurnSandbox", () => {
  it("shows a loading state then the demo title and cost readouts", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    expect(screen.getByText("loading demo…")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "churn threshold sandbox" }),
      ).toBeInTheDocument(),
    );
    // cursor defaults to the committed threshold (0.3) at fn_cost = 5
    expect(screen.getByText("threshold t = 0.30")).toBeInTheDocument();
    expect(screen.getByText("cost at t: 335")).toBeInTheDocument();
    expect(screen.getByText("cost at 0.5: 365")).toBeInTheDocument();
    expect(screen.getByText("saves 30 vs 0.5")).toBeInTheDocument();
    // TP 75 + FP 210 contacts at t = 0.3
    expect(screen.getByText("contact 285 of 1000")).toBeInTheDocument();
    // decision outcomes per 1,000 (holdout n = 1,000 → raw counts)
    expect(screen.getByText("TP 75")).toBeInTheDocument();
    expect(screen.getByText("FP 210")).toBeInTheDocument();
    expect(screen.getByText("FN 25")).toBeInTheDocument();
    expect(screen.getByText("TN 690")).toBeInTheDocument();
    // slices at t = 0.3: month-to-month TP 75 + FP 250 = 325; two-year TP 90 + FP 180 = 270
    expect(screen.getByText("325 alarms")).toBeInTheDocument();
    expect(screen.getByText("270 alarms")).toBeInTheDocument();
    // footer honest-numbers lines
    expect(document.querySelector(".demo-footer")!.textContent).toContain(
      "selected_model_calibrated",
    );
    expect(document.querySelector(".demo-footer")!.textContent).toContain("-30 [-40, -20]");
  });

  it("flips the cost math when the FN slider moves", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await waitFor(() => expect(screen.getByText("cost at t: 335")).toBeInTheDocument());
    // fn_ratio 5 → 1: cost = fp + fn; at t = 0.3 → 210 + 25 = 235 vs 0.5 → 140 + 45 = 185
    fireEvent.change(screen.getByLabelText(/a missed churner costs/), { target: { value: "1" } });
    expect(screen.getByText("cost at t: 235")).toBeInTheDocument();
    expect(screen.getByText("cost at 0.5: 185")).toBeInTheDocument();
    expect(screen.getByText("costs 50 vs 0.5")).toBeInTheDocument();
  });

  it("moves the threshold via pointer events and updates the outcome counts", async () => {
    mockFetch(payloadFetch());
    stubSvgRect();
    renderDemo();
    const svg = await screen.findByRole("img", { name: "campaign cost over alarm threshold" });
    // jsdom's PointerEvent drops clientX — dispatch a MouseEvent typed pointerdown
    fireEvent(svg, new MouseEvent("pointerdown", { bubbles: true, clientX: 382, buttons: 1 }));
    expect(screen.getByText("threshold t = 0.50")).toBeInTheDocument();
    expect(screen.getByText("cost at t: 365")).toBeInTheDocument();
    // outcomes at t = 0.5, fn_cost = 5
    expect(screen.getByText("TP 55")).toBeInTheDocument();
    expect(screen.getByText("FP 140")).toBeInTheDocument();
    expect(screen.getByText("FN 45")).toBeInTheDocument();
    expect(screen.getByText("TN 760")).toBeInTheDocument();
  });

  it("scores a customer live and alarms against the cursor threshold", async () => {
    mockFetch((path, init) => {
      if (path.endsWith("/demos/churn-sandbox/manifest")) return jsonResponse(MANIFEST);
      if (path.endsWith("/demos/churn-sandbox/payload")) return jsonResponse(PAYLOAD);
      if (path.endsWith("/projects/05-ml-pipeline-churn/score")) {
        expect(init?.method).toBe("POST");
        expect(JSON.parse(String(init?.body))).toEqual({
          features: { tenure_months: 3, monthly_charges: 95, contract: "month-to-month", internet_service: "fiber-optic" },
        });
        return jsonResponse({
          churn_probability: 0.64,
          decision: { alarm: true, threshold: 0.3, expected_cost_note: "n/a" },
        });
      }
      return jsonResponse({}, 404);
    });
    renderDemo();
    await screen.findByText("cost at t: 335");
    // preset chip fills the form; score live calls the serving endpoint
    fireEvent.click(screen.getByRole("button", { name: "at-risk fiber customer" }));
    fireEvent.click(screen.getByRole("button", { name: "score live" }));
    await waitFor(() => expect(screen.getByText("churn probability 64.0%")).toBeInTheDocument());
    expect(
      screen.getByText("alarm at t = 0.30 — this customer gets contacted"),
    ).toBeInTheDocument();
    expect(screen.getByText(/closest preset band: at-risk fiber customer/)).toBeInTheDocument();
  });

  it("shows a graceful notice when live scoring returns 503", async () => {
    mockFetch((path) => {
      if (path.endsWith("/demos/churn-sandbox/manifest")) return jsonResponse(MANIFEST);
      if (path.endsWith("/demos/churn-sandbox/payload")) return jsonResponse(PAYLOAD);
      if (path.endsWith("/score")) return jsonResponse({ detail: "serving artifacts not built" }, 503);
      return jsonResponse({}, 404);
    });
    renderDemo();
    await screen.findByText("cost at t: 335");
    fireEvent.click(screen.getByRole("button", { name: "score live" }));
    await waitFor(() =>
      expect(
        screen.getByText("live scoring unavailable — showing precomputed presets only"),
      ).toBeInTheDocument(),
    );
  });

  it("shows an error state when the payload cannot be loaded", async () => {
    mockFetch(() => jsonResponse({ detail: "no payload" }, 404));
    renderDemo();
    await waitFor(() =>
      expect(screen.getByText(/could not load the demo payload/i)).toBeInTheDocument(),
    );
  });

  it("pins a labeled customer marker on the cost curve when a preset is selected", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    const svg = await screen.findByRole("img", { name: "campaign cost over alarm threshold" });
    const markerTexts = () =>
      Array.from(svg.querySelectorAll("text")).map((el) => el.textContent);
    // no customer active by default — only the default-threshold marker label
    expect(markerTexts()).not.toContain("at-risk fiber");
    fireEvent.click(screen.getByRole("button", { name: "at-risk fiber customer" }));
    // marker line labeled with the short preset form appears in the SVG
    expect(markerTexts()).toContain("at-risk fiber");
    // switching presets moves the marker to the other customer
    fireEvent.click(screen.getByRole("button", { name: "sticky dsl customer" }));
    expect(markerTexts()).toContain("sticky dsl");
  });
});

describe("churn sandbox routing & links", () => {
  it("renders the demo at /demos/churn-sandbox inside App", async () => {
    mockFetch(payloadFetch());
    render(
      <MemoryRouter initialEntries={["/demos/churn-sandbox"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "churn threshold sandbox" }),
      ).toBeInTheDocument(),
    );
    // shell chrome: back link, linked experiment, footer band
    expect(screen.getByRole("link", { name: "← back to demos" })).toHaveAttribute(
      "href",
      "/projects#demos",
    );
    expect(screen.getByRole("link", { name: "05-ml-pipeline-churn" })).toHaveAttribute(
      "href",
      "/projects/05-ml-pipeline-churn",
    );
  });

  it("shows the live-demo link on the 05 project detail page", async () => {
    mockFetch((path) => {
      if (path.endsWith("/projects")) return jsonResponse([CHURN_PROJECT]);
      if (path.endsWith("/demos")) return jsonResponse([CHURN_DEMO_ENTRY]);
      return jsonResponse({ detail: "no story" }, 404);
    });
    render(
      <MemoryRouter initialEntries={["/projects/05-ml-pipeline-churn"]}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "▶ try the live demo" })).toHaveAttribute(
        "href",
        "/demos/churn-sandbox",
      ),
    );
  });

  it("omits the live-demo link when the registry has no demo for the project", async () => {
    mockFetch((path) => {
      if (path.endsWith("/projects")) return jsonResponse([CHURN_PROJECT]);
      if (path.endsWith("/demos")) return jsonResponse([]);
      return jsonResponse({ detail: "no story" }, 404);
    });
    render(
      <MemoryRouter initialEntries={["/projects/05-ml-pipeline-churn"]}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByRole("link", { name: "[code]" })).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "▶ try the live demo" })).toBeNull();
  });

  it("omits the live-demo link when the registry fetch fails", async () => {
    mockFetch((path) => {
      if (path.endsWith("/projects")) return jsonResponse([CHURN_PROJECT]);
      return jsonResponse({ detail: "registry down" }, 503);
    });
    render(
      <MemoryRouter initialEntries={["/projects/05-ml-pipeline-churn"]}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByRole("link", { name: "[code]" })).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "▶ try the live demo" })).toBeNull();
  });
});
