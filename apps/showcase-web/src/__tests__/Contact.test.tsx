import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { Contact } from "../pages/Contact";

afterEach(cleanup);

describe("Contact page", () => {
  it("renders availability status, GitHub, email placeholder, languages, timezone and response note", () => {
    render(
      <MemoryRouter>
        <Contact />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Get in touch");
    expect(screen.getByText(/\[status\] open for freelance and consulting engagements/i)).toBeInTheDocument();
    const github = screen.getByRole("link", { name: /github\.com\/amm-ds/i });
    expect(github.getAttribute("href")).toBe("https://github.com/amm-ds");
    expect(screen.getByText(/placeholder — add before launch/i)).toBeInTheDocument();
    expect(screen.getByText(/English, Spanish/i)).toBeInTheDocument();
    expect(screen.getByText(/flexible overlap with EU and US hours/i)).toBeInTheDocument();
    expect(screen.getAllByText(/within 48 hours/i).length).toBeGreaterThan(0);
  });

  it("links the engagement-starter copy to /services", () => {
    render(
      <MemoryRouter>
        <Contact />
      </MemoryRouter>,
    );
    expect(screen.getByText(/free 30–45 minute discovery call/i)).toBeInTheDocument();
    const services = screen.getByRole("link", { name: /services & process/i });
    expect(services.getAttribute("href")).toBe("/services");
  });
});
