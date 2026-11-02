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
  it("is a single line: brand, nav links, GitHub and the contact email", () => {
    renderFooter();
    const nav = screen.getByRole("navigation", { name: "Footer" });
    // one flex line — no inner brand column, no second small-print row
    expect(document.querySelector(".footer-inner")).toBeNull();
    expect(document.querySelector(".footer-small")).toBeNull();
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
    // the brand sits inside the same line
    expect(nav.querySelector(".footer-name")!.textContent).toBe(SITE_NAME);
  });

  it("carries no copyright or license small print (that lives on /about)", () => {
    renderFooter();
    expect(screen.queryByText(/© 2026/)).toBeNull();
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
