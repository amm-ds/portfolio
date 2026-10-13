import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { Services } from "../pages/Services";

afterEach(cleanup);

describe("Services page (wave 4)", () => {
  it("renders the hero, 5 generic offerings and deliverables", () => {
    render(
      <MemoryRouter>
        <Services />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
      "Senior ML/AI engineering",
    );
    expect(screen.getByText("ML/AI systems delivery")).toBeInTheDocument();
    expect(screen.getByText("Agentic AI & LLM applications")).toBeInTheDocument();
    expect(screen.getByText("Data engineering")).toBeInTheDocument();
    expect(screen.getByText("Forecasting & analytics")).toBeInTheDocument();
    expect(screen.getByText("MLOps & reproducibility audits")).toBeInTheDocument();
    expect(screen.getByText("faithfulness/relevance eval harness")).toBeInTheDocument();
  });

  it("describes offerings generically without referencing specific projects", () => {
    render(
      <MemoryRouter>
        <Services />
      </MemoryRouter>,
    );
    expect(screen.queryByText(/project 0\d/i)).toBeNull();
    expect(screen.queryByText(/reference build/i)).toBeNull();
  });

  it("renders the frameworks grid with all 13 frameworks and a #frameworks anchor", () => {
    render(
      <MemoryRouter>
        <Services />
      </MemoryRouter>,
    );
    expect(document.getElementById("frameworks")).not.toBeNull();
    const tiles = document.querySelectorAll(".framework-tile");
    expect(tiles).toHaveLength(13);
    expect(screen.getByText("pydantic-ai")).toBeInTheDocument();
    // pydantic-ai has no simpleicons slug → renders the letter tile directly
    expect(screen.getByText("PA")).toBeInTheDocument();
  });

  it("degrades to a mono letter tile when the logo CDN image fails", () => {
    render(
      <MemoryRouter>
        <Services />
      </MemoryRouter>,
    );
    const tiles = document.querySelectorAll(".framework-tile");
    const firstImg = tiles[0].querySelector("img")!;
    expect(firstImg).not.toBeNull();
    fireEvent.error(firstImg);
    // first tile is pydantic → letters "Pd" replace its img; other tiles keep theirs
    expect(screen.getByText("Pd")).toBeInTheDocument();
    expect(tiles[0].querySelector("img")).toBeNull();
    // scikit-learn tile (3rd; 2nd is pydantic-ai which has no slug) still shows its img
    expect(tiles[2].querySelector("img")).not.toBeNull();
  });

  it("renders the cloud-agnostic block and the proof band linking to /projects", () => {
    render(
      <MemoryRouter>
        <Services />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Cloud-agnostic by design/i)).toBeInTheDocument();
    expect(screen.getByText(/AWS, Azure, GCP, or on-premises/i)).toBeInTheDocument();
    const proof = screen.getByRole("link", { name: /browse the case studies/i });
    expect(proof.getAttribute("href")).toBe("/projects");
  });

  it("keeps the process timeline, engagement models and contact block", () => {
    render(
      <MemoryRouter>
        <Services />
      </MemoryRouter>,
    );
    expect(screen.getByText("Discovery (free, 30–45 min)")).toBeInTheDocument();
    expect(screen.getByText("Fixed-scope project")).toBeInTheDocument();
    expect(screen.getByText("Retainer")).toBeInTheDocument();
    expect(screen.getByText("Advisory / audit")).toBeInTheDocument();
    expect(screen.getByText(/typical response within 48 hours/i)).toBeInTheDocument();
  });
});
