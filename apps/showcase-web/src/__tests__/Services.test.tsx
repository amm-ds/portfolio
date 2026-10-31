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
  it("renders the hero and exactly 8 generic offering cards (one per service line)", () => {
    renderServices();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "ML/AI engineering, end to end",
    );
    const offerings = document.querySelectorAll(".offering-card");
    expect(offerings).toHaveLength(8);
    const titles = [...document.querySelectorAll(".offering-card h3")].map(
      (el) => el.textContent,
    );
    expect(titles).toEqual([
      "AI/LLM systems",
      "Machine learning",
      "Optimization",
      "Data engineering",
      "MLOps",
      "Interactive dashboards",
      "Full-stack product engineering",
      "APIs & model serving",
    ]);
    // no anomaly-specific or otherwise vertical-specific offering card
    expect(titles).not.toContain("Anomaly detection");
    expect(titles).not.toContain("Predictive analytics");
    // offering cards use the shared Card surface
    document.querySelectorAll(".offering-card").forEach((el) => {
      expect(el.classList.contains("accent-card")).toBe(true);
    });
  });

  it("each offering has an outcome line, technical chips, evidence and concrete deliverables", () => {
    renderServices();
    expect(screen.getByText(/answer from your documents, cite their sources/)).toBeInTheDocument();
    // technical elements rendered as short, generic chips (scoped — some names also appear in prose)
    const chipTexts = [...document.querySelectorAll(".chip")].map((el) => el.textContent);
    for (const chip of [
      "APIs (FastAPI/REST)",
      "Retrieval pipelines",
      "Structured output",
      "Eval harnesses",
      "Leakage-proof CV",
      "Calibrated models",
      "Cost curves",
      "Optuna HPO",
      "Exact & heuristics",
      "Benchmark instances",
      "Runtime budgets",
      "Polars/DVC pipelines",
      "DQ gates",
      "Checksum pinning",
      "CI eval gates",
      "Docker + uv",
      "Clean-clone runs",
      "React + Plotly",
      "Live endpoints",
      "Pinned payloads",
      "FastAPI + React",
      "Docker Compose",
      "Caddy deploy",
      "FastAPI",
      "OpenAPI contracts",
      "Rate limits",
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
      "proof: vehicle routing benchmark",
      "/projects/06-routing-optimization",
    ]);
    expect(proofLinks).toContainEqual([
      "proof: NYC mobility data pipeline",
      "/projects/07-open-data-mobility",
    ]);
    expect(proofLinks).toContainEqual([
      "proof: demand forecast pipeline",
      "/projects/02-demand-forecasting",
    ]);
    expect(proofLinks).toContainEqual([
      "proof: inference serving benchmark",
      "/projects/08-inference-serving",
    ]);
    expect(proofLinks).toContainEqual(["proof: served demand API", "/projects/07-open-data-mobility"]);
    // the new APIs & model serving card is a generic offering like the others
    expect(proofLinks.filter(([, href]) => href === "/projects/08-inference-serving").length)
      .toBeGreaterThanOrEqual(2);
    // the anomaly card is gone — no offering links to it as its proof anymore
    expect(proofLinks.every(([, href]) => href !== "/projects/03-anomaly-detection")).toBe(true);
    // no success-measured sentences remain anywhere on the page
    expect(screen.queryByText(/how success is measured/i)).toBeNull();
    const cards = document.querySelectorAll(".offering-card");
    expect(cards).toHaveLength(8);
    cards.forEach((card) => {
      expect(card.textContent).not.toMatch(/how success is measured/i);
      // no slogan register: every card keeps the plain evidence/deliverables structure
      expect(card.querySelector("h4")?.textContent).toBe("evidence");
    });
    // deliverables are real, concrete items
    expect(screen.getByText("versioned inference endpoints (REST)")).toBeInTheDocument();
    expect(screen.getByText("OpenAPI contract with request/response schemas")).toBeInTheDocument();
    expect(screen.getByText("latency/throughput benchmark report")).toBeInTheDocument();
  });

  it("lays the offerings out in a strict 4-column grid inside a capped container (2 then 1 columns below)", () => {
    const css = readFileSync("src/styles.css", "utf8");
    expect(css).toContain(".offerings-grid {");
    expect(css).toContain("max-width: 1400px;");
    expect(css).toContain("grid-template-columns: repeat(4, minmax(0, 1fr));");
    expect(css).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    // 4-col breakpoint sits above the 2-col one so rows wrap 4+4 on desktop
    expect(css.indexOf("repeat(4, minmax(0, 1fr))")).toBeGreaterThan(
      css.indexOf("repeat(2, minmax(0, 1fr))"),
    );
    expect(css).not.toContain("repeat(auto-fill, minmax(300px, 1fr))");
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

  it("serves AWS and Azure from local SVGs (no CC0 CDN source) with documented provenance", () => {
    renderServices();
    const providerSection = document.querySelector(".providers-grid")!;
    const awsImg = providerSection.querySelector('[alt="AWS logo"]')!;
    const azureImg = providerSection.querySelector('[alt="Microsoft Azure logo"]')!;
    expect(awsImg.getAttribute("src")).toBe("/logos/aws.svg");
    expect(azureImg.getAttribute("src")).toBe("/logos/azure.svg");
    // Google Cloud still has a Simple Icons entry and stays on the CDN
    const gcImg = providerSection.querySelector('[alt="Google Cloud logo"]')!;
    expect(gcImg.getAttribute("src")).toBe("https://cdn.simpleicons.org/googlecloud");
    // every local logo file exists and carries a source/license note
    for (const f of ["aws", "azure", "ragas", "pydantic-ai"]) {
      const svg = readFileSync(`public/logos/${f}.svg`, "utf8");
      expect(svg).toContain("<svg");
      expect(svg).toMatch(/source/i);
    }
    const notes = readFileSync("public/logos/README.md", "utf8");
    expect(notes).toMatch(/trademark/i);
  });

  it("serves RAGAS and pydantic-ai logos locally (never had Simple Icons entries)", () => {
    renderServices();
    const frameworks = document.querySelector(".frameworks-grid:not(.providers-grid)")!;
    expect(frameworks.querySelector('[alt="RAGAS logo"]')!.getAttribute("src")).toBe(
      "/logos/ragas.svg",
    );
    expect(frameworks.querySelector('[alt="pydantic-ai logo"]')!.getAttribute("src")).toBe(
      "/logos/pydantic-ai.svg",
    );
  });

  it("degrades a provider logo to a letter tile on image error", () => {
    renderServices();
    const providerTiles = document.querySelectorAll(".providers-grid .framework-tile");
    // AWS is the first provider tile, served from the local SVG
    fireEvent.error(providerTiles[0].querySelector("img")!);
    expect(screen.getByText("Aw")).toBeInTheDocument();
    expect(providerTiles[0].querySelector("img")).toBeNull();
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

  it("degrades a local logo to a letter tile on image error", () => {
    renderServices();
    const ragasTile = document.querySelector('.framework-tile[title="RAGAS"]')!;
    fireEvent.error(ragasTile.querySelector("img")!);
    expect(screen.getByText("Ra")).toBeInTheDocument();
    expect(ragasTile.querySelector("img")).toBeNull();
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
  });
});
