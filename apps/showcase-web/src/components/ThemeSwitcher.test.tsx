import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { THEME_STORAGE_KEY } from "../theme/useTheme";
import { ThemeSwitcher } from "./ThemeSwitcher";

beforeEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  document.documentElement.style.colorScheme = "";
});

afterEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  document.documentElement.style.colorScheme = "";
});

describe("ThemeSwitcher", () => {
  it("renders a labelled group with a dark and a light option", () => {
    render(<ThemeSwitcher />);

    const group = screen.getByRole("group", { name: "Display theme" });
    expect(group).toHaveClass("theme-switcher");
    const options = screen.getAllByRole("button");
    expect(options.map((b) => b.textContent!.replace(/\s+/g, ""))).toEqual(["☾dark", "☼light"]);
    // the glyphs are decorative; the accessible name comes from the label text
    for (const option of options) {
      expect(option.querySelector("span")!.getAttribute("aria-hidden")).toBe("true");
    }
  });

  it("defaults to the dark option active and applies it to the document", () => {
    render(<ThemeSwitcher />);

    expect(screen.getByRole("button", { name: "dark" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "light" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("activates light on click and persists it for the next visit", () => {
    render(<ThemeSwitcher />);

    fireEvent.click(screen.getByRole("button", { name: "light" }));

    expect(screen.getByRole("button", { name: "light" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "dark" })).toHaveAttribute("aria-pressed", "false");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("restores a persisted light theme and switches back to dark", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "light");
    render(<ThemeSwitcher />);

    expect(screen.getByRole("button", { name: "light" })).toHaveAttribute("aria-pressed", "true");
    expect(document.documentElement.dataset.theme).toBe("light");

    fireEvent.click(screen.getByRole("button", { name: "dark" }));

    expect(screen.getByRole("button", { name: "dark" })).toHaveAttribute("aria-pressed", "true");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  });
});
