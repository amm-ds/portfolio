import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Home } from "../pages/Home";

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

describe("Home presentation page", () => {
  it("uses the exact title wording without 'Senior'", () => {
    renderHome();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Data Scientist & ML Engineer",
    );
    expect(screen.queryByText(/senior/i)).toBeNull();
  });

  it("renders the terminal hero with the typed script", () => {
    renderHome();
    expect(screen.getByText("alejandro@amm-ds: ~")).toBeInTheDocument();
    // reduced-motion guard is not active in jsdom → starts untyped; the cursor renders
    expect(document.querySelector(".cursor")).not.toBeNull();
  });

  it("renders three capability cards linking to /services", () => {
    renderHome();
    expect(screen.getByText("ML/AI systems")).toBeInTheDocument();
    expect(screen.getByText("Agentic AI & LLM applications")).toBeInTheDocument();
    expect(screen.getByText("Data engineering & forecasting")).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: "services →" });
    expect(links.length).toBeGreaterThanOrEqual(3);
    links.forEach((l) => expect(l.getAttribute("href")).toBe("/services"));
  });

  it("renders the three featured case studies with links to their pages", () => {
    renderHome();
    for (const id of ["01-rag-agent", "07-open-data-mobility", "03-anomaly-detection"]) {
      const link = screen.getByRole("link", { name: new RegExp(id) });
      expect(link.getAttribute("href")).toBe(`/projects/${id}`);
    }
    expect(screen.getByRole("link", { name: "all 7 projects →" })).toHaveAttribute(
      "href",
      "/projects",
    );
  });

  it("renders the frameworks strip linking to /services#frameworks", () => {
    renderHome();
    expect(screen.getByRole("link", { name: "all →" })).toHaveAttribute(
      "href",
      "/services#frameworks",
    );
    expect(screen.getByText("FastAPI")).toBeInTheDocument();
    expect(screen.getByText("Polars")).toBeInTheDocument();
  });

  it("renders the CTA band with services and GitHub links", () => {
    renderHome();
    expect(screen.getByText(/Available now/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "/services" })).toBeInTheDocument();
  });

  it("no longer renders the full project grid", () => {
    renderHome();
    expect(screen.queryByText(/loading projects/i)).toBeNull();
    expect(document.querySelector(".project-grid .project-card .badge")).toBeNull();
  });
});
