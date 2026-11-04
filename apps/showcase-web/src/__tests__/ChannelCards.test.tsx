import { readFileSync } from "node:fs";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChannelCards, isEmailOrPhone } from "../components/ChannelCards";
import { CONTACT_EMAIL, LINKEDIN_URL } from "../config";

/** Stub the one API call the phone gate makes — records the request so tests
 * can assert the endpoint and the body. */
function stubUnlockApi(opts: { phone?: string; status?: number } = {}) {
  const calls: { url: string; body: unknown }[] = [];
  const fetchStub = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(input), body: init?.body ? JSON.parse(String(init.body)) : null });
    const status = opts.status ?? 200;
    return new Response(
      JSON.stringify(status === 200 ? { phone: opts.phone ?? "+34 670 881 697" } : { error: "boom" }),
      { status, headers: { "Content-Type": "application/json" } },
    );
  });
  vi.stubGlobal("fetch", fetchStub);
  return { fetchStub, calls };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderCards() {
  return render(<ChannelCards />);
}

function unlockInput() {
  return screen.getByLabelText(/email or phone/i);
}

describe("isEmailOrPhone", () => {
  it("accepts email addresses and phone numbers, rejects everything else", () => {
    expect(isEmailOrPhone("ada@example.com")).toBe(true);
    expect(isEmailOrPhone("  ada@example.com  ")).toBe(true);
    expect(isEmailOrPhone("+34 670 881 697")).toBe(true);
    expect(isEmailOrPhone("670881697")).toBe(true);
    expect(isEmailOrPhone("+1 (555) 123-4567")).toBe(true);
    expect(isEmailOrPhone("not-an-email")).toBe(false);
    expect(isEmailOrPhone("12345")).toBe(false);
    expect(isEmailOrPhone("")).toBe(false);
    expect(isEmailOrPhone("call me maybe")).toBe(false);
  });
});

describe("ChannelCards", () => {
  it("renders the four channel cards with inline SVG logos in one grid", () => {
    renderCards();
    const grid = document.querySelector(".channel-grid")!;
    const names = [...grid.querySelectorAll(".channel-name")].map((el) => el.textContent);
    expect(names).toEqual(["Phone", "Email", "GitHub", "LinkedIn"]);
    for (const card of grid.querySelectorAll("svg")) {
      expect(card.querySelector("path")).not.toBeNull();
    }
    const github = screen.getByRole("link", { name: /github\.com/i });
    expect(github.getAttribute("href")).toBe("https://github.com/amm-ds");
    expect(github.getAttribute("target")).toBe("_blank");
    expect(github.getAttribute("rel")).toContain("noopener");
    const linkedin = screen.getByRole("link", { name: /linkedin/i });
    expect(linkedin.getAttribute("href")).toBe(LINKEDIN_URL);
    expect(linkedin.getAttribute("target")).toBe("_blank");
    const email = screen.getByRole("link", { name: new RegExp(CONTACT_EMAIL, "i") });
    expect(email.getAttribute("href")).toContain(`mailto:${CONTACT_EMAIL}`);
    // no external-target on the mailto card
    expect(email.getAttribute("target")).toBeNull();
  });

  it("renders the phone card locked by default — no tel link, a gate form instead", () => {
    renderCards();
    expect(screen.getByText(/share your email or phone to unlock/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /unlock/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /\+34/ })).toBeNull();
    const locked = document.querySelector(".channel-card--locked")!;
    expect(locked).not.toBeNull();
    // slim full-width layout: spans the whole grid line, no label/note text
    expect(locked.classList.contains("channel-card--slim")).toBe(true);
    expect(locked.querySelector(".channel-unlock-label")).toBeNull();
    expect(locked.querySelector(".channel-unlock-note")).toBeNull();
  });

  it("keeps the phone number out of page code — the component source carries no digits", () => {
    const src = readFileSync("src/components/ChannelCards.tsx", "utf8");
    for (const fragment of ["670 881 697", "670881697", "34670881697"]) {
      expect(src).not.toContain(fragment);
    }
  });

  it("shows an inline validation error on invalid input and never calls the API", () => {
    const { fetchStub } = stubUnlockApi();
    renderCards();
    fireEvent.change(unlockInput(), { target: { value: "not-an-email" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(screen.getByText("enter a valid email address or phone number")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(unlockInput()).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByRole("link", { name: /\+34/ })).toBeNull();
    expect(fetchStub).not.toHaveBeenCalled();
  });

  it("unlocks on a valid email: posts to the API and reveals the tel link from the response", async () => {
    const { calls } = stubUnlockApi({ phone: "+34 670 881 697" });
    renderCards();
    fireEvent.change(unlockInput(), { target: { value: "ada@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    const tel = await screen.findByRole("link", { name: /\+34 670 881 697/ });
    expect(calls).toEqual([{ url: "/contact/unlock", body: { value: "ada@example.com" } }]);
    expect(tel.getAttribute("href")).toBe("tel:+34670881697");
    // the unlocked line keeps the gate's slim full-width structure — it
    // replaces the gate in place instead of becoming a fourth grid card
    expect(tel.classList.contains("channel-card")).toBe(true);
    expect(tel.classList.contains("channel-card--slim")).toBe(true);
    // the gate form is gone
    expect(screen.queryByLabelText(/email or phone/i)).toBeNull();
    expect(document.querySelector(".channel-card--locked")).toBeNull();
  });

  it("unlocks on a valid phone number too", async () => {
    stubUnlockApi({ phone: "+34 670 881 697" });
    renderCards();
    fireEvent.change(unlockInput(), { target: { value: "+34 670 881 697" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(await screen.findByRole("link", { name: /\+34 670 881 697/ })).toHaveAttribute(
      "href",
      "tel:+34670881697",
    );
  });

  it("stays locked with an explanatory error when the API cannot be reached", async () => {
    stubUnlockApi({ status: 503 });
    renderCards();
    fireEvent.change(unlockInput(), { target: { value: "ada@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/email channel below/i);
    expect(screen.queryByRole("link", { name: /\+34/ })).toBeNull();
    expect(screen.getByLabelText(/email or phone/i)).toBeInTheDocument();
  });

  it("the gate is back on every reload — the unlock is view state only, nothing persisted", async () => {
    stubUnlockApi({ phone: "+34 670 881 697" });
    // the environment may or may not ship a localStorage — watch it either way;
    // the unlock flow must never write to it
    const setItem = vi.fn();
    vi.stubGlobal("localStorage", {
      getItem: vi.fn(() => null),
      setItem,
      removeItem: vi.fn(),
      clear: vi.fn(),
    });
    const first = renderCards();
    fireEvent.change(unlockInput(), { target: { value: "ada@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(await screen.findByRole("link", { name: /\+34 670 881 697/ })).toBeInTheDocument();
    // nothing was persisted — no flag, no entered value
    expect(setItem).not.toHaveBeenCalled();
    // a fresh mount (the reload) shows the gate again
    first.unmount();
    renderCards();
    expect(screen.getByLabelText(/email or phone/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /\+34/ })).toBeNull();
  });

  it("keeps the unlock gate inside the phone card's own bounds — all cards share one geometry", () => {
    const css = readFileSync("src/styles.css", "utf8");
    // the slimmed gate lets every card share the same height again (grid
    // default stretch) — the form stays inside the phone card's own track
    const gridRule = css.match(/\.channel-grid \{[\s\S]*?\n\}/)![0];
    expect(gridRule).toContain("align-items: stretch;");
    // the locked card cannot outgrow its grid track…
    const lockedRule = css.match(/\.channel-card--locked \{[\s\S]*?\n\}/)![0];
    expect(lockedRule).toContain("min-width: 0;");
    // …and the form row shrinks inside the card instead of overflowing it
    const inputRule = css.match(/\.channel-unlock-row input \{[\s\S]*?\n\}/)![0];
    expect(inputRule).toContain("flex: 1;");
    expect(inputRule).toContain("min-width: 0;");
    const textRule = css.match(/\.channel-text \{[\s\S]*?\n\}/)![0];
    expect(textRule).toContain("min-width: 0;");
  });

  it("clears the error once the input is edited", () => {
    stubUnlockApi();
    renderCards();
    fireEvent.change(unlockInput(), { target: { value: "nope" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
    fireEvent.change(unlockInput(), { target: { value: "ada@example.com" } });
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
