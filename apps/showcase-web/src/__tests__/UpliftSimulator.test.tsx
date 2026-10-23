import { readFileSync } from "node:fs";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { DemoManifest, UpliftPayload } from "../demos/types";
import UpliftSimulator from "../demos/uplift-simulator/UpliftSimulator";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// 7 costs × 7 fractions synthetic lattice, values in total campaign profit ($).
const COSTS = [0.01, 0.05, 0.1, 0.2, 0.31, 0.4, 0.5];
const FRACTIONS = [0.1, 0.2, 0.25, 0.3, 0.5, 0.75, 1.0];
const BEST_ROWS = [
  [100000, 250000, 380000, 370000, 300000, 150000, 50000],
  [90000, 230000, 360000, 350000, 280000, 140000, 45000],
  [80000, 210000, 340000, 330000, 260000, 130000, 40000],
  [70000, 200000, 320000, 310000, 240000, 120000, 35000],
  [65000, 190000, 310000, 300000, 230000, 115000, 30000],
  [60000, 180000, 300000, 290000, 220000, 110000, 25000],
  [55000, 170000, 290000, 280000, 210000, 105000, 20000],
];
const offsetRows = (rows: number[][], delta: number): number[][] =>
  rows.map((row) => row.map((v) => v + delta));

// 1% arm-mix lattice: top of the ranking is mens-heavy, the full-send endpoint
// matches scalars.recommended_arm_shares (mens .76 / womens .20 / none .04).
const MIX_FRACTIONS = Array.from({ length: 100 }, (_, i) => (i + 1) / 100);
const ARM_MIX = {
  fractions: MIX_FRACTIONS,
  shares: {
    mens: MIX_FRACTIONS.map((f) => 0.95 - 0.19 * f),
    womens: MIX_FRACTIONS.map((f) => 0.03 + 0.17 * f),
    none: MIX_FRACTIONS.map((f) => 0.02 + 0.02 * f),
  },
};

/** Payload fixture mirroring the real `demo_payload.json` contract (small grid). */
const PAYLOAD: UpliftPayload = {
  schema_version: 1,
  demo: "uplift-simulator",
  project: "10-uplift-experimentation",
  n_customers: 1000,
  scalars: {
    n_customers: 1000,
    revenue_per_conversion: 100,
    cost_default: 0.01,
    policy_budget: 0.25,
    incremental_conversions_full_send_model_estimated: { mens: 442.62, womens: 400 },
    incremental_conversions_full_send_best_arm: 586.78,
    per_arm_qini: {
      mens: {
        qini_coefficient: 12.03,
        qini_ci: [-0.47, 24.21],
        incremental_conversions_full: 145,
        incremental_conversions_full_ci: [108, 182],
        n_arm: 333,
        n_control: 334,
      },
      womens: {
        qini_coefficient: 3.37,
        qini_ci: [-6.78, 13.75],
        incremental_conversions_full: 66.5,
        incremental_conversions_full_ci: [40, 93],
        n_arm: 334,
        n_control: 333,
      },
    },
    recommended_arm_shares: { mens: 0.76, womens: 0.2, none: 0.04 },
    break_even: {
      two_arm_committed: { cost_per_email: 0.29989, source: "fixture" },
      multi_arm_best_arm: { cost_per_email: 0.30801, vs: "mail_everyone_mens", policy_budget: 0.25, source: "fixture" },
    },
    // slope −1,000 per $1: mail-everyone sends 1,000 emails whatever the cost
    mail_everyone_profit: {
      mens: {
        "0.01": 500000,
        "0.05": 460000,
        "0.10": 410000,
        "0.20": 310000,
        "0.31": 199000,
        "0.40": 110000,
        "0.50": 10000,
      },
      womens: {
        "0.01": 300000,
        "0.05": 260000,
        "0.10": 210000,
        "0.20": 110000,
        "0.31": -1000,
        "0.40": -90000,
        "0.50": -190000,
      },
    },
    model_estimated_note:
      "Multi-arm read is MODEL-ESTIMATED at the policy level: incremental conversions are summed predicted uplift over the targeted set, not observed counterfactuals.",
  },
  profit_grid: {
    costs: COSTS,
    fractions: FRACTIONS,
    policies: {
      best_arm: {
        profit: BEST_ROWS,
        ci: { lo: offsetRows(BEST_ROWS, -20000), hi: offsetRows(BEST_ROWS, 20000) },
      },
      single_arm: { profit: offsetRows(BEST_ROWS, -60000) },
      random: {
        profit: [
          [4000, 90000, 140000, 180000, 200000, 190000, 150000],
          [2000, 80000, 135000, 175000, 195000, 185000, 145000],
          [0, 70000, 130000, 170000, 190000, 180000, 140000],
          [-2000, 60000, 120000, 160000, 180000, 170000, 130000],
          [-3100, 55000, 115000, 155000, 175000, 165000, 125000],
          [-4000, 50000, 110000, 150000, 170000, 160000, 120000],
          [-5000, 45000, 105000, 145000, 165000, 155000, 115000],
        ],
        ci: {
          lo: offsetRows(
            [
              [4000, 90000, 140000, 180000, 200000, 190000, 150000],
              [2000, 80000, 135000, 175000, 195000, 185000, 145000],
              [0, 70000, 130000, 170000, 190000, 180000, 140000],
              [-2000, 60000, 120000, 160000, 180000, 170000, 130000],
              [-3100, 55000, 115000, 155000, 175000, 165000, 125000],
              [-4000, 50000, 110000, 150000, 170000, 160000, 120000],
              [-5000, 45000, 105000, 145000, 165000, 155000, 115000],
            ],
            -15000,
          ),
          hi: offsetRows(
            [
              [4000, 90000, 140000, 180000, 200000, 190000, 150000],
              [2000, 80000, 135000, 175000, 195000, 185000, 145000],
              [0, 70000, 130000, 170000, 190000, 180000, 140000],
              [-2000, 60000, 120000, 160000, 180000, 170000, 130000],
              [-3100, 55000, 115000, 155000, 175000, 165000, 125000],
              [-4000, 50000, 110000, 150000, 170000, 160000, 120000],
              [-5000, 45000, 105000, 145000, 165000, 155000, 115000],
            ],
            15000,
          ),
        },
      },
    },
    n_boot: 200,
    seed: 2000,
    alpha: 0.05,
    model_estimated: true,
    note: "fixture",
  },
  qini_points: {
    mens: {
      fractions: [0, 0.5, 1],
      incremental: [0, 80, 145],
      random_fractions: [0, 1],
      random_incremental: [0, 145],
      qini_coefficient: 12.03,
      qini_ci: [-0.47, 24.21],
    },
    womens: {
      fractions: [0, 0.5, 1],
      incremental: [0, 30, 66.5],
      random_fractions: [0, 1],
      random_incremental: [0, 66.5],
      qini_coefficient: 3.37,
      qini_ci: [-6.78, 13.75],
    },
    random: { fractions: [0, 1], incremental: [0, 586.78], note: "fixture" },
  },
  arm_mix_by_fraction: ARM_MIX,
  segments: {
    "Mens E-Mail": {
      n: 334,
      visit_rate: 0.18,
      conversion_rate: 0.0125,
      mean_spend: 1.42,
      incremental_conversions_full_send_model_estimated: { mens: 148.47, womens: 65.18 },
    },
    "Womens E-Mail": {
      n: 334,
      visit_rate: 0.15,
      conversion_rate: 0.0088,
      mean_spend: 1.08,
      incremental_conversions_full_send_model_estimated: { mens: 146.42, womens: 63.52 },
    },
    "No E-Mail": {
      n: 332,
      visit_rate: 0.11,
      conversion_rate: 0.0057,
      mean_spend: 0.65,
      incremental_conversions_full_send_model_estimated: { mens: 147.73, womens: 63.64 },
    },
  },
};

/** Manifest fixture mirroring projects/10-uplift-experimentation/demo.yaml. */
const MANIFEST: DemoManifest = {
  id: "uplift-simulator",
  title: "uplift policy simulator",
  hook: "Move the send cost and the targeting budget — watch when personalized targeting beats mailing everyone.",
  project: "10-uplift-experimentation",
  group: "spend marketing budget",
  skills: ["causal inference", "uplift modeling", "experimentation"],
  modes: ["browser"],
  hero: null,
  scenarios: [
    { name: "base", controls: { cost: 0.05, budget: 0.25 } },
    { name: "break-even-discovery", controls: { cost: 0.31, budget: 0.5 } },
    { name: "high-cost", controls: { cost: 0.5, budget: 0.35 } },
  ],
  live_endpoints: [],
  payload: {
    path: "reports/demo_payload.json",
    schema_version: 1,
    required_keys: [
      "schema_version",
      "demo",
      "project",
      "n_customers",
      "scalars",
      "profit_grid",
      "qini_points",
      "arm_mix_by_fraction",
      "segments",
    ],
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
    if (path.endsWith("/demos/uplift-simulator/manifest")) return jsonResponse(MANIFEST);
    if (path.endsWith("/demos/uplift-simulator/payload")) return jsonResponse(PAYLOAD);
    return jsonResponse({}, 404);
  };
}

function renderDemo() {
  return render(
    <MemoryRouter>
      <UpliftSimulator />
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
 * stubbed) layout box so pointer tests exercise the measured code path. */
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

describe("UpliftSimulator", () => {
  it("shows a loading state then the demo title, readouts and KPIs", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    expect(screen.getByText("loading demo…")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "uplift policy simulator" }),
      ).toBeInTheDocument(),
    );
    // base scenario: cost $0.05 (grid idx 1), budget 25% (grid idx 2)
    expect(screen.getByText("cost $0.05/email")).toBeInTheDocument();
    expect(screen.getByText("budget 25%")).toBeInTheDocument();
    expect(screen.getByText("best arm $360.0k")).toBeInTheDocument();
    // mail-everyone-mens at $0.05 is 460k → beats best-arm 360k by 100k
    expect(screen.getByText("mail everyone mens +$100.0k")).toBeInTheDocument();
    // KPIs at the cursor
    expect(screen.getByText("profit at budget")).toBeInTheDocument();
    expect(screen.getByText("$360.0k")).toBeInTheDocument();
    expect(screen.getByText("vs random +$225.0k · 95% CI band")).toBeInTheDocument();
    // incremental conversions = (360000 + 0.25·1000·0.05)/100 ≈ 3600
    expect(screen.getByText("3600")).toBeInTheDocument();
    // break-even scalars
    expect(screen.getByText("$0.31")).toBeInTheDocument();
    expect(screen.getByText("committed two-arm $0.30 · best-arm $0.31")).toBeInTheDocument();
    // customers targeted = 1000 × 0.25
    expect(screen.getByText("250")).toBeInTheDocument();
    expect(screen.getByText("of 1,000 scored customers")).toBeInTheDocument();
  });

  it("flips the crossover notice and winner chip as the cost slider moves", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("best arm $360.0k");
    const strip = document.querySelector(".wb-notice-strip")!;
    const tiles = strip.querySelectorAll(".wb-notice");
    expect(tiles).toHaveLength(2);
    // cheap cost: mailing everyone wins; peak hint cites 25% targeting
    expect(tiles[0].textContent).toContain("mailing everyone wins");
    expect(tiles[0].textContent).toContain("$0.05/email");
    expect(tiles[1].textContent).toContain("sits near 25% targeting");
    for (const tile of Array.from(tiles)) {
      expect(tile.textContent!.replace("▸", "").trim()[0]).toMatch(/[A-Z]/);
    }
    // $0.40 (grid idx 5): best-arm 300k vs mail-everyone 110k → targeting wins
    fireEvent.change(screen.getByLabelText(/cost per email/i), { target: { value: "0.40" } });
    expect(screen.getByText("cost $0.40/email")).toBeInTheDocument();
    expect(screen.getByText("best arm $300.0k")).toBeInTheDocument();
    expect(screen.getByText("best-arm targeting +$190.0k")).toBeInTheDocument();
    const after = strip.querySelectorAll(".wb-notice");
    expect(after[0].textContent).toContain("best-arm targeting beats mailing everyone");
    expect(after[0].textContent).toContain("$0.40/email");
  });

  it("drives the filled slider track through the inline --fill style", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("best arm $360.0k");
    const slider = screen.getByLabelText(/cost per email/i) as HTMLInputElement;
    // $0.05 on the $0.01–$0.50 range → (0.05−0.01)/0.49 of the track filled
    expect(slider.style.getPropertyValue("--fill")).toBe(`${((0.05 - 0.01) / 0.49) * 100}%`);
    fireEvent.change(slider, { target: { value: "0.01" } });
    expect(slider.style.getPropertyValue("--fill")).toBe("0%");
    fireEvent.change(slider, { target: { value: "0.5" } });
    expect(slider.style.getPropertyValue("--fill")).toBe("100%");
    expect(screen.getByText("cost $0.50/email")).toBeInTheDocument();
  });

  it("moves the targeting budget via pointer events on the frontier", async () => {
    mockFetch(payloadFetch());
    stubSvgRect();
    renderDemo();
    const svg = await screen.findByRole("img", { name: "campaign profit over targeted fraction" });
    // qini capture + arm-mix readouts start at the 25% default
    const qiniChip = screen.getByTestId("qini-capture");
    const mixChip = screen.getByTestId("arm-mix-targeted");
    expect(qiniChip.textContent).toBe(
      "at 25% targeting: mens captures 40.0 vs random's 146.7 (−106.7)",
    );
    expect(mixChip.textContent).toBe("top 25%: 90% mens · 7% womens · 3% none");
    // stubbed 720px box, PAD.l 56, plot 646 wide: clientX 343 → fraction 0.5
    fireEvent(svg, new MouseEvent("pointerdown", { bubbles: true, clientX: 343, buttons: 1 }));
    expect(screen.getByText("budget 50%")).toBeInTheDocument();
    expect(screen.getByText("500")).toBeInTheDocument(); // 1000 × 0.5 targeted
    expect(screen.getByText("best arm $280.0k")).toBeInTheDocument();
    // both secondary-panel readouts follow the cursor
    expect(qiniChip.textContent).toBe(
      "at 50% targeting: mens captures 80.0 vs random's 293.4 (−213.4)",
    );
    expect(mixChip.textContent).toBe("top 50%: 86% mens · 12% womens · 3% none");
  });

  it("applies scenario presets from the URL query string", async () => {
    mockFetch(payloadFetch());
    // useControlState reads window.location, not the router location
    window.history.replaceState(null, "", "/demos/uplift-simulator?cost=0.31&budget=0.5");
    render(
      <MemoryRouter initialEntries={["/demos/uplift-simulator?cost=0.31&budget=0.5"]}>
        <UpliftSimulator />
      </MemoryRouter>,
    );
    // break-even-discovery scenario: $0.31/email, 50% budget
    await screen.findByText("cost $0.31/email");
    expect(screen.getByText("budget 50%")).toBeInTheDocument();
    expect(screen.getByText("best arm $230.0k")).toBeInTheDocument();
  });

  it("renders three secondary panels with full commentary and no fig id", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("best arm $360.0k");
    const panels = document.querySelectorAll(".wb-secondary-panel");
    expect(panels).toHaveLength(3);
    for (const panel of Array.from(panels)) {
      const band = panel.querySelector("footer.figure-card-band");
      expect(band).not.toBeNull();
      expect(band!.querySelector(".figure-id")).toBeNull();
      const comment = band!.querySelector(".figure-comment")!;
      expect(comment).not.toBeNull();
      expect(comment.textContent!.length).toBeGreaterThan(40);
      expect(comment.className).not.toContain("line-clamp");
    }
    // qini panel cites both coefficients and the honest CI-span caveat
    expect(panels[0].textContent).toContain("mens qini 12.03");
    expect(panels[0].textContent).toContain("womens 3.37");
    expect(panels[0].textContent).toContain("ranking not established");
    // arm mix bars show shares and segment conversion rates
    expect(panels[2].textContent).toContain("76%");
    expect(panels[2].textContent).toContain("1.25%");
  });

  it("keeps the evidence drawer in two columns with metric tags and arm shares", async () => {
    mockFetch(payloadFetch());
    renderDemo();
    await screen.findByText("best arm $360.0k");
    const more = document.querySelector(".wb-more")!;
    expect(more).not.toBeNull();
    const cols = more.querySelectorAll(".wb-evidence-col");
    expect(cols).toHaveLength(2);
    expect(cols[0].textContent).toContain("interpretation");
    expect(cols[0].textContent).toContain("honest caveats");
    // the model-estimated note rides along verbatim
    expect(cols[0].textContent).toContain(PAYLOAD.scalars.model_estimated_note);
    expect(cols[1].textContent).toContain("models used");
    expect(cols[1].textContent).toContain("T-learners");
    expect(cols[1].textContent).toContain("metrics results");
    expect(cols[1].textContent).toContain("qini mens 12.03");
    expect(cols[1].textContent).toContain("qini womens 3.37");
    expect(cols[1].textContent).toContain("break-even $0.31");
    expect(cols[1].textContent).toContain("arm none 4%");
    expect(more.querySelector(".wb-evidence-linked")!.textContent).toContain(
      "10-uplift-experimentation",
    );
  });

  it("shows an error state when the payload cannot be loaded", async () => {
    mockFetch(() => jsonResponse({ detail: "no payload" }, 404));
    renderDemo();
    await waitFor(() =>
      expect(screen.getByText(/could not load the demo payload/i)).toBeInTheDocument(),
    );
  });
});

describe("uplift simulator routing", () => {
  it("renders the demo at /demos/uplift-simulator inside App", async () => {
    mockFetch(payloadFetch());
    render(
      <MemoryRouter initialEntries={["/demos/uplift-simulator"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "uplift policy simulator" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: "← back to demos" })).toHaveAttribute(
      "href",
      "/projects#demos",
    );
    const experimentLinks = screen.getAllByRole("link", { name: "10-uplift-experimentation" });
    expect(experimentLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of experimentLinks) {
      expect(link).toHaveAttribute("href", "/projects/10-uplift-experimentation");
    }
  });
});

describe("uplift payload contract", () => {
  /** The committed payload must keep matching the UpliftPayload type the UI
   * is built on (field names, grid dims, string-keyed mail-everyone map). */
  it("the committed demo_payload.json satisfies the UpliftPayload shape", () => {
    const raw = readFileSync(
      // vitest runs from apps/showcase-web — repo root is two levels up
      `${process.cwd()}/../../projects/10-uplift-experimentation/reports/demo_payload.json`,
      "utf-8",
    );
    const payload = JSON.parse(raw) as UpliftPayload;
    // every key the manifest declares required
    for (const key of MANIFEST.payload.required_keys) {
      expect(payload, key).toHaveProperty(key);
    }
    const grid = payload.profit_grid;
    expect(grid.costs).toHaveLength(50);
    expect(grid.fractions).toHaveLength(100);
    for (const policy of ["best_arm", "single_arm", "random"] as const) {
      expect(grid.policies[policy].profit).toHaveLength(50);
      expect(grid.policies[policy].profit[0]).toHaveLength(100);
    }
    expect(grid.policies.best_arm.ci?.lo).toHaveLength(50);
    expect(grid.policies.random.ci?.hi).toHaveLength(50);
    // mail-everyone maps use two-decimal string keys across the cost grid
    for (const c of grid.costs) {
      expect(payload.scalars.mail_everyone_profit.mens).toHaveProperty(c.toFixed(2));
      expect(payload.scalars.mail_everyone_profit.womens).toHaveProperty(c.toFixed(2));
    }
    // per-arm qini + segments + break-even scalars the UI reads
    expect(payload.qini_points.mens.qini_coefficient).toBeCloseTo(12.03, 1);
    expect(payload.qini_points.womens.qini_ci).toHaveLength(2);
    expect(payload.scalars.recommended_arm_shares.mens).toBeCloseTo(0.76, 1);
    expect(payload.scalars.break_even.multi_arm_best_arm.cost_per_email).toBeCloseTo(0.31, 1);
    expect(Object.keys(payload.segments)).toEqual([
      "Mens E-Mail",
      "Womens E-Mail",
      "No E-Mail",
    ]);
    expect(typeof payload.scalars.model_estimated_note).toBe("string");
    // arm-mix lattice: 100 shares per arm, summing to 1, endpoint = full send
    const mix = payload.arm_mix_by_fraction;
    expect(mix.fractions).toHaveLength(100);
    for (const key of ["mens", "womens", "none"] as const) {
      expect(mix.shares[key]).toHaveLength(100);
    }
    for (let i = 0; i < 100; i++) {
      const total = mix.shares.mens[i] + mix.shares.womens[i] + mix.shares.none[i];
      expect(total).toBeCloseTo(1, 5);
    }
    const shares = payload.scalars.recommended_arm_shares;
    expect(mix.shares.mens[99]).toBeCloseTo(shares.mens, 4);
    expect(mix.shares.womens[99]).toBeCloseTo(shares.womens, 4);
    expect(mix.shares.none[99]).toBeCloseTo(shares.none, 4);
  });
});
