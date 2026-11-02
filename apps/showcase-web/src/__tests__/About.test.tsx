import { readFileSync } from "node:fs";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { About } from "../pages/About";
import { CONTACT_EMAIL, REPO_URL, SITE_NAME } from "../config";

afterEach(cleanup);

function renderAbout() {
  return render(
    <MemoryRouter>
      <About />
    </MemoryRouter>,
  );
}

describe("About page", () => {
  it("opens with the consultant's name, positioning and contact block", () => {
    renderAbout();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Alejandro Mérida Maroto",
    );
    expect(screen.getByText("> about")).toBeInTheDocument();
    expect(screen.getByText("Independent ML/AI consultant — Barcelona.")).toBeInTheDocument();
    // the home-hero positioning sentence
    expect(
      screen.getByText(/I design, build and evaluate ML systems end to end, and I keep the code, metrics/),
    ).toBeInTheDocument();
    // contact block
    const tel = screen.getByRole("link", { name: "+34 670 881 697" });
    expect(tel.getAttribute("href")).toBe("tel:+34670881697");
    expect(screen.getByRole("link", { name: CONTACT_EMAIL })).toBeInTheDocument();
    const github = screen.getByRole("link", { name: "github.com/amm-ds" });
    expect(github.getAttribute("href")).toBe(REPO_URL);
    expect(screen.getByText("Spanish · Catalan · English")).toBeInTheDocument();
    expect(screen.getByText("Barcelona")).toBeInTheDocument();
  });

  it("renders six experience stops as a vertical timeline with periods and 2–3 bullets each", () => {
    renderAbout();
    const items = document.querySelectorAll(".timeline-item");
    expect(items).toHaveLength(6);
    const titles = [...document.querySelectorAll(".timeline-item h3")].map(
      (el) => el.textContent,
    );
    expect(titles).toEqual([
      "Lead ML/AI engineer — pharmaceutical AI (remote)",
      "Senior data scientist — network telemetry (ISP data)",
      "Senior data scientist — manufacturing analytics",
      "Senior data scientist — e-commerce retail",
      "Data scientist & engineer",
      "Data scientist — venture studio",
    ]);
    // periods, newest first, in accent mono
    const dates = [...document.querySelectorAll(".timeline-period")].map((el) => el.textContent);
    expect(dates).toEqual([
      "2025 — now",
      "2024 — 2025",
      "2023 — 2024",
      "2022 — 2023",
      "2021 — 2022",
      "2019 — 2021",
    ]);
    // each stop carries 2–3 achievement bullets
    for (const item of items) {
      const bullets = item.querySelectorAll("ul li").length;
      expect(bullets).toBeGreaterThanOrEqual(2);
      expect(bullets).toBeLessThanOrEqual(3);
    }
    // scope notes from the profile survive
    expect(screen.getByText(/100k\+ products with hierarchical models/i)).toBeInTheDocument();
    expect(screen.getByText(/30\+ interviews/i)).toBeInTheDocument();
    // generic industry descriptors only — no company names anywhere on the page
    expect(screen.queryByText(/vanti|kognic|dera|pecan|letgo|olx|king/i)).toBeNull();
  });

  it("connects the timeline with the site's dot/line language", () => {
    const css = readFileSync("src/styles.css", "utf8");
    // a connecting line down the list…
    const lineRule = css.match(/\.timeline::before \{[\s\S]*?\n\}/)![0];
    expect(lineRule).toContain("width: 1px;");
    expect(lineRule).toContain("background: var(--border);");
    // …and an accent dot per stop
    const dotRule = css.match(/\.timeline-item::before \{[\s\S]*?\n\}/)![0];
    expect(dotRule).toContain("border-radius: 50%;");
    expect(dotRule).toContain("background: var(--accent);");
    // vertical layout, single column
    expect(css.match(/\.timeline \{[\s\S]*?\n\}/)![0]).toContain("padding: 0 0 0 1.5rem;");
  });

  it("renders education & certifications as one condensed list", () => {
    renderAbout();
    const items = [...document.querySelectorAll(".education-card li")].map(
      (el) => el.textContent,
    );
    expect(items).toEqual([
      "Master in Big Data & Business Intelligence (UOC)",
      "Business & IT (UAB)",
      "Postgraduate in financial markets (UA)",
      "MITx — Machine Learning with Python",
      "GCP Big Data & ML fundamentals",
    ]);
  });

  it("opens 'how I work' at the top as importance cards with the services card geometry", () => {
    renderAbout();
    const cards = document.querySelectorAll(".practice-card");
    expect(cards).toHaveLength(6);
    const text = document.querySelector(".practices-grid")!.textContent!;
    for (const practice of [
      "reproducible pipelines",
      "pinned data with checksums",
      "scored-once evaluation",
      "honest baselines",
      "tested code",
      "stated limits",
    ]) {
      expect(text).toContain(practice);
    }
    // importance cards, not a narrative strip
    expect(document.querySelectorAll(".practices-grid")).toHaveLength(1);
    expect(document.querySelector(".practices-strip")).toBeNull();
    // "how I work" is the FIRST section right after the profile intro
    const firstTitle = document.querySelector(".section-title")!;
    expect(firstTitle.textContent).toBe("how I work");
    // and it precedes the experience timeline
    const hero = document.querySelector(".services-hero")!;
    const practices = document.querySelector(".practices-grid")!;
    const timeline = document.querySelector(".timeline")!;
    expect(
      hero.compareDocumentPosition(practices) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      practices.compareDocumentPosition(timeline) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("has no stack/frameworks section (Projects owns that) and no license line", () => {
    renderAbout();
    expect(document.querySelector(".about-stack")).toBeNull();
    expect(document.querySelector(".license-line")).toBeNull();
    expect(screen.queryByText(/© 2026/)).toBeNull();
    expect(screen.queryByText(/MIT licensed/i)).toBeNull();
    expect(screen.queryByRole("heading", { name: /^stack$/i })).toBeNull();
    // no framework chip vocabulary on the page
    expect(screen.queryByText("pydantic-ai")).toBeNull();
    expect(screen.queryByText("FastAPI")).toBeNull();
  });

  it("gives the practice cards the services card geometry (bigger padding)", () => {
    const css = readFileSync("src/styles.css", "utf8");
    const practiceRule = css.match(/\.practice-card \{[\s\S]*?\n\}/)![0];
    expect(practiceRule).toContain("padding: 1.6rem 1.75rem;");
    const offeringRule = css.match(/\.offering-card \{[\s\S]*?\n\}/)![0];
    expect(offeringRule).toContain("padding: 1.6rem 1.75rem;");
  });

  it("sets document title and meta description", () => {
    renderAbout();
    expect(document.title).toBe(`About · ${SITE_NAME}`);
    expect(
      document.head
        .querySelector<HTMLElement>('meta[name="description"]')
        ?.getAttribute("content"),
    ).toMatch(/Alejandro Mérida Maroto/);
  });
});
