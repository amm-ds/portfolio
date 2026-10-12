import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { Services } from "../pages/Services";

afterEach(cleanup);

describe("Services page", () => {
  it("renders hero, offerings, process, engagement models and contact", () => {
    render(
      <MemoryRouter>
        <Services />
      </MemoryRouter>,
    );

    // hero
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
      "Senior ML/AI engineering",
    );
    // 5 offering cards
    expect(screen.getByText("ML/AI systems delivery")).toBeInTheDocument();
    expect(screen.getByText("Agentic AI & RAG applications")).toBeInTheDocument();
    expect(screen.getByText("Data engineering")).toBeInTheDocument();
    expect(screen.getByText("Forecasting & analytics")).toBeInTheDocument();
    expect(screen.getByText("MLOps & reproducibility audits")).toBeInTheDocument();
    // deliverables list under an offering
    expect(screen.getByText("faithfulness/relevance eval harness")).toBeInTheDocument();
    // process timeline steps
    expect(screen.getByText("Discovery (free, 30–45 min)")).toBeInTheDocument();
    expect(screen.getByText("Scoped pilot")).toBeInTheDocument();
    expect(screen.getByText("Production build")).toBeInTheDocument();
    expect(screen.getByText("Handover")).toBeInTheDocument();
    // engagement models
    expect(screen.getByText("Fixed-scope project")).toBeInTheDocument();
    expect(screen.getByText("Retainer")).toBeInTheDocument();
    expect(screen.getByText("Advisory / audit")).toBeInTheDocument();
    expect(screen.getByText(/pricing/i)).toBeInTheDocument();
    // contact block
    expect(screen.getByText(/typical response within 48 hours/i)).toBeInTheDocument();
    expect(screen.getByText(/English, Spanish/i)).toBeInTheDocument();
    // case-study links point at internal project routes
    const links = screen.getAllByRole("link", { name: /→$/ });
    expect(links.some((l) => l.getAttribute("href") === "/projects/01-rag-agent")).toBe(true);
    expect(links.some((l) => l.getAttribute("href") === "/projects/02-demand-forecasting")).toBe(true);
    // CTA to the project list
    expect(screen.getByRole("link", { name: "/projects" })).toBeInTheDocument();
  });
});
