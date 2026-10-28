import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { Footer } from "../components/Footer";
import { LINKEDIN_URL, SITE_EMAIL } from "../config";

afterEach(cleanup);

describe("Footer", () => {
  it("renders brand, positioning line, compact nav and small print", () => {
    render(
      <MemoryRouter>
        <Footer />
      </MemoryRouter>,
    );
    expect(screen.getByText("amm-ds")).toBeInTheDocument();
    expect(
      screen.getByText(/Data Scientist & ML Engineer — end-to-end ML\/AI systems/),
    ).toBeInTheDocument();

    const nav = screen.getByRole("navigation", { name: "Footer" });
    const links = [...nav.querySelectorAll("a")].map((a) => ({
      text: a.textContent,
      href: a.getAttribute("href"),
    }));
    expect(links).toEqual([
      { text: "Projects", href: "/projects" },
      { text: "Services", href: "/services" },
      { text: "Contact", href: "/contact" },
      { text: "GitHub", href: "https://github.com/amm-ds/portfolio" },
      { text: "LinkedIn", href: LINKEDIN_URL },
      { text: SITE_EMAIL, href: `mailto:${SITE_EMAIL}` },
    ]);

    expect(screen.getByText(/© 2026 amm-ds · MIT licensed/)).toBeInTheDocument();
  });

  it("states the privacy posture: no analytics, cookies, or stored user data", () => {
    render(
      <MemoryRouter>
        <Footer />
      </MemoryRouter>,
    );
    expect(
      screen.getByText("No analytics, no cookies, no user data stored."),
    ).toBeInTheDocument();
  });

  it("drops the old gimmicky shell status line", () => {
    render(
      <MemoryRouter>
        <Footer />
      </MemoryRouter>,
    );
    expect(screen.queryByText(/reproducible/i)).toBeNull();
    expect(document.querySelector(".footer .status-line")).toBeNull();
  });
});
