import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { Contact } from "../pages/Contact";
import {
  AVAILABILITY,
  CONTACT_EMAIL,
  LINKEDIN_URL,
  REPO_URL,
  SITE_TITLE_SUFFIX,
} from "../config";

afterEach(cleanup);

describe("Contact page", () => {
  it("renders the availability status once, from config", () => {
    render(
      <MemoryRouter>
        <Contact />
      </MemoryRouter>,
    );
    expect(screen.getByText(AVAILABILITY.status)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Get in touch");
  });

  it("states the reply window exactly once, from config", () => {
    render(
      <MemoryRouter>
        <Contact />
      </MemoryRouter>,
    );
    const matches = screen.getAllByText(
      new RegExp(`replies within ${AVAILABILITY.replyHours} hours on business days`),
    );
    expect(matches).toHaveLength(1);
    expect(screen.getByText(/Europe\/Madrid \(CET, UTC\+1\)/i)).toBeInTheDocument();
    expect(screen.queryByText(/available now/i)).not.toBeInTheDocument();
  });

  it("offers a primary mailto CTA with prefilled subject and body scaffold", () => {
    render(
      <MemoryRouter>
        <Contact />
      </MemoryRouter>,
    );
    const cta = screen.getByRole("link", { name: "Start a conversation" });
    const href = cta.getAttribute("href") ?? "";
    expect(href.startsWith(`mailto:${CONTACT_EMAIL}?`)).toBe(true);
    const params = new URLSearchParams(href.slice(`mailto:${CONTACT_EMAIL}?`.length));
    expect(params.get("subject")).toBe(`Project inquiry — ${SITE_TITLE_SUFFIX}`);
    const body = params.get("body") ?? "";
    expect(body).toContain("Problem:");
    expect(body).toContain("Data available:");
    expect(body).toContain("Timeline:");
  });

  it("keeps the GitHub issue link secondary and adds a LinkedIn chip", () => {
    render(
      <MemoryRouter>
        <Contact />
      </MemoryRouter>,
    );
    const issues = screen.getByRole("link", { name: /open an issue/i });
    expect(issues.getAttribute("href")).toBe(`${REPO_URL}/issues`);
    expect(issues.getAttribute("rel")).toContain("noopener");
    const linkedin = screen.getByRole("link", { name: /linkedin/i });
    expect(linkedin.getAttribute("href")).toBe(LINKEDIN_URL);
    expect(linkedin.getAttribute("rel")).toBe("noopener noreferrer");
    const email = screen.getByRole("link", { name: CONTACT_EMAIL });
    expect(email.getAttribute("href")).toBe(`mailto:${CONTACT_EMAIL}`);
    expect(screen.getByText(/English, Spanish/i)).toBeInTheDocument();
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

  it("sets the document title via usePageMeta", () => {
    render(
      <MemoryRouter>
        <Contact />
      </MemoryRouter>,
    );
    expect(document.title).toBe(`Contact · ${SITE_TITLE_SUFFIX}`);
  });
});
