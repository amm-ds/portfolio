import { readFileSync } from "node:fs";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { Footer } from "../components/Footer";
import { REPO_URL, SITE_EMAIL, SITE_NAME } from "../config";

afterEach(cleanup);

function renderFooter() {
  return render(
    <MemoryRouter>
      <Footer />
    </MemoryRouter>,
  );
}

describe("Footer", () => {
  it("is a two-zone single bar: brand + copyright left, links right", () => {
    renderFooter();
    // one flex bar — no inner brand column, no second small-print row
    expect(document.querySelector(".footer-inner")).toBeNull();
    expect(document.querySelector(".footer-small")).toBeNull();
    const bar = document.querySelector(".footer-bar")!;
    expect(bar).not.toBeNull();
    // left zone: brand (mono, accent) + © 2026 (muted, small) on one line
    const brand = bar.querySelector(".footer-brand")!;
    expect(brand.querySelector(".footer-name")!.textContent).toBe(SITE_NAME);
    expect(brand.querySelector(".footer-copy")!.textContent).toBe("© 2026");
    // right zone: nav links + GitHub + contact email
    const nav = screen.getByRole("navigation", { name: "Footer" });
    const links = [...nav.querySelectorAll("a")].map((a) => ({
      text: a.textContent,
      href: a.getAttribute("href"),
    }));
    expect(links).toEqual([
      { text: "Projects", href: "/projects" },
      { text: "Services", href: "/services" },
      { text: "About", href: "/about" },
      { text: "Contact", href: "/contact" },
      { text: "Glossary", href: "/glossary" },
      { text: "GitHub", href: REPO_URL },
      { text: SITE_EMAIL, href: `mailto:${SITE_EMAIL}` },
    ]);
  });

  it("lays the bar out with space-between and baseline alignment, wrapping on mobile", () => {
    const css = readFileSync("src/styles.css", "utf8");
    const barRule = css.match(/\.footer-bar \{[\s\S]*?\n\}/)![0];
    expect(barRule).toContain("display: flex;");
    expect(barRule).toContain("justify-content: space-between;");
    expect(barRule).toContain("align-items: baseline;");
    expect(barRule).toContain("flex-wrap: wrap;");
    const brandRule = css.match(/\.footer-brand \{[\s\S]*?\n\}/)![0];
    expect(brandRule).toContain("align-items: baseline;");
    // brand is accent-colored mono
    expect(css.match(/\.footer-name \{[\s\S]*?\n\}/)![0]).toContain("color: var(--accent);");
    expect(css.match(/\.footer-copy \{[\s\S]*?\n\}/)![0]).toContain("color: var(--muted);");
  });

  it("carries the copyright in the footer (it no longer lives on /about)", () => {
    renderFooter();
    expect(screen.getByText(/© 2026/)).toBeInTheDocument();
    expect(screen.queryByText(/MIT licensed/i)).toBeNull();
  });

  it("drops the positioning tagline and the LinkedIn link", () => {
    renderFooter();
    expect(screen.queryByText(/Data Scientist & ML Engineer/)).toBeNull();
    expect(screen.queryByRole("link", { name: /linkedin/i })).toBeNull();
  });

  it("drops the old gimmicky shell status line", () => {
    renderFooter();
    expect(screen.queryByText(/reproducible/i)).toBeNull();
    expect(document.querySelector(".footer .status-line")).toBeNull();
  });
});
