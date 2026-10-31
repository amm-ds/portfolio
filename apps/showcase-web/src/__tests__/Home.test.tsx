import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AVAILABILITY } from "../config";
import { Home } from "../pages/Home";

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

describe("Home (terminal-centered)", () => {
  it("leads with the Data Scientist, ML & AI Consultant title", () => {
    renderHome();
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.textContent).toBe("Data Scientist, ML & AI Consultant");
    expect(screen.getByText(/from experiment to production/i)).toBeInTheDocument();
  });

  it("has no demo CTAs, proof tiles or featured-demo cards", () => {
    renderHome();
    expect(screen.queryByRole("link", { name: "Try a live demo" })).toBeNull();
    expect(screen.queryByTestId("proof-tiles")).toBeNull();
    expect(screen.queryByText("0.498 vs 0.603")).toBeNull();
    expect(screen.queryByText(/\$ demand forecast workbench/i)).toBeNull();
    expect(document.querySelectorAll(".go-card")).toHaveLength(3);
  });

  it("types the script and carries the full message as the terminal's accessible name", () => {
    renderHome();
    expect(screen.getByText("alejandro@amm-ds: ~")).toBeInTheDocument();
    expect(screen.getByText("data scientist · ml & ai consultant")).toBeInTheDocument();
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
    expect(term.getAttribute("aria-label")).toContain("data scientist · ml & ai consultant");
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
    expect(cards).toHaveLength(3);
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
    expect(document.title).toContain("Data Scientist, ML & AI Consultant");
    const ld = document.querySelector('script[type="application/ld+json"]')!;
    expect(ld).not.toBeNull();
    const data = JSON.parse(ld.textContent!);
    expect(data["@type"]).toBe("Person");
    expect(data.jobTitle).toBe("Data Scientist, ML & AI Consultant");
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

describe("Home hero layout", () => {
  it("widens the hero and terminal, caps the hero height, and covers it with a static full-size grid", () => {
    const css = readFileSync("src/styles.css", "utf8");
    // 940 → 1160px hero, 780 → 1020px terminal
    expect(css).toContain("max-width: 1160px;");
    expect(css).not.toContain("max-width: 940px;");
    expect(css).toContain("max-width: 1020px;");
    expect(css).not.toContain("max-width: 780px;");
    // min-height can never exceed 88vh, so the hero never forces scroll
    expect(css).toContain("min-height: min(88vh, 880px);");
    const heroRule = css.match(/\.hero \{[\s\S]*?\n\}/)![0];
    expect(heroRule).toContain("max-width: 1160px;");
    expect(heroRule).toContain("min-height: min(88vh, 880px);");
    // the grid layer has an explicit inset and no grow-in of any kind
    const gridRule = css.match(/\.hero::before \{[\s\S]*?\n\}/)![0];
    expect(gridRule).toContain("inset: 0;");
    expect(gridRule).toContain("width: 100vw;");
    expect(gridRule).not.toMatch(/animation|@keyframes/);
    expect(gridRule).not.toMatch(/scale\(|width:\s*0/);
  });
});
