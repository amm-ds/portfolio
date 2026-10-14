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

  it("keeps the frameworks grid, cloud block, process and engagement table", () => {
    renderServices();
    expect(document.getElementById("frameworks")).not.toBeNull();
    expect(document.querySelectorAll(".framework-tile")).toHaveLength(13);
    expect(screen.getByText(/Cloud-agnostic by design/i)).toBeInTheDocument();
    // cloud block uses the shared Card with the secondary accent
    const cloud = document.querySelector(".cloud-block")!;
    expect(cloud.classList.contains("accent-card")).toBe(true);
    expect(cloud.classList.contains("card-secondary")).toBe(true);
    expect(screen.getByText("Discovery (free, 30–45 min)")).toBeInTheDocument();
    // engagement models render through the shared DataTable
    expect(screen.getByText("Fixed-scope project")).toBeInTheDocument();
    const table = document.querySelector(".engagement-table")!;
    expect(table.classList.contains("data-table")).toBe(true);
    expect(table.classList.contains("table-scroll")).toBe(true);
  });

  it("degrades a framework logo to a letter tile on image error", () => {
    renderServices();
    const tiles = document.querySelectorAll(".framework-tile");
    fireEvent.error(tiles[0].querySelector("img")!);
    expect(screen.getByText("Pd")).toBeInTheDocument();
    expect(tiles[0].querySelector("img")).toBeNull();
  });
});
