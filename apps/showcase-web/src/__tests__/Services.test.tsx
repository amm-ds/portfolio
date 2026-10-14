import { readFileSync } from "node:fs";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { Services } from "../pages/Services";

afterEach(cleanup);

function renderServices() {
  return render(
    <MemoryRouter>
      <Services />
    </MemoryRouter>,
  );
}

describe("Services page (wave 8)", () => {
  it("renders the hero and exactly 6 offering cards", () => {
    renderServices();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
      "Senior ML/AI engineering",
    );
    const offerings = document.querySelectorAll(".offering-card");
    expect(offerings).toHaveLength(6);
    // offering cards use the shared Card surface
    document.querySelectorAll(".offering-card").forEach((el) => {
      expect(el.classList.contains("accent-card")).toBe(true);
    });
  });

  it("each offering has an outcome line, technical chips and deliverables", () => {
    renderServices();
    expect(screen.getByText(/Production ML systems designed, built, and handed over/)).toBeInTheDocument();
    // technical elements rendered as chips (scoped — some names also appear in prose)
    const chipTexts = [...document.querySelectorAll(".chip")].map((el) => el.textContent);
    for (const chip of [
      "full-stack development",
      "API design — FastAPI/REST",
      "model inference & serving",
      "data pipelines — Polars/DVC",
      "interactive visualization — Plotly/React",
      "evaluation & HPO — Optuna",
      "MLOps/CI — GitHub Actions",
      "Docker",
      "uv",
    ]) {
      expect(chipTexts).toContain(chip);
    }
    expect(screen.getByText("faithfulness/relevance eval harness")).toBeInTheDocument();
  });

  it("has no proof band and no contact/availability block (Contact owns those)", () => {
    renderServices();
    expect(screen.queryByRole("link", { name: /browse the case studies/i })).toBeNull();
    expect(screen.queryByText(/typical response within 48 hours/i)).toBeNull();
    expect(screen.queryByText(/\[status\]/i)).toBeNull();
    expect(document.querySelector(".contact-block")).toBeNull();
  });

  it("keeps the frameworks grid, a plain cloud block with provider logos, process and engagement table", () => {
    renderServices();
    expect(document.getElementById("frameworks")).not.toBeNull();
    expect(document.querySelectorAll(".frameworks-grid:not(.providers-grid) .framework-tile")).toHaveLength(13);
    expect(screen.getByText(/Cloud-agnostic by design/i)).toBeInTheDocument();
    // cloud section is plain text (no Card wrapper) + provider logo row
    const cloud = document.querySelector(".cloud-plain")!;
    expect(cloud).not.toBeNull();
    expect(cloud.classList.contains("accent-card")).toBe(false);
    const providers = cloud.querySelectorAll(".providers-grid .framework-tile");
    expect(providers).toHaveLength(4);
    for (const name of ["AWS", "Microsoft Azure", "Google Cloud", "Docker"]) {
      expect(screen.getByRole("link", { name })).toBeInTheDocument();
    }
    expect(screen.getByText("Discovery (free, 30–45 min)")).toBeInTheDocument();
    // engagement models render through the shared DataTable
    expect(screen.getByText("Fixed-scope project")).toBeInTheDocument();
    const table = document.querySelector(".engagement-table")!;
    expect(table.classList.contains("data-table")).toBe(true);
    expect(table.classList.contains("table-scroll")).toBe(true);
  });

  it("degrades a provider logo to a letter tile on image error", () => {
    renderServices();
    const providerTiles = document.querySelectorAll(".providers-grid .framework-tile");
    fireEvent.error(providerTiles[0].querySelector("img")!);
    expect(screen.getByText("Aw")).toBeInTheDocument();
    expect(providerTiles[0].querySelector("img")).toBeNull();
  });

  it("ships a horizontal process timeline (4-up, 2-up, 1-up)", () => {
    const css = readFileSync("src/styles.css", "utf8");
    expect(css).toContain(".process-timeline {\n  list-style: none;\n  margin: 0;\n  padding: 0;\n  display: grid;\n  grid-template-columns: repeat(4, minmax(0, 1fr));");
    expect(css).toContain("@media (max-width: 1099px)");
    expect(css).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(css).toContain("@media (max-width: 719px)");
    expect(css).toContain("grid-template-columns: 1fr;");
    // step nodes straddle the connecting line
    expect(css).toContain("top: -0.75rem;");
  });

  it("degrades a framework logo to a letter tile on image error", () => {
    renderServices();
    const tiles = document.querySelectorAll(".framework-tile");
    fireEvent.error(tiles[0].querySelector("img")!);
    expect(screen.getByText("Pd")).toBeInTheDocument();
    expect(tiles[0].querySelector("img")).toBeNull();
  });
});
