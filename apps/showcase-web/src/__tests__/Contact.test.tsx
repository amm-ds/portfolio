import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
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

  it("has no 'Start a conversation' CTA button anywhere", () => {
    renderContact();
    expect(screen.queryByRole("link", { name: "Start a conversation" })).toBeNull();
    expect(screen.queryByText("Start a conversation")).toBeNull();
    expect(document.querySelector(".cta-band")).toBeNull();
  });

  it("prefills the Email channel card mailto with the subject and body scaffold", () => {
    renderContact();
    const email = screen.getByRole("link", { name: new RegExp(CONTACT_EMAIL, "i") });
    const href = email.getAttribute("href") ?? "";
    expect(href.startsWith(`mailto:${CONTACT_EMAIL}?`)).toBe(true);
    const params = new URLSearchParams(href.slice(`mailto:${CONTACT_EMAIL}?`.length));
    expect(params.get("subject")).toBe(`Project inquiry — ${SITE_TITLE_SUFFIX}`);
    const body = params.get("body") ?? "";
    expect(body).toContain("Problem:");
    expect(body).toContain("Data available:");
    expect(body).toContain("Timeline:");
  });

  it("renders GitHub, LinkedIn and Email as individual cards — the whole card is the link", () => {
    renderContact();
    const cards = [...document.querySelectorAll(".channel-card")];
    expect(cards).toHaveLength(3);
    // every card is an <a> carrying an inline SVG logo, a name and an address
    for (const card of cards) {
      expect(card.tagName).toBe("A");
      expect(card.querySelector("svg")).not.toBeNull();
      expect(card.querySelector("svg path")).not.toBeNull();
      expect(card.querySelector(".channel-name")!.textContent!.length).toBeGreaterThan(0);
      expect(card.querySelector(".channel-address")!.textContent!.length).toBeGreaterThan(0);
    }
    const github = screen.getByRole("link", { name: /github\.com/i });
    expect(github.classList.contains("channel-card")).toBe(true);
    expect(github.getAttribute("href")).toBe(`${REPO_URL}/issues`);
    expect(github.getAttribute("rel")).toContain("noopener");
    expect(github.textContent).toContain("github.com/amm-ds");
    const linkedin = screen.getByRole("link", { name: /linkedin/i });
    expect(linkedin.getAttribute("href")).toBe(LINKEDIN_URL);
    expect(linkedin.getAttribute("rel")).toBe("noopener noreferrer");
    expect(linkedin.textContent).toContain("linkedin/in/alejandro-mérida-maroto");
    const email = screen.getByRole("link", { name: new RegExp(CONTACT_EMAIL, "i") });
    expect(email.classList.contains("channel-card")).toBe(true);
    expect(email.getAttribute("href")).toContain(`mailto:${CONTACT_EMAIL}`);
    expect(screen.getByText(/English, Spanish/i)).toBeInTheDocument();
  });

  it("renders how-engagements-start as a numbered roadmap timeline with no revision-count claim", () => {
    renderContact();
    const items = [...document.querySelectorAll(".start-timeline li")];
    expect(items).toHaveLength(4);
    // numbered steps with the site's step-chip language
    const nums = [...document.querySelectorAll(".start-timeline .step-num")].map(
      (el) => el.textContent,
    );
    expect(nums).toEqual(["01", "02", "03", "04"]);
    expect(items[0].textContent).toMatch(/describe the problem, the data and the goal/i);
    expect(items[1].textContent).toMatch(/scoped proposal: objectives, data needs, deliverables, timeline/i);
    expect(items[2].textContent).toMatch(/shared repository from day one/i);
    expect(items[3].textContent).toMatch(/structured revision rounds/i);
    expect(items[3].textContent).toMatch(/full repository, documentation and a walkthrough/i);
    // no "05 revision rounds" / "5 revisions" claim anywhere on the page
    expect(document.body.textContent).not.toMatch(/0?5\s+revision/i);
    expect(document.body.textContent).not.toMatch(/\b5 revisions\b/i);
    const services = screen.getByRole("link", { name: /services & process/i });
    expect(services.getAttribute("href")).toBe("/services");
  });

  it("renders the bottom row as plain centered text links — no card, border or background", () => {
    renderContact();
    const row = document.querySelector(".footer-links")!;
    expect(row).not.toBeNull();
    expect(row.tagName).toBe("P");
    expect(row.classList.contains("accent-card")).toBe(false);
    const css = readFileSync("src/styles.css", "utf8");
    const rule = css.match(/\.footer-links \{[\s\S]*?\n\}/)![0];
    expect(rule).toContain("text-align: center;");
    expect(rule).not.toContain("background");
    expect(rule).not.toContain("border");
    expect(css).not.toContain(".cta-band");
    // the three plain links
    expect(screen.getByRole("link", { name: "/projects" })).toHaveAttribute("href", "/projects");
    expect(screen.getByRole("link", { name: "github" })).toHaveAttribute("href", REPO_URL);
    expect(screen.getByRole("link", { name: "email" })).toHaveAttribute("href", expect.stringContaining("mailto:"));
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
    // form sits above the channel cards
    const form = document.querySelector(".contact-form")!;
    const channels = document.querySelector(".channel-grid")!;
    expect(
      form.compareDocumentPosition(channels) & Node.DOCUMENT_POSITION_FOLLOWING,
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
    expect(screen.getByText("message must be at least 10 characters")).toBeInTheDocument();
  });

  it("constrains the message box resize and keeps the form and channel cards full width", () => {
    const css = readFileSync("src/styles.css", "utf8");
    const textareaRule = css.match(/\.form-field textarea \{\n  resize: vertical;[\s\S]*?\n\}/)![0];
    expect(textareaRule).toContain("resize: vertical;");
    expect(textareaRule).toContain("max-width: 100%;");
    expect(textareaRule).toContain("max-height: 10rem;");
    // no narrow centered column on the contact page
    expect(css.match(/\.contact-form \{[\s\S]*?\n\}/)![0]).not.toContain("max-width");
    expect(css.match(/\.channel-grid \{[\s\S]*?\n\}/)![0]).not.toContain("max-width");
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
