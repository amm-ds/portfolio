import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ChannelCards,
  isEmailOrPhone,
  PHONE_HREF,
  PHONE_UNLOCK_KEY,
} from "../components/ChannelCards";
import { CONTACT_EMAIL, LINKEDIN_URL } from "../config";

/** The vitest jsdom environment ships no localStorage — stub a minimal one
 * per test so the phone gate can be exercised both ways. */
function stubLocalStorage(initial: Record<string, string> = {}) {
  const store: Record<string, string> = { ...initial };
  const getItem = vi.fn((key: string) => (key in store ? store[key] : null));
  const setItem = vi.fn((key: string, value: string) => {
    store[key] = String(value);
  });
  vi.stubGlobal("localStorage", {
    getItem,
    setItem,
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      for (const key of Object.keys(store)) delete store[key];
    }),
  });
  return { store, getItem, setItem };
}

beforeEach(() => {
  stubLocalStorage();
});

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
    expect(grid.classList.contains("channel-grid--4")).toBe(true);
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
    expect(screen.getByText(/share your email or phone to unlock the direct line/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /unlock/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /\+34 670 881 697/ })).toBeNull();
    const locked = document.querySelector(".channel-card--locked")!;
    expect(locked).not.toBeNull();
    // the one-line privacy note under the form
    expect(screen.getByText(/nothing leaves your device/i)).toBeInTheDocument();
  });

  it("shows an inline validation error on invalid input and stays locked", () => {
    const { setItem } = stubLocalStorage();
    renderCards();
    fireEvent.change(unlockInput(), { target: { value: "not-an-email" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(screen.getByText("enter a valid email address or phone number")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(unlockInput()).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByRole("link", { name: /\+34 670 881 697/ })).toBeNull();
    expect(setItem).not.toHaveBeenCalled();
  });

  it("unlocks on a valid email: stores the flag and reveals the tel link", () => {
    const { setItem } = stubLocalStorage();
    renderCards();
    fireEvent.change(unlockInput(), { target: { value: "ada@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(setItem).toHaveBeenCalledWith(PHONE_UNLOCK_KEY, "1");
    const tel = screen.getByRole("link", { name: /\+34 670 881 697/ });
    expect(tel.getAttribute("href")).toBe(PHONE_HREF);
    expect(tel.classList.contains("channel-card")).toBe(true);
    // the gate form is gone
    expect(screen.queryByLabelText(/email or phone/i)).toBeNull();
    expect(document.querySelector(".channel-card--locked")).toBeNull();
  });

  it("unlocks on a valid phone number too", () => {
    renderCards();
    fireEvent.change(unlockInput(), { target: { value: "+34 670 881 697" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(screen.getByRole("link", { name: /\+34 670 881 697/ })).toHaveAttribute(
      "href",
      PHONE_HREF,
    );
  });

  it("renders unlocked on load when the localStorage flag is already set", () => {
    stubLocalStorage({ [PHONE_UNLOCK_KEY]: "1" });
    renderCards();
    expect(screen.getByRole("link", { name: /\+34 670 881 697/ })).toHaveAttribute(
      "href",
      PHONE_HREF,
    );
    expect(screen.queryByLabelText(/email or phone/i)).toBeNull();
  });

  it("clears the error once the input is edited", () => {
    renderCards();
    fireEvent.change(unlockInput(), { target: { value: "nope" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
    fireEvent.change(unlockInput(), { target: { value: "ada@example.com" } });
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
