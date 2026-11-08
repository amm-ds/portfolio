import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it } from "vitest";
import { ThemeSwitcher } from "./ui";

beforeEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
});

afterEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
});

it("exposes an accessible segmented theme control and updates the document", async () => {
  const user = userEvent.setup();
  render(<ThemeSwitcher />);

  const group = screen.getByRole("group", { name: "Display theme" });
  const dark = screen.getByRole("button", { name: "dark" });
  const light = screen.getByRole("button", { name: "light" });

  expect(group).toContainElement(dark);
  expect(group).toContainElement(light);
  expect(dark).toHaveAttribute("aria-pressed", "true");
  expect(light).toHaveAttribute("aria-pressed", "false");
  expect(document.documentElement).toHaveAttribute("data-theme", "dark");

  await user.click(light);
  await waitFor(() => expect(document.documentElement).toHaveAttribute("data-theme", "light"));
  expect(dark).toHaveAttribute("aria-pressed", "false");
  expect(light).toHaveAttribute("aria-pressed", "true");
  expect(window.localStorage.getItem("document-intelligence-theme")).toBe("light");

  await user.click(dark);
  await waitFor(() => expect(document.documentElement).toHaveAttribute("data-theme", "dark"));
  expect(window.localStorage.getItem("document-intelligence-theme")).toBe("dark");
});

it("restores the persisted light theme without changing the default", () => {
  window.localStorage.setItem("document-intelligence-theme", "light");
  const first = render(<ThemeSwitcher />);

  expect(screen.getByRole("button", { name: "light" })).toHaveAttribute("aria-pressed", "true");
  expect(document.documentElement).toHaveAttribute("data-theme", "light");

  first.unmount();
  window.localStorage.clear();
  render(<ThemeSwitcher />);
  expect(screen.getByRole("button", { name: "dark" })).toHaveAttribute("aria-pressed", "true");
});
