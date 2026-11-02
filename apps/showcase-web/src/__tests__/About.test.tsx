import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { About } from "../pages/About";
import { CONTACT_EMAIL, SITE_NAME } from "../config";

afterEach(cleanup);

function renderAbout() {
  return render(
    <MemoryRouter>
      <About />
    </MemoryRouter>,
  );
}

describe("About page", () => {
  it("renders the independent-consultant positioning from the home hero", () => {
    renderAbout();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Independent ML/AI consultant",
    );
    expect(
      screen.getByText(/I design, build and evaluate ML systems end to end, and I keep the code, metrics/),
    ).toBeInTheDocument();
    expect(screen.getByText("> about")).toBeInTheDocument();
  });

  it("distills 8 concrete engineering practices from the playbook", () => {
    renderAbout();
    const practices = document.querySelectorAll(".practice-card");
    expect(practices).toHaveLength(8);
    const titles = [...document.querySelectorAll(".practice-card h3")].map((el) => el.textContent);
    for (const title of [
      "reproducible pipelines",
      "pinned data with checksums",
      "honest baselines",
      "scored-once evaluation",
      "drift & data-quality gates",
      "tested code",
      "typed contracts",
      "honest limits",
    ]) {
      // each h3 carries the numbered mono prefix, e.g. "01 reproducible pipelines"
      expect(titles.some((t) => t!.includes(title))).toBe(true);
    }
    // concrete practices, not slogans
    expect(screen.getByText(/dvc repro/i)).toBeInTheDocument();
    expect(screen.getAllByText(/checksum/i).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/regression test/i)).toBeInTheDocument();
  });

  it("lists the stack as chips and carries the contact address", () => {
    renderAbout();
    const chips = [...document.querySelectorAll(".about-stack .chip")].map((el) => el.textContent);
    expect(chips.length).toBeGreaterThanOrEqual(16);
    expect(chips).toContain("pydantic-ai");
    expect(chips).toContain("DVC");
    expect(screen.getByRole("link", { name: CONTACT_EMAIL })).toBeInTheDocument();
  });

  it("holds the copyright and MIT license line at the bottom of the page", () => {
    renderAbout();
    const license = document.querySelector(".license-line")!;
    expect(license.textContent).toBe(`© 2026 ${SITE_NAME} · MIT licensed`);
  });

  it("sets document title and meta description", () => {
    renderAbout();
    expect(document.title).toBe(`About · ${SITE_NAME}`);
    expect(
      document.head
        .querySelector<HTMLElement>('meta[name="description"]')
        ?.getAttribute("content"),
    ).toMatch(/Independent ML\/AI consultant/);
  });
});
