import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MermaidDiagram } from "../components/MermaidDiagram";
import { resetThemeStoreForTests } from "../theme/useTheme";

const mocks = vi.hoisted(() => ({
  initialize: vi.fn(),
  render: vi.fn(),
}));

vi.mock("mermaid", () => ({
  default: { initialize: mocks.initialize, render: mocks.render },
}));

beforeEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  resetThemeStoreForTests();
});

afterEach(() => {
  resetThemeStoreForTests();
  cleanup();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  mocks.initialize.mockReset();
  mocks.render.mockReset();
});

describe("MermaidDiagram", () => {
  it("initializes mermaid once and renders the svg into the host", async () => {
    mocks.render.mockResolvedValue({ svg: '<svg data-mock="direct"></svg>' });
    render(<MermaidDiagram code="graph TD; A-->B;" />);
    expect(screen.getByText("rendering diagram…")).toBeInTheDocument();
    await waitFor(() =>
      expect(document.querySelector('.mermaid-host svg[data-mock="direct"]')).not.toBeNull(),
    );
    expect(mocks.initialize).toHaveBeenCalledTimes(1);
    expect(mocks.initialize).toHaveBeenCalledWith(
      expect.objectContaining({
        themeVariables: expect.objectContaining({ primaryColor: "#1e293b" }),
      }),
    );
    expect(mocks.render).toHaveBeenCalledWith(
      expect.stringMatching(/^mmd-\d+$/),
      "graph TD; A-->B;",
    );
  });

  it("falls back to a styled pre when mermaid fails to parse", async () => {
    mocks.render.mockRejectedValue(new Error("parse error"));
    render(<MermaidDiagram code="not a diagram" />);
    // fallback: the source is shown in a pre, page did not crash
    await waitFor(() =>
      expect(document.querySelector("pre.mermaid-fallback code")?.textContent).toBe(
        "not a diagram",
      ),
    );
  });

  it("ignores the SPA fallback HTML (200 + text/html) and uses runtime rendering", async () => {
    mocks.render.mockResolvedValue({ svg: '<svg data-mock="runtime"></svg>' });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<!doctype html><html></html>", {
          status: 200,
          headers: { "content-type": "text/html" },
        }),
      ),
    );
    render(<MermaidDiagram code="graph LR; A-->B;" />);
    await waitFor(() =>
      expect(document.querySelector('.mermaid-host svg[data-mock="runtime"]')).not.toBeNull(),
    );
    expect(mocks.render).toHaveBeenCalled();
  });

  it("loads the pre-rendered SVG variant matching the persisted light theme", async () => {
    window.localStorage.setItem("portfolio-theme", "light");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('<svg data-mock="light-static"></svg>', {
        status: 200,
        headers: { "content-type": "image/svg+xml" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<MermaidDiagram code="graph TD; A-->B;" />);

    await waitFor(() =>
      expect(document.querySelector('.mermaid-host svg[data-mock="light-static"]')).not.toBeNull(),
    );
    expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\.light\.svg$/));
    expect(mocks.render).not.toHaveBeenCalled();
  });

  it("initializes the runtime renderer with the light palette when the static variant is unavailable", async () => {
    window.localStorage.setItem("portfolio-theme", "light");
    mocks.render.mockResolvedValue({ svg: '<svg data-mock="light-runtime"></svg>' });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("missing static variant")));
    render(<MermaidDiagram code="graph TD; A-->B;" />);

    await waitFor(() =>
      expect(document.querySelector('.mermaid-host svg[data-mock="light-runtime"]')).not.toBeNull(),
    );
    expect(mocks.initialize).toHaveBeenCalledWith(
      expect.objectContaining({
        themeVariables: expect.objectContaining({ primaryColor: "#ffffff" }),
      }),
    );
  });
});
