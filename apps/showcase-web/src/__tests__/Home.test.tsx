import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AVAILABILITY } from "../config";
import { Home } from "../pages/Home";

const LIVE_REGISTRY = [
  {
    id: "forecast-workbench",
    title: "demand forecast workbench",
    hook: "Pick a store-product series and compare candidates on scored-once origins.",
    group: "plan operations",
    href: "/demos/forecast-workbench",
    project: "02-demand-forecasting",
    status: "live",
    hero: {
      label: "pooled test WAPE — ensemble vs seasonal-naive floor",
      value: "0.498 vs 0.603",
      ci: "paired bootstrap CI [−0.115, −0.095]; 89.3% per-series win rate",
    },
  },
  {
    id: "churn-sandbox",
    title: "churn threshold sandbox",
    hook: "Move the alarm threshold and watch the saved budget change.",
    group: "retain customers",
    href: "/demos/churn-sandbox",
    project: "05-ml-pipeline-churn",
    status: "live",
    hero: {
      label: "decision cost per 1,400 customers",
      value: "$601 vs $1,035 naive",
      ci: "paired bootstrap CI [−485, −343]",
    },
  },
];

function mockReducedMotion() {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: true,
      media: "",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
}

beforeEach(() => {
  mockReducedMotion();
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("API unreachable")));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderHome() {
  return render(
    <MemoryRouter>
      <Home />
    </MemoryRouter>,
  );
}

describe("Home (consulting brief, wave 7)", () => {
  it("leads with the consultant positioning line", () => {
    renderHome();
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.textContent).toBe("Independent AI & ML Consultant");
    expect(screen.getByText(/from experiment to production/i)).toBeInTheDocument();
    expect(screen.queryByText(/senior/i)).toBeNull();
  });

  it("has a primary demo CTA and a secondary experiment CTA", () => {
    renderHome();
    const primary = screen.getByRole("link", { name: "Try a live demo" });
    expect(primary).toHaveAttribute("href", "/demos/forecast-workbench");
    const secondary = screen.getByRole("link", { name: "Read an experiment" });
    expect(secondary).toHaveAttribute("href", "/projects/02-demand-forecasting");
  });

  it("renders three proof tiles with registry hero metrics (static fallback)", async () => {
    renderHome();
    const tiles = await screen.findAllByText(/vs/i);
    expect(tiles.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("0.498 vs 0.603")).toBeInTheDocument();
    expect(screen.getByText("$601 vs $1,035 naive")).toBeInTheDocument();
    expect(screen.getByText("paired bootstrap CI [−485, −343]")).toBeInTheDocument();
    // config-sourced third tile fills the strip
    expect(screen.getByText("availability")).toBeInTheDocument();
    expect(screen.getByText(AVAILABILITY.status)).toBeInTheDocument();
    const strip = screen.getByTestId("proof-tiles");
    expect(strip.children).toHaveLength(3);
  });

  it("uses live registry hero fields when the API responds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => LIVE_REGISTRY }),
    );
    renderHome();
    // flush both registry fetches so no re-render invalidates element refs
    await act(async () => {});
    // long label trimmed at the em-dash
    expect(screen.getByText("pooled test WAPE")).toBeInTheDocument();
    expect(screen.getByText("0.498 vs 0.603")).toBeInTheDocument();
    // CI line trimmed at the semicolon
    expect(screen.getByText("paired bootstrap CI [−0.115, −0.095]")).toBeInTheDocument();
  });

  it("renders the featured demo strip linking into both demos", async () => {
    renderHome();
    // flush both registry fetches so no re-render invalidates element refs
    await act(async () => {});
    const forecast = screen.getByRole("link", { name: /\$ demand forecast workbench/i });
    expect(forecast).toHaveAttribute("href", "/demos/forecast-workbench");
    const churn = screen.getByRole("link", { name: /\$ churn threshold sandbox/i });
    expect(churn).toHaveAttribute("href", "/demos/churn-sandbox");
  });

  it("types the script and carries the full message as the terminal's accessible name", () => {
    renderHome();
    expect(screen.getByText("alejandro@amm-ds: ~")).toBeInTheDocument();
    expect(screen.getByText("data scientist & ml engineer")).toBeInTheDocument();
    expect(
      screen.getByText("agentic ai · forecasting · machine learning · optimization · data engineering"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("pydantic-ai · pytorch · polars · scikit-learn · plotly · dvc"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("reproducible pipelines · honest baselines · production-grade code"),
    ).toBeInTheDocument();
    // full typed content exists in the DOM from first render via aria-label
    const term = document.querySelector(".hero-terminal")!;
    expect(term.getAttribute("role")).toBe("img");
    expect(term.getAttribute("aria-label")).toContain("$ whoami");
    expect(term.getAttribute("aria-label")).toContain("data scientist & ml engineer");
    // animated copy is aria-hidden
    expect(term.firstElementChild!.getAttribute("aria-hidden")).toBe("true");
  });

  it("CTA points to /contact", () => {
    renderHome();
    const cta = screen.getByRole("link", { name: "→ /contact" });
    expect(cta.getAttribute("href")).toBe("/contact");
  });

  it("renders the where-to-go trio as three identical cards", () => {
    renderHome();
    const cards = document.querySelectorAll(".go-card");
    expect(cards).toHaveLength(5); // 2 featured demos + 3 where-to-go
    for (const { to, label } of [
      { to: "/projects", label: "projects" },
      { to: "/services", label: "services" },
      { to: "/contact", label: "contact" },
    ]) {
      const link = screen.getByRole("link", { name: new RegExp(`\\$ ${label}`, "i") });
      expect(link).toHaveAttribute("href", to);
    }
  });

  it("availability line reads from config", () => {
    renderHome();
    const status = document.querySelector(".home-status")!;
    expect(status).not.toBeNull();
    expect(status.textContent).toContain(AVAILABILITY.status);
    expect(status.textContent).toMatch(new RegExp(`${AVAILABILITY.replyHours}h`));
    expect(status.querySelector(".status-dot")).not.toBeNull();
    expect(status.classList.contains("accent-card")).toBe(false);
  });

  it("sets page meta and renders Person JSON-LD", () => {
    renderHome();
    expect(document.title).toContain("Independent AI & ML consultant");
    const ld = document.querySelector('script[type="application/ld+json"]')!;
    expect(ld).not.toBeNull();
    const data = JSON.parse(ld.textContent!);
    expect(data["@type"]).toBe("Person");
    expect(data.jobTitle).toBe("Independent AI & ML Consultant");
  });

  it("is lean: no duplicated services/case-study/frameworks content", () => {
    renderHome();
    expect(screen.queryByText("ML/AI systems")).toBeNull();
    expect(screen.queryByText("Agentic AI & LLM applications")).toBeNull();
    expect(screen.queryByText("Data engineering & forecasting")).toBeNull();
    expect(screen.queryByText(/all 7 projects/i)).toBeNull();
    expect(screen.queryByRole("link", { name: /01-rag-agent/ })).toBeNull();
    expect(screen.queryByText("FastAPI")).toBeNull();
    expect(screen.queryByRole("link", { name: "all →" })).toBeNull();
    expect(document.querySelector(".project-grid")).toBeNull();
  });
});
