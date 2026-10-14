import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App routing", () => {
  it("renders the terminal-styled 404 for unknown routes", () => {
    render(
      <MemoryRouter initialEntries={["/no-such-page"]}>
        <App />
      </MemoryRouter>,
    );
    expect(screen.getByText("$ 404 — page not found")).toBeInTheDocument();
    const home = screen.getByRole("link", { name: "→ home" });
    expect(home.getAttribute("href")).toBe("/");
    const projects = screen.getByRole("link", { name: "→ projects" });
    expect(projects.getAttribute("href")).toBe("/projects");
    // the project grid is not rendered on the 404 page
    expect(document.querySelector(".project-grid")).toBeNull();
  });
});
