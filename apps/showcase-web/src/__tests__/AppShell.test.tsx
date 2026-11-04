import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { SITE_NAME, SITE_NAME_ROOT, SITE_NAME_SUFFIX } from "../config";

beforeEach(() => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Nav brand split", () => {
  it("renders the brand as the identical text with '.dev' in an accent span", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    const brand = document.querySelector(".nav-brand")!;
    expect(brand).not.toBeNull();
    // the accessible/read text is unchanged
    expect(brand.textContent).toBe(SITE_NAME);
    // split: root in the default brand color, ".dev" in the accent span
    const accent = brand.querySelector(".nav-brand-accent")!;
    expect(accent).not.toBeNull();
    expect(accent.textContent).toBe(".dev");
    expect(brand.textContent!.replace(accent.textContent!, "")).toBe(SITE_NAME_ROOT);
    // the config split concatenates back to the full site name
    expect(`${SITE_NAME_ROOT}${SITE_NAME_SUFFIX}`).toBe(SITE_NAME);
    const css = readFileSync("src/styles.css", "utf8");
    expect(css.match(/\.nav-brand-accent \{[\s\S]*?\n\}/)![0]).toContain(
      "color: var(--accent);",
    );
  });
});

describe("App shell (temporary smoke)", () => {
  it("skip link is the first focusable element and targets #main", () => {
    render(
      <MemoryRouter initialEntries={["/no-such-page"]}>
        <App />
      </MemoryRouter>,
    );
    const main = document.getElementById("main")!;
    expect(main.tabIndex).toBe(-1);
    const focusables = Array.from(
      document.querySelectorAll<HTMLElement>("a[href], button, [tabindex]"),
    ).filter((el) => el.tabIndex >= 0);
    expect(focusables[0]?.textContent).toBe("Skip to content");
    expect(focusables[0]?.getAttribute("href")).toBe("#main");
  });

  it("resets scroll and focuses #main without hiding it behind the nav", async () => {
    const scrollTo = vi.mocked(window.scrollTo);
    const focus = vi.spyOn(HTMLElement.prototype, "focus");
    render(
      <MemoryRouter initialEntries={["/no-such-page"]}>
        <App />
      </MemoryRouter>,
    );
    const routedMain = document.getElementById("main")!;
    await waitFor(() => expect(document.title).toContain("Page not found"));
    expect(document.head.querySelector('meta[name="robots"]')?.getAttribute("content")).toBe(
      "noindex",
    );
    expect(scrollTo).toHaveBeenCalledWith(0, 0);
    expect(document.activeElement).toBe(routedMain);
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    const live = screen.getByRole("status", { hidden: true });
    expect(live.className).toBe("visually-hidden");
    // announced via a macrotask after the route meta effect runs
    await waitFor(() => expect(live.textContent).toContain("Page not found"));
  });

  it("shows the styled skeleton while a lazy route chunk loads", async () => {
    render(
      <MemoryRouter initialEntries={["/services"]}>
        <App />
      </MemoryRouter>,
    );
    expect(document.querySelector(".route-skeleton")).not.toBeNull();
    await waitFor(() =>
      expect(document.querySelector(".route-skeleton")).toBeNull(),
    );
  });

  it("pads the page content one token above the footer", () => {
    const css = readFileSync("src/styles.css", "utf8");
    // every route renders .app-main--fluid (App.tsx), so its bottom padding is
    // the space before the footer bar: 0.5rem base + one ~3rem token = 3.5rem
    const fluidRule = css.match(/\.app-main--fluid \{[\s\S]*?\n\}/)![0];
    expect(fluidRule).toContain("padding: 0.5rem 1.25rem 3.5rem;");
  });
});
