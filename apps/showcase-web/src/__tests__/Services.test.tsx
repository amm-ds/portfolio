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
  it("renders the hero and exactly 5 offering cards (one per service line)", () => {
    renderServices();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "ML/AI engineering, end to end",
    );
    const offerings = document.querySelectorAll(".offering-card");
    expect(offerings).toHaveLength(5);
    const titles = [...document.querySelectorAll(".offering-card h3")].map(
      (el) => el.textContent,
    );
    expect(titles).toEqual([
      "AI/LLM systems",
      "Predictive analytics",
      "ML engineering & MLOps",
      "Optimization",
      "Anomaly detection",
    ]);
    // offering cards use the shared Card surface
    document.querySelectorAll(".offering-card").forEach((el) => {
      expect(el.classList.contains("accent-card")).toBe(true);
    });
  });

  it("each offering has an outcome line, technical chips, evidence and a success sentence", () => {
    renderServices();
    expect(screen.getByText(/Assistants and agents that cite their sources/)).toBeInTheDocument();
    // technical elements rendered as short, specific chips (scoped — some names also appear in prose)
    const chipTexts = [...document.querySelectorAll(".chip")].map((el) => el.textContent);
    for (const chip of [
      "APIs (FastAPI/REST)",
      "Inference & serving",
      "Data pipelines (Polars/DVC)",
      "Viz (Plotly/React)",
      "Eval/HPO (Optuna)",
      "MLOps/CI (Actions/Docker)",
      "Leakage-proof CV",
      "Benchmark instances",
      "Alert budgets",
      "uv",
    ]) {
      expect(chipTexts).toContain(chip);
    }
    // every chip stays short (≤ 3 words)
    chipTexts.forEach((c) => {
      expect(c!.trim().split(/\s+/).length).toBeLessThanOrEqual(3);
    });
    // evidence chips link each offering to its proving experiment/demo
    const proofLinks = [...document.querySelectorAll(".offering-card .chip-link")].map(
      (el) => [el.textContent, el.getAttribute("href")] as const,
    );
    expect(proofLinks).toContainEqual(["proof: verified-claim RAG agent", "/projects/01-rag-agent"]);
    expect(proofLinks).toContainEqual([
      "proof: graded agentic workflow suite",
      "/projects/09-agentic-workflows",
    ]);
    expect(proofLinks).toContainEqual([
      "proof: demand forecast workbench",
      "/projects/02-demand-forecasting",
    ]);
    expect(proofLinks).toContainEqual(["live demo: forecast workbench", "/demos/forecast-workbench"]);
    expect(proofLinks).toContainEqual([
      "proof: CI-evaluated churn pipeline",
      "/projects/05-ml-pipeline-churn",
    ]);
    expect(proofLinks).toContainEqual(["live demo: churn sandbox", "/demos/churn-sandbox"]);
    expect(proofLinks).toContainEqual([
      "proof: uplift targeting study",
      "/projects/10-uplift-experimentation",
    ]);
    expect(proofLinks).toContainEqual([
      "proof: inference serving benchmark",
      "/projects/08-inference-serving",
    ]);
    expect(proofLinks).toContainEqual([
      "proof: vehicle routing benchmark",
      "/projects/06-routing-optimization",
    ]);
    expect(proofLinks).toContainEqual([
      "proof: incident detection w/ alert budget",
      "/projects/03-anomaly-detection",
    ]);
    // every offering carries exactly one metric-first success sentence
    const cards = document.querySelectorAll(".offering-card");
    expect(cards).toHaveLength(5);
    cards.forEach((card) => {
      expect(card.textContent).toMatch(/how success is measured ::/);
      expect(card.textContent).toMatch(/measured (on|by|as)/);
      expect(card.textContent).not.toMatch(/revenue/i);
    });
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
    expect(document.querySelectorAll(".frameworks-grid:not(.providers-grid) .framework-tile")).toHaveLength(16);
    // deterministic order: new entries placed per spec
    const names = [...document.querySelectorAll(".frameworks-grid:not(.providers-grid) .framework-name")].map(
      (el) => el.textContent,
    );
    expect(names).toEqual([
      "pydantic",
      "pydantic-ai",
      "Ollama",
      "scikit-learn",
      "PyTorch",
      "Polars",
      "Plotly",
      "DVC",
      "uv",
      "FastAPI",
      "React",
      "TypeScript",
      "Optuna",
      "RAGAS",
      "pydantic-evals",
      "Hugging Face",
    ]);
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
    // Google Cloud is the first provider still served a CDN logo (AWS/Azure are
    // letter tiles by design — their Simple Icons entries were removed).
    fireEvent.error(providerTiles[2].querySelector("img")!);
    expect(screen.getByText("Gc")).toBeInTheDocument();
    expect(providerTiles[2].querySelector("img")).toBeNull();
  });

  it("ships a horizontal process timeline (4-up, 2-up, 1-up) with breathing room", () => {
    const css = readFileSync("src/styles.css", "utf8");
    expect(css).toContain(".process-timeline {\n  list-style: none;\n  margin: 1.75rem 0 0;\n  padding: 0;\n  display: grid;\n  grid-template-columns: repeat(4, minmax(0, 1fr));");
    expect(css).toContain("row-gap: 2.25rem;");
    expect(css).toContain("padding-top: 1.15rem;");
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

  it("framework logos carry explicit dimensions and meaningful alt text", () => {
    renderServices();
    const imgs = [...document.querySelectorAll(".framework-tile img")];
    expect(imgs.length).toBeGreaterThan(0);
    imgs.forEach((img) => {
      expect(img.getAttribute("width")).toBe("22");
      expect(img.getAttribute("height")).toBe("22");
      expect(img.getAttribute("alt")).toMatch(/logo$/);
    });
    // AWS and Azure have no CC0-licensed icon source anymore — letter tiles, no <img>
    const providerSection = document.querySelector(".providers-grid")!;
    const providerImgs = [...providerSection.querySelectorAll("img")].map((i) => i.getAttribute("alt"));
    expect(providerImgs).not.toContain("AWS logo");
    expect(providerImgs).not.toContain("Microsoft Azure logo");
  });
});
