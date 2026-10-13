import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MermaidDiagram } from "../components/MermaidDiagram";

const mocks = vi.hoisted(() => ({
  initialize: vi.fn(),
  render: vi.fn(),
}));

vi.mock("mermaid", () => ({
  default: { initialize: mocks.initialize, render: mocks.render },
}));

afterEach(() => {
  cleanup();
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
});
