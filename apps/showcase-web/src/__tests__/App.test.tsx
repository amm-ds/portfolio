import { cleanup, render, screen, waitFor } from "@testing-library/react";
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

  it("renders the Projects index at both /projects and /experiments", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    for (const path of ["/projects", "/experiments"]) {
      cleanup();
      render(
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>,
      );
      await waitFor(() =>
        expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("projects"),
      );
      expect(screen.getByText("Demos — interactive experiments")).toBeInTheDocument();
    }
  });

  it("uses the fluid full-width layout on demo routes only", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const { container, unmount } = render(
      <MemoryRouter initialEntries={["/demos/churn-sandbox"]}>
        <App />
      </MemoryRouter>,
    );
    const main = container.querySelector("main")!;
    expect(main.className).toContain("app-main--fluid");
    unmount();

    const { container: projectsContainer } = render(
      <MemoryRouter initialEntries={["/projects"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("projects"),
    );
    expect(projectsContainer.querySelector("main")!.className).not.toContain("app-main--fluid");
  });
});
