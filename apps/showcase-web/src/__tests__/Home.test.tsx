import { cleanup, render, screen } from "@testing-library/react";
import { readStylesCss } from "./helpers/css";
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
  it("leads with the AI & ML engineering positioning headline", () => {
    renderHome();
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.textContent).toBe("Data Scientist, ML & AI Consultant");
    // the old kicker wording is gone from the hero
    expect(screen.queryByText(/from experiment to production/i)).toBeNull();
  });

  it("positions with the audit copy: sub, three capability bullets, two CTAs", () => {
    renderHome();
    const sub = document.querySelector(".hero-sub")!;
    expect(sub.textContent).toBe(
      "I design and build predictive systems, intelligent applications and data platforms — from first experiment to reliable production deployment.",
    );
    const points = [...document.querySelectorAll(".hero-points li")].map((el) => el.textContent);
    expect(points).toEqual([
      "Predictive analytics & forecasting",
      "Applied AI, RAG & agentic systems",
      "ML engineering & production infrastructure",
    ]);
    const cta = screen.getByRole("link", { name: /Discuss a project/i });
    expect(cta).toHaveAttribute("href", "/contact");
    const explore = screen.getByRole("link", { name: /Explore the work/i });
    expect(explore).toHaveAttribute("href", "/projects");
  });

  it("goes straight from the hero to where-to-go, with no project links", () => {
    renderHome();
    expect(
      screen.queryByText(/naive baselines · honest metrics · auditable claims/i),
    ).toBeNull();
    // the home page links to sections only — never to individual projects
    expect(screen.queryByRole("link", { name: /01-rag-agent/ })).toBeNull();
    const hero = document.querySelector(".hero")!;
    const whereTo = document.querySelector(".go-grid")!;
    expect(
      hero.compareDocumentPosition(whereTo) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("has no demo CTAs, proof tiles or featured-demo cards", () => {
    renderHome();
    expect(screen.queryByRole("link", { name: "Try a live demo" })).toBeNull();
    expect(screen.queryByTestId("proof-tiles")).toBeNull();
    expect(screen.queryByText("0.498 vs 0.603")).toBeNull();
    expect(screen.queryByText(/\$ demand forecast workbench/i)).toBeNull();
    expect(screen.queryByText(/> demand forecast workbench/i)).toBeNull();
    expect(document.querySelectorAll(".go-card")).toHaveLength(3);
  });

  it("types the script and carries the full message as the terminal's accessible name", () => {
    renderHome();
    expect(screen.getByText("alejandro@alejandromerida.dev: ~")).toBeInTheDocument();
    expect(screen.getByText("data scientist · ml & ai consultant")).toBeInTheDocument();
    expect(
      screen.getByText(
        "artificial intelligence · machine learning · optimization · data engineering · mlops · full-stack engineering",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "python · typescript/react · pytorch · lightgbm · scikit-learn · pydantic-ai · ollama · docker · dvc · uv",
      ),
    ).toBeInTheDocument();
    // mlx is off the stack list; ollama stays
    expect(screen.queryByText(/mlx/i)).toBeNull();
    const stackLine = screen.getByText(/typescript\/react/);
    expect(stackLine.textContent).toContain("ollama");
    expect(stackLine.textContent).not.toContain("mlx");
    expect(
      screen.getByText(
        "reproducible pipelines · honest baselines · production-grade code · results quality & performance first",
      ),
    ).toBeInTheDocument();
    // the retired principles are gone from the page
    expect(screen.queryByText(/models propose/i)).toBeNull();
    expect(screen.queryByText(/small, reversible changes/i)).toBeNull();
    // full typed content exists in the DOM from first render via aria-label
    const term = document.querySelector(".hero-terminal")!;
    expect(term.getAttribute("role")).toBe("img");
    expect(term.getAttribute("aria-label")).toContain("> whoami");
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
      const link = screen.getByRole("link", { name: new RegExp(`> ${label}`, "i") });
      expect(link).toHaveAttribute("href", to);
    }
  });

  it("hero intro is the exact positioning sentence, centered, in grey (--muted)", () => {
    renderHome();
    const sub = document.querySelector(".hero-sub")!;
    expect(sub.textContent).toBe(
      "I design and build predictive systems, intelligent applications and data platforms — from first experiment to reliable production deployment.",
    );
    const css = readStylesCss();
    const rule = css.match(/\.hero-sub \{[\s\S]*?\n\}/)![0];
    // the hero centers text and the sentence block centers within it
    expect(css.match(/\.hero \{[\s\S]*?\n\}/)![0]).toContain("text-align: center;");
    expect(rule).toContain("margin: 1.5rem auto 0.75rem;");
    expect(rule).toContain("color: var(--muted);");
  });

  it("where-to-go keeps a small breathing gap under the hero stage", () => {
    const css = readStylesCss();
    const heroRule = css.match(/\.hero \{[\s\S]*?\n\}/)![0];
    expect(heroRule).toContain("padding: 3rem 0 0.15rem;");
    // the hero no longer stretches to 88vh — the dead space above the
    // where-to-go block is gone
    expect(heroRule).toContain("min-height: min(52vh, 560px);");
    expect(css).toContain(".section-title--tight");
    expect(css.match(/\.section-title--tight \{[\s\S]*?\n\}/)![0]).toContain("margin-top: 0.8rem;");
  });

  it("renders the capability bullets in the hero and keeps the intro sentence in grey (--muted)", () => {
    renderHome();
    const points = document.querySelector(".hero-points")!;
    expect(points).not.toBeNull();
    expect(points.textContent).toContain("Predictive analytics & forecasting");
    expect(points.textContent).toContain("Applied AI, RAG & agentic systems");
    expect(points.textContent).toContain("ML engineering & production infrastructure");
    // the retired kicker line is gone from the hero
    expect(document.querySelector(".hero-kicker")).toBeNull();
  });

  it("paints only the Data/ML/AI words green — h1 base white, accent spans, no gradient", () => {
    renderHome();
    const accents = [...document.querySelectorAll(".hero-accent")].map((e) => e.textContent);
    expect(accents).toEqual(["Data", "ML", "AI"]);
    const h1 = document.querySelector(".hero h1")!;
    expect(h1.textContent).toContain("Data Scientist, ML & AI Consultant");
    const css = readStylesCss();
    const rule = css.match(/\.hero h1 \{[\s\S]*?\n\}/)![0];
    expect(rule).toContain("color: var(--text);");
    expect(css.match(/\.hero-accent \{[\s\S]*?\n\}/)![0]).toContain("color: var(--accent);");
    expect(rule).not.toContain("linear-gradient");
    expect(rule).not.toContain("background-clip");
    expect(rule).not.toContain("transparent");
    expect(rule).not.toContain("text-shadow");
  });

  it("centers the availability band with a 4rem bottom margin before the footer", () => {
    renderHome();
    const status = document.querySelector(".home-status")!;
    expect(status).not.toBeNull();
    const css = readStylesCss();
    const rule = css.match(/\.home-status \{[\s\S]*?\n\}/)![0];
    expect(rule).toContain("justify-content: center;");
    expect(rule).toContain("margin: 1.75rem 0 4rem;");
    expect(rule).toContain("text-align: center;");
  });

  it("availability line reads 'replies within 24h' from config", () => {
    renderHome();
    // AVAILABILITY is the source of truth — the site commits to a 24h reply
    expect(AVAILABILITY.replyHours).toBe(24);
    const status = document.querySelector(".home-status")!;
    expect(status).not.toBeNull();
    expect(status.textContent).toContain(AVAILABILITY.status);
    expect(status.textContent).toContain("replies within 24h");
    expect(status.querySelector(".status-dot")).not.toBeNull();
    expect(status.classList.contains("accent-card")).toBe(false);
    // the contact go-card carries the same reply window wording
    const contactCard = [...document.querySelectorAll(".go-card")].find((c) =>
      c.textContent!.includes("timezone overlap"),
    )!;
    expect(contactCard.textContent).toContain("replies within 24h on business days");
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
    const css = readStylesCss();
    // 1160 → 1280px hero, 1120 → 1200px terminal (wide enough for the one-line focus output)
    expect(css).toContain("max-width: 1280px;");
    expect(css).not.toContain("max-width: 1160px;");
    expect(css).toContain("max-width: 1200px;");
    expect(css).not.toContain("max-width: 1120px;");
    expect(css).not.toContain("max-width: 1160px;");
    // the stage is capped low so "where to go" sits close under the terminal
    expect(css).toContain("min-height: min(52vh, 560px);");
    const heroRule = css.match(/\.hero \{[\s\S]*?\n\}/)![0];
    expect(heroRule).toContain("max-width: 1280px;");
    expect(heroRule).toContain("min-height: min(52vh, 560px);");
    // the grid layer has an explicit inset and no grow-in of any kind
    const gridRule = css.match(/\.hero::before \{[\s\S]*?\n\}/)![0];
    expect(gridRule).toContain("inset: 0;");
    expect(gridRule).toContain("width: 100vw;");
    expect(gridRule).not.toMatch(/animation|@keyframes/);
    expect(gridRule).not.toMatch(/scale\(|width:\s*0/);
  });
});
