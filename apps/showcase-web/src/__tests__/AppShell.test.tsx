import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
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

  it("moves focus to #main and announces document.title on the 404 route", async () => {
    render(
      <MemoryRouter initialEntries={["/no-such-page"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(document.title).toContain("Page not found"),
    );
    expect(document.head.querySelector('meta[name="robots"]')?.getAttribute("content")).toBe(
      "noindex",
    );
    expect(document.activeElement).toBe(document.getElementById("main"));
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
});
