import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { buildInquiryMailto, Contact } from "../pages/Contact";
import {
  AVAILABILITY,
  CONTACT_EMAIL,
  LINKEDIN_URL,
  REPO_URL,
  SITE_TITLE_SUFFIX,
} from "../config";

afterEach(cleanup);

function renderContact() {
  return render(
    <MemoryRouter>
      <Contact />
    </MemoryRouter>,
  );
}

const FIELDS = {
  name: "Ada Lovelace",
  email: "ada@example.com",
  organization: "Analytical Engines Ltd",
  message: "We need a demand forecast we can defend in front of the board.",
};

describe("Contact page", () => {
  it("renders the availability status once, from config", () => {
    renderContact();
    expect(screen.getByText(AVAILABILITY.status)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Get in touch");
  });

  it("states the reply window exactly once, from config", () => {
    renderContact();
    const matches = screen.getAllByText(
      new RegExp(`replies within ${AVAILABILITY.replyHours} hours on business days`),
    );
    expect(matches).toHaveLength(1);
    expect(screen.getByText(/Europe\/Madrid \(CET, UTC\+1\)/i)).toBeInTheDocument();
    expect(screen.queryByText(/available now/i)).not.toBeInTheDocument();
  });

  it("offers a primary mailto CTA with prefilled subject and body scaffold", () => {
    renderContact();
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
    renderContact();
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
    renderContact();
    expect(screen.getByText(/free 30–45 minute discovery call/i)).toBeInTheDocument();
    const services = screen.getByRole("link", { name: /services & process/i });
    expect(services.getAttribute("href")).toBe("/services");
  });

  it("sets the document title via usePageMeta", () => {
    renderContact();
    expect(document.title).toBe(`Contact · ${SITE_TITLE_SUFFIX}`);
  });
});

describe("Contact inquiry form", () => {
  it("renders name, email, organization and message fields above the links block", () => {
    renderContact();
    expect(screen.getByLabelText(/name/)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/)).toBeInTheDocument();
    expect(screen.getByLabelText(/organization/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/message/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send inquiry/i })).toBeInTheDocument();
    // the note that the mail client opens with the message pre-filled
    expect(screen.getByText(/opens your mail client with the message pre-filled/i)).toBeInTheDocument();
    // form sits above the existing links card
    const form = document.querySelector(".contact-form")!;
    const links = document.querySelector(".contact-block")!;
    expect(
      form.compareDocumentPosition(links) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("shows inline validation errors for empty required fields", () => {
    renderContact();
    fireEvent.click(screen.getByRole("button", { name: /send inquiry/i }));
    expect(screen.getByText("name is required")).toBeInTheDocument();
    expect(screen.getByText("email is required")).toBeInTheDocument();
    expect(screen.getByText("message is required")).toBeInTheDocument();
    expect(screen.getByLabelText(/name/)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText(/message/)).toHaveAttribute("aria-invalid", "true");
    // organization is optional — no error for it
    expect(screen.queryByText(/organization is required/i)).toBeNull();
  });

  it("rejects an invalid email address and a too-short message", () => {
    renderContact();
    fireEvent.change(screen.getByLabelText(/email/), { target: { value: "not-an-email" } });
    fireEvent.change(screen.getByLabelText(/message/), { target: { value: "too short" } });
    fireEvent.click(screen.getByRole("button", { name: /send inquiry/i }));
    expect(screen.getByText("enter a valid email address")).toBeInTheDocument();
    expect(screen.getByText("message must be at least 20 characters")).toBeInTheDocument();
  });

  it("clears a field's error once the field is edited", () => {
    renderContact();
    const name = screen.getByLabelText(/name/);
    fireEvent.click(screen.getByRole("button", { name: /send inquiry/i }));
    expect(screen.getByText("name is required")).toBeInTheDocument();
    fireEvent.change(name, { target: { value: FIELDS.name } });
    expect(screen.queryByText("name is required")).toBeNull();
  });

  it("composes a mailto with all fields plus the sender's email, and opens it", () => {
    const locationStub = { href: "" };
    vi.stubGlobal("location", locationStub);
    renderContact();
    fireEvent.change(screen.getByLabelText(/name/), { target: { value: FIELDS.name } });
    fireEvent.change(screen.getByLabelText(/email/), { target: { value: FIELDS.email } });
    fireEvent.change(screen.getByLabelText(/organization/i), {
      target: { value: FIELDS.organization },
    });
    fireEvent.change(screen.getByLabelText(/message/), { target: { value: FIELDS.message } });
    fireEvent.click(screen.getByRole("button", { name: /send inquiry/i }));

    expect(locationStub.href.startsWith(`mailto:${CONTACT_EMAIL}?`)).toBe(true);
    const params = new URLSearchParams(
      locationStub.href.slice(`mailto:${CONTACT_EMAIL}?`.length),
    );
    expect(params.get("subject")).toBe(`Project inquiry — ${FIELDS.organization}`);
    const body = params.get("body") ?? "";
    expect(body).toContain(`Name: ${FIELDS.name}`);
    expect(body).toContain(`Email: ${FIELDS.email}`);
    expect(body).toContain(`Organization: ${FIELDS.organization}`);
    expect(body).toContain(FIELDS.message);
    // the sender's email is in the body so the reply can be addressed
    expect(body).toContain("ada@example.com");
    // confirmation note: the mail client opens with the message pre-filled
    expect(screen.getByRole("status").textContent).toMatch(/mail client/i);
    vi.unstubAllGlobals();
  });
});

describe("buildInquiryMailto", () => {
  it("uses the organization in the subject when present, else the name", () => {
    const withOrg = new URLSearchParams(
      buildInquiryMailto(FIELDS).split("?")[1],
    );
    expect(withOrg.get("subject")).toBe("Project inquiry — Analytical Engines Ltd");
    const noOrg = new URLSearchParams(
      buildInquiryMailto({ ...FIELDS, organization: "" }).split("?")[1],
    );
    expect(noOrg.get("subject")).toBe("Project inquiry — Ada Lovelace");
  });

  it("marks a missing organization as a dash and encodes special characters", () => {
    const params = new URLSearchParams(
      buildInquiryMailto({ ...FIELDS, organization: "" }).split("?")[1],
    );
    expect(params.get("body")).toContain("Organization: —");
    const umlaut = buildInquiryMailto({
      ...FIELDS,
      name: "Jürgen Müller",
      message: "Budget: 50.000 € — plus travel & lodging.",
    });
    expect(umlaut.startsWith(`mailto:${CONTACT_EMAIL}?`)).toBe(true);
    const decoded = new URLSearchParams(umlaut.split("?")[1]);
    expect(decoded.get("body")).toContain("Jürgen Müller");
    expect(decoded.get("body")).toContain("50.000 €");
  });
});
