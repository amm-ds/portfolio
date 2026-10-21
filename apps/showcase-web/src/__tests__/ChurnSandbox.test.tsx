import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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

/** jsdom lacks ResizeObserver; derive the measurement from the (possibly
 * stubbed) layout box so pointer tests exercise the measured code path.
 * Elements with a zero box (default jsdom layout) stay on the static
 * fallback sizes. */
function stubResizeObserver() {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      private cb: ResizeObserverCallback;
      constructor(cb: ResizeObserverCallback) {
        this.cb = cb;
      }
      observe(el: Element) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          this.cb(
            [{ target: el, contentRect: rect } as unknown as ResizeObserverEntry],
            this as unknown as ResizeObserver,
          );
        }
      }
      unobserve() {}
      disconnect() {}
    },
  );
}

beforeEach(() => {
  stubResizeObserver();
});

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
    // honest-numbers lines in the evidence drawer (models used column)
    const drawer = document.querySelector(".wb-evidence")!;
    expect(drawer.textContent).toContain("selected_model_calibrated");
    expect(drawer.textContent).toContain("roc-auc 0.8300");
  });

  it("flips the cost math when the FN slider moves", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await waitFor(() => expect(screen.getByText("cost at t: 335")).toBeInTheDocument());
    // fn_ratio 5 → 1: cost = fp + fn; at t = 0.3 → 210 + 25 = 235 vs 0.5 → 140 + 45 = 185
    fireEvent.change(screen.getByLabelText(/FP\/FN cost ratio/i), { target: { value: "1" } });
    expect(screen.getByText("cost at t: 235")).toBeInTheDocument();
    expect(screen.getByText("cost at 0.5: 185")).toBeInTheDocument();
    expect(screen.getByText("costs 50 vs 0.5")).toBeInTheDocument();
  });

  it("drives the filled slider track through the inline --fill style", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await waitFor(() => expect(screen.getByText("cost at t: 335")).toBeInTheDocument());
    const slider = screen.getByLabelText(/FP\/FN cost ratio/i) as HTMLInputElement;
    // fn 5 on the 1–10 range → (5−1)/9 of the track filled
    expect(slider.style.getPropertyValue("--fill")).toBe(`${((5 - 1) / 9) * 100}%`);
    // extremes reach the very ends of the track
    fireEvent.change(slider, { target: { value: "1" } });
    expect(slider.style.getPropertyValue("--fill")).toBe("0%");
    fireEvent.change(slider, { target: { value: "10" } });
    expect(slider.style.getPropertyValue("--fill")).toBe("100%");
  });

  it("renders two capitalized notice tiles that both react to the FN slider", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("cost at t: 335");
    const strip = document.querySelector(".wb-notice-strip")!;
    expect(strip).not.toBeNull();
    const tiles = strip.querySelectorAll(".wb-notice");
    expect(tiles).toHaveLength(2);
    // cursor starts at the committed threshold t = 0.3, which is cost-optimal
    // at fn = 5 in the fixture
    expect(tiles[0].textContent).toContain(
      "At 5× a miss, catching one more churner here costs ~7 extra false alarms",
    );
    expect(tiles[1].textContent).toContain("This is the cheapest cutoff for a 5× miss cost");
    for (const tile of Array.from(tiles)) {
      expect(tile.textContent!.replace("▸", "").trim()[0]).toMatch(/[A-Z]/);
    }
    // fn 5 → 1 moves the optimum to t = 0.9 and rewrites both tiles
    fireEvent.change(screen.getByLabelText(/FP\/FN cost ratio/i), { target: { value: "1" } });
    const after = strip.querySelectorAll(".wb-notice");
    expect(after[0].textContent).toContain(
      "At 1× a miss, catching one more churner here costs ~7 extra false alarms",
    );
    expect(after[1].textContent).toContain(
      "The cheapest cutoff at 1× is t = 0.90 — above your cursor by 0.60",
    );
    for (const tile of Array.from(after)) {
      expect(tile.textContent!.replace("▸", "").trim()[0]).toMatch(/[A-Z]/);
    }
  });

  it("keeps control group labels outside the input boxes, ahead of them in the DOM", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("cost at t: 335");
    const groups = document.querySelectorAll(".wb-control-group");
    expect(groups).toHaveLength(3);
    const labelTexts: string[] = [];
    for (const group of Array.from(groups)) {
      const label = group.querySelector(".wb-rail-title");
      const box = group.querySelector(".demo-control");
      expect(label).not.toBeNull();
      expect(box).not.toBeNull();
      // label element precedes the input box in the DOM
      expect(
        label!.compareDocumentPosition(box!) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
      labelTexts.push(label!.textContent!);
    }
    expect(labelTexts).toEqual(["FP/FN cost ratio", "Preset customers", "Score a customer"]);
    for (const text of labelTexts) {
      expect(text[0]).toMatch(/[A-Z]/);
    }
    // the slider box holds the range input plus the live multiplier badge
    const sliderBox = document.querySelector(".wb-group-slider .demo-control")!;
    expect(sliderBox.querySelector('input[type="range"]')).not.toBeNull();
    expect(sliderBox.querySelector(".wb-value-badge")!.textContent).toBe("5×");
  });

  it("renders the canvas chart footer with full commentary and no fig id or clamp", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("cost at t: 335");
    const band = document.querySelector(".wb-canvas-slot footer.figure-card-band")!;
    expect(band).not.toBeNull();
    expect(band.querySelector(".figure-id")).toBeNull();
    const comment = band.querySelector(".figure-comment")!;
    expect(comment.className).not.toContain("line-clamp");
    // the full two-sentence commentary renders untrimmed
    expect(comment.textContent).toContain("Cost = FP + N×FN on the untouched holdout");
    expect(comment.textContent).toContain("the star marks the threshold the pipeline committed to");
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
    // the submit button sits at the bottom of the scorer card, in the foot row
    const scorer = document.querySelector(".wb-scorer")!;
    expect(scorer).not.toBeNull();
    const foot = scorer.querySelector(".wb-scorer-foot")!;
    expect(foot).toContain(screen.getByRole("button", { name: "score live" }));
    // preset chip fills the form; score live calls the serving endpoint
    fireEvent.click(screen.getByRole("button", { name: "at-risk fiber customer" }));
    fireEvent.click(screen.getByRole("button", { name: "score live" }));
    // the result renders in the full-width strip below the main row, outside
    // the scorer box (the preset chip remounts the card via key={presetKey})
    await waitFor(() => {
      const strip = document.querySelector(".wb-score-result")!;
      expect(strip).not.toBeNull();
      expect(strip.textContent).toContain("64.0%");
      expect(strip.textContent).toContain("Alarm at t = 0.30 — this customer gets contacted");
      expect(strip.textContent).toContain("Closest preset band: at-risk fiber customer");
    });
    const scorerBox = document.querySelector(".wb-scorer")!;
    expect(scorerBox.querySelector(".demo-score-result")).toBeNull();
    const mainRow = document.querySelector(".wb-main")!;
    const strip = document.querySelector(".wb-score-result")!;
    expect(
      mainRow.compareDocumentPosition(strip) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
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
        screen.getByText("Live scoring unavailable — showing precomputed presets only"),
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

  it("keeps the scorer form in the controls column, with no under strip", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("cost at t: 335");
    const controls = document.querySelector(".wb-controls")!;
    expect(controls).not.toBeNull();
    // scorer card (and its live button) live in the rail, below the presets
    const scorer = controls.querySelector(".wb-scorer")!;
    expect(scorer).not.toBeNull();
    expect(controls.contains(screen.getByRole("button", { name: "score live" }))).toBe(true);
    // the full-width under strip is gone (workbench keeps the slot as optional API)
    expect(document.querySelector(".wb-under")).toBeNull();
    expect(document.querySelector(".wb-scorer-strip")).toBeNull();
  });

  it("gives all three secondary panels a figure footer with full commentary, no fig id", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("cost at t: 335");
    const panels = document.querySelectorAll(".wb-secondary-panel");
    expect(panels).toHaveLength(3);
    for (const panel of panels) {
      const band = panel.querySelector("footer.figure-card-band");
      expect(band).not.toBeNull();
      // no `fig ::` id line, no line-clamp trimming — commentary renders full
      expect(band!.querySelector(".figure-id")).toBeNull();
      const comment = band!.querySelector(".figure-comment")!;
      expect(comment).not.toBeNull();
      expect(comment.textContent!.length).toBeGreaterThan(40);
      expect(comment.className).not.toContain("line-clamp");
    }
    // the cost-composition panel is the third one and still labeled
    expect(screen.getByText("cost composition")).toBeInTheDocument();
  });

  it("cost-composition panel rescales with the FN slider and tracks the cursor", async () => {
    mockFetch(payloadFetch());
    stubSvgRect();
    renderDemo();
    const svg = await screen.findByRole("img", { name: "cost composition over alarm threshold" });
    const fnPath = () => svg.querySelector('[data-layer="fn"]')!.getAttribute("d");
    const cursorX = () => svg.querySelector('[data-layer="cursor"]')!.getAttribute("x1");
    // cursor starts at the committed threshold 0.3 (stubbed 720px box:
    // 38 + 0.25 × 674 = 206.5 in viewBox coords)
    expect(Number(cursorX())).toBeCloseTo(206.5, 5);
    const fnBefore = fnPath();
    expect(fnBefore).not.toBeNull();
    // FN slider 5 → 9 rescales the stacked FN area
    fireEvent.change(screen.getByLabelText(/FP\/FN cost ratio/i), { target: { value: "9" } });
    expect(fnPath()).not.toBe(fnBefore);
    // dragging the main chart cursor to t = 0.7 moves the marker
    const mainSvg = screen.getByRole("img", { name: "campaign cost over alarm threshold" });
    fireEvent(mainSvg, new MouseEvent("pointerdown", { bubbles: true, clientX: 518, buttons: 1 }));
    expect(screen.getByText("threshold t = 0.70")).toBeInTheDocument();
    expect(Number(cursorX())).toBeCloseTo(543.5, 5);
  });

  it("keeps the calibration chart out of the demo (results use metric tags)", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("cost at t: 335");
    const band = document.querySelector(".wb-secondary")!;
    expect(band.querySelector('svg[aria-label="calibration scatter"]')).toBeNull();
    const more = document.querySelector(".wb-more")!;
    expect(more.querySelector('svg[aria-label="calibration scatter"]')).toBeNull();
    expect(more.querySelectorAll(".wb-tag").length).toBeGreaterThanOrEqual(3);
    // evidence content is organized in two labeled columns: models used left,
    // metrics results right; the linked experiment sits on top, full width
    const cols = more.querySelectorAll(".wb-evidence-col");
    expect(cols).toHaveLength(2);
    expect(cols[0].textContent).toContain("interpretation");
    expect(cols[1].textContent).toContain("models used");
    expect(cols[1].textContent).toContain("metrics results");
    expect(cols[1].textContent).toContain("$335");
    expect(more.querySelector(".wb-evidence-linked")!.textContent).toContain(
      "05-ml-pipeline-churn",
    );
    expect(more.textContent).toContain("more information");
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
    // shell chrome: back link, linked experiment, footer band — the experiment
    // link appears both in the drawer chrome and in the evidence column
    expect(screen.getByRole("link", { name: "← back to demos" })).toHaveAttribute(
      "href",
      "/projects#demos",
    );
    const experimentLinks = screen.getAllByRole("link", { name: "05-ml-pipeline-churn" });
    expect(experimentLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of experimentLinks) {
      expect(link).toHaveAttribute("href", "/projects/05-ml-pipeline-churn");
    }
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
