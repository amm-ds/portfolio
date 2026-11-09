import { readFileSync } from "node:fs";
import { readStylesCss } from "./helpers/css";
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
  it("renders the hero and exactly 5 offering cards — the canonical categories", () => {
    renderServices();
    expect(screen.getByText("> services")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "ML/AI engineering, end to end",
    );
    const offerings = document.querySelectorAll(".offering-card");
    expect(offerings).toHaveLength(5);
    const titles = [...document.querySelectorAll(".offering-card h3")].map(
      (el) => el.textContent,
    );
    // the same five category names the projects index groups its rows by
    expect(titles).toEqual([
      "Agentic AI & LLM systems",
      "Machine learning",
      "Optimization",
      "Data engineering",
      "APIs & model serving",
    ]);
    // no anomaly-specific or otherwise vertical-specific offering card
    expect(titles).not.toContain("Anomaly detection");
    expect(titles).not.toContain("Predictive analytics");
    expect(titles).not.toContain("MLOps");
    expect(titles).not.toContain("Interactive dashboards");
    expect(titles).not.toContain("Full-stack engineering");
    // offering cards use the shared Card surface
    document.querySelectorAll(".offering-card").forEach((el) => {
      expect(el.classList.contains("accent-card")).toBe(true);
    });
  });

  it("each offering has an outcome, 4 tags, 4 deliverables and one evidence link", () => {
    renderServices();
    expect(screen.getByText(/answer from your documents, cite every claim/)).toBeInTheDocument();
    const cards = [...document.querySelectorAll(".offering-card")];
    expect(cards).toHaveLength(5);
    for (const card of cards) {
      const chips = [...card.querySelectorAll(".chip")].map((el) => el.textContent);
      expect(chips, card.querySelector("h3")!.textContent).toHaveLength(4);
      chips.forEach((c) => {
        expect(c!.trim().split(/\s+/).length).toBeLessThanOrEqual(3);
      });
      // deliverables: exactly four on every card, adapted to the offering
      const items = [...card.querySelectorAll("li")].map((el) => el.textContent);
      expect(items, card.querySelector("h3")!.textContent).toHaveLength(4);
      // one restrained evidence path per offering, not another sales block
      expect(card.querySelector("h4")?.textContent).toBe("deliverables");
      const evidence = card.querySelector("a.case-study-link");
      expect(evidence?.textContent).toBe("related case study →");
      expect(evidence?.getAttribute("href")).toMatch(/^\/projects(?:#|\/)/);
      expect(card.textContent).not.toMatch(/proof:|live demo:/i);
      expect(card.textContent).not.toMatch(/how success is measured/i);
    }
    // every card leads with a deliverable of its own vertical
    const firstDeliverables = cards.map((card) => card.querySelectorAll("li")[0]?.textContent);
    expect(firstDeliverables).toEqual([
      "retrieval pipeline over your documents with pinned corpus versions",
      "training pipeline with leakage-proof cross-validation",
      "solver tuned against named benchmark instances",
      "versioned, checksummed datasets in a documented registry",
      "versioned endpoint with an explicit contract",
    ]);
    // the full tag vocabulary covers every offering — capability wording only
    const chipTexts = [...document.querySelectorAll(".offering-card .chip")].map(
      (el) => el.textContent,
    );
    for (const chip of [
      "Retrieval pipelines",
      "Structured output",
      "Eval harnesses",
      "Cost budgets",
      "Leakage-proof CV",
      "Calibrated models",
      "Cost curves",
      "Hyperparameter search",
      "Exact & heuristics",
      "Benchmark instances",
      "Runtime budgets",
      "Gap reports",
      "Pipeline orchestration",
      "DQ gates",
      "Data registry",
      "CI eval gates",
      "OpenAPI contracts",
      "Latency budgets",
      "Contract tests",
      "Parity tests",
    ]) {
      expect(chipTexts).toContain(chip);
    }
    // no framework or library names in the tags — the frameworks section
    // carries the stack, which adapts to the task at hand
    for (const chip of chipTexts) {
      expect(chip!).not.toMatch(
        /react|plotly|fastapi|docker|polars|\bdvc\b|optuna|caddy|compose|pytorch|scikit/i,
      );
    }
  });

  it("lays the offerings out full width as 2 columns — 2 columns from 640px up, 1 below", () => {
    const css = readStylesCss();
    const gridRule = css.match(/\.offerings-grid \{[\s\S]*?\n\}/)![0];
    expect(gridRule).toContain("display: grid;");
    expect(gridRule).toContain("grid-template-columns: 1fr;");
    expect(gridRule).toContain("max-width: none;");
    // 2 columns from 640px up…
    expect(css).toContain("@media (min-width: 640px)");
    const twoCol = css.match(
      /@media \(min-width: 640px\) \{\s*\.offerings-grid \{[\s\S]*?\n  \}/,
    )![0];
    expect(twoCol).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    // …and no 4-column desktop tier remains for the offerings grid
    expect(css).not.toMatch(/@media \(min-width: 1200px\) \{\s*\.offerings-grid/);
    const offeringsRules = [...css.matchAll(/\.offerings-grid\s*\{[^}]*\}/g)].map((m) => m[0]);
    expect(offeringsRules.join("\n")).not.toContain("repeat(4");
    // the old single-column flex list is gone
    expect(gridRule).not.toContain("flex-direction: column;");
  });

  it("paints all offering tags blue — the hue rotation is gone entirely", () => {
    renderServices();
    const cards = [...document.querySelectorAll(".offering-card")];
    expect(cards).toHaveLength(5);
    for (const card of cards) {
      const chips = [...card.querySelectorAll(".chip")];
      expect(chips).toHaveLength(4);
      // every chip is the plain blue chip — no per-tag hue classes anywhere
      for (const c of chips) {
        expect(c.className).toBe("chip");
      }
    }
    const css = readStylesCss();
    const rule = css.match(/\.study-card \.chip,\n\.offering-card \.chip \{[\s\S]*?\n\}/)![0];
    expect(rule).toContain("color: var(--chip-blue-text);");
    expect(rule).toContain("background: var(--chip-blue-bg);");
    expect(rule).toContain("border-color: var(--chip-blue-border);");
    // no hue modifier classes remain in the stylesheet
    for (const hue of ["teal", "sky", "violet", "amber"]) {
      expect(css).not.toContain(`.chip--${hue}`);
    }
    // the muted mono label style is otherwise untouched
    expect(css.match(/\.chip \{[\s\S]*?\n\}/)![0]).toContain("color: var(--muted);");
  });

  it("keeps every offering description generic — architect/full-stack expertise, no model-type specifics", () => {
    renderServices();
    // the ML card no longer names forecasting/churn models and carries the
    // canonical category name
    expect(screen.getByRole("heading", { name: "Machine learning" })).toBeInTheDocument();
    expect(screen.queryByText("Machine learning & deep learning")).toBeNull();
    expect(screen.queryByText(/forecasting, classification and churn/i)).toBeNull();
    // every card reads as delivery expertise in its own vertical
    const blurbs = [...document.querySelectorAll(".offering-blurb")].map((el) => el.textContent!);
    expect(blurbs).toHaveLength(5);
    for (const blurb of blurbs) {
      expect(blurb.length).toBeGreaterThan(60);
    }
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
    expect(document.querySelectorAll(".frameworks-grid:not(.providers-grid) .framework-tile")).toHaveLength(17);
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
      "DuckDB",
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

  it("serves every provider icon from local SVGs (production CSP blocks CDNs) with documented provenance", () => {
    renderServices();
    const providerSection = document.querySelector(".providers-grid")!;
    const awsImg = providerSection.querySelector('[alt="AWS logo"]')!;
    const azureImg = providerSection.querySelector('[alt="Microsoft Azure logo"]')!;
    expect(awsImg.getAttribute("src")).toBe("/logos/aws.svg");
    expect(azureImg.getAttribute("src")).toBe("/logos/azure.svg");
    // Google Cloud and Docker moved off the CDN too — every icon is self-hosted
    const gcImg = providerSection.querySelector('[alt="Google Cloud logo"]')!;
    expect(gcImg.getAttribute("src")).toBe("/logos/googlecloud.svg");
    const dockerImg = providerSection.querySelector('[alt="Docker logo"]')!;
    expect(dockerImg.getAttribute("src")).toBe("/logos/docker.svg");
    // every Simple Icons download is a real, non-empty SVG
    for (const f of ["googlecloud", "docker"]) {
      const svg = readFileSync(`public/logos/${f}.svg`, "utf8");
      expect(svg).toContain("<svg");
    }
    // every documented local logo file exists and carries a source/license note
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

  it("ships a horizontal process timeline (5-up, 2-up, 1-up) with a numbered revisions step", () => {
    const css = readStylesCss();
    expect(css).toContain(".process-timeline {\n  list-style: none;\n  margin: 1.75rem 0 0;\n  padding: 0;\n  display: grid;\n  grid-template-columns: repeat(5, minmax(0, 1fr));");
    expect(css).toContain("row-gap: 2.25rem;");
    expect(css).toContain("padding-top: 1.15rem;");
    expect(css).toContain("@media (max-width: 1099px)");
    expect(css).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(css).toContain("@media (max-width: 719px)");
    expect(css).toContain("grid-template-columns: 1fr;");
    // step nodes straddle the connecting line
    expect(css).toContain("top: -0.75rem;");
    renderServices();
    const items = [...document.querySelectorAll(".process-timeline li")];
    expect(items).toHaveLength(5);
    // all five steps numbered — the revisions step carries its "05" badge
    const steps = [...document.querySelectorAll(".process-timeline .step-num")].map(
      (el) => el.textContent,
    );
    expect(steps).toEqual(["01", "02", "03", "04", "05"]);
    const revisions = items[items.length - 1];
    expect(revisions.querySelector(".step-num")!.textContent).toBe("05");
    expect(revisions.querySelector("h3")!.textContent).toBe("Revisions");
    expect(screen.getByText(/re-run, and the report updated/i)).toBeInTheDocument();
    expect(screen.getByText("Revisions").closest("li")!.textContent).toMatch(/^05/);
    // engagement models mention the revision rounds
    expect(screen.getAllByText(/includes structured revision rounds/i).length).toBeGreaterThanOrEqual(2);
  });

  it("wraps framework and provider names instead of truncating them", () => {
    const css = readStylesCss();
    const nameRule = css.match(/\.framework-name \{[\s\S]*?\n\}/)![0];
    expect(nameRule).toContain("overflow-wrap: anywhere;");
    expect(nameRule).not.toContain("text-overflow");
    expect(css.match(/\.frameworks-grid \{[\s\S]*?\n\}/)![0]).toContain("minmax(160px, 1fr)");
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
