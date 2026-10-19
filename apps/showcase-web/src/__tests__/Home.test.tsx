import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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

beforeEach(mockReducedMotion);

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

describe("Home (lean, wave 6)", () => {
  it("uses the exact title wording without 'Senior'", () => {
    renderHome();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Data Scientist & ML Engineer",
    );
    expect(screen.queryByText(/senior/i)).toBeNull();
  });

  it("types the wave-6 script: whoami, focus, stack, principles", () => {
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
    expect(screen.queryByText(/dvc repro/i)).toBeNull();
  });

  it("CTA points to /contact", () => {
    renderHome();
    const cta = screen.getByRole("link", { name: "/contact" });
    expect(cta.getAttribute("href")).toBe("/contact");
  });

  it("renders the where-to-go trio as three identical cards", () => {
    renderHome();
    const cards = document.querySelectorAll(".go-card");
    expect(cards).toHaveLength(3);
    cards.forEach((card) => {
      // shared accent-card surface + title with $ prefix + one-liner
      expect(card.classList.contains("accent-card")).toBe(true);
      const h3 = card.querySelector("h3")!;
      expect(h3.textContent).toMatch(/^\$ \w+ →$/);
      expect(card.querySelector("p")!.textContent!.length).toBeGreaterThan(10);
    });
    for (const { to, label } of [
      { to: "/projects", label: "experiments" },
      { to: "/services", label: "services" },
      { to: "/contact", label: "contact" },
    ]) {
      const link = screen.getByRole("link", { name: new RegExp(`\\$ ${label}`, "i") });
      expect(link).toHaveAttribute("href", to);
    }
  });

  it("is lean: no duplicated services/case-study/frameworks content", () => {
    renderHome();
    // services capability cards gone
    expect(screen.queryByText("ML/AI systems")).toBeNull();
    expect(screen.queryByText("Agentic AI & LLM applications")).toBeNull();
    expect(screen.queryByText("Data engineering & forecasting")).toBeNull();
    // featured case studies gone
    expect(screen.queryByText(/all 7 projects/i)).toBeNull();
    expect(screen.queryByRole("link", { name: /01-rag-agent/ })).toBeNull();
    // frameworks strip gone
    expect(screen.queryByText("FastAPI")).toBeNull();
    expect(screen.queryByRole("link", { name: "all →" })).toBeNull();
    // no project grid, no metrics fetching
    expect(document.querySelector(".project-grid")).toBeNull();
  });

  it("keeps a positioning paragraph and a terminal-style status line (no card)", () => {
    renderHome();
    expect(screen.getByText(/I build ML\/AI systems end to end/i)).toBeInTheDocument();
    const status = document.querySelector(".home-status")!;
    expect(status).not.toBeNull();
    expect(status.textContent).toContain("available for engagements");
    expect(status.querySelector(".status-dot")).not.toBeNull();
    expect(status.textContent).toMatch(/48h/);
    const contact = screen.getByRole("link", { name: "→ /contact" });
    expect(contact.getAttribute("href")).toBe("/contact");
    // no boxed availability card remains
    expect(document.querySelector(".availability")).toBeNull();
    expect(document.querySelector(".home-status")!.classList.contains("accent-card")).toBe(false);
  });
});
