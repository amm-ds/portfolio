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

  it("renders six experience roles with date ranges and generic industry descriptors", () => {
    renderAbout();
    const roles = document.querySelectorAll(".role-card");
    expect(roles).toHaveLength(6);
    const titles = [...document.querySelectorAll(".role-card h3")].map((el) => el.textContent);
    expect(titles).toEqual([
      "Lead ML/AI engineer — pharmaceutical AI (remote)",
      "Senior data scientist — network telemetry (ISP data)",
      "Senior data scientist — manufacturing analytics",
      "Senior data scientist — e-commerce retail",
      "Data scientist & engineer",
      "Data scientist — venture studio",
    ]);
    // date ranges, newest first
    const dates = [...document.querySelectorAll(".role-dates")].map((el) => el.textContent);
    expect(dates).toEqual([
      "2025 — now",
      "2024 — 2025",
      "2023 — 2024",
      "2022 — 2023",
      "2021 — 2022",
      "2019 — 2021",
    ]);
    // scope notes from the profile
    expect(screen.getByText(/100k\+ products with hierarchical models/i)).toBeInTheDocument();
    expect(screen.getByText(/30\+ interviews/i)).toBeInTheDocument();
    // generic industry descriptors only — no company names anywhere on the page
    expect(screen.queryByText(/vanti|kognic|dera|pecan|letgo|olx|king/i)).toBeNull();
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

  it("trims 'how I work' to six narrative practices in one strip", () => {
    renderAbout();
    const items = document.querySelectorAll(".practices-strip li");
    expect(items).toHaveLength(6);
    const text = document.querySelector(".practices-strip")!.textContent!;
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
    // narrative style: one card, not a grid of service cards
    expect(document.querySelectorAll(".practices-strip")).toHaveLength(1);
    expect(document.querySelector(".practices-grid")).toBeNull();
    expect(document.querySelectorAll(".role-card")).toHaveLength(6);
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

  it("gives role cards the services card geometry (bigger padding)", () => {
    const css = readFileSync("src/styles.css", "utf8");
    const roleRule = css.match(/\.role-card \{[\s\S]*?\n\}/)![0];
    expect(roleRule).toContain("padding: 1.6rem 1.75rem;");
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
