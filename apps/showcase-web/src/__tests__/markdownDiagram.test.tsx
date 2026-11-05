import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderMarkdown } from "../lib/markdown";

vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async () => ({ svg: '<svg data-mock="dispatch-mermaid"></svg>' })),
  },
}));

vi.mock("../components/diagrams/LazyFlowDiagram", () => ({
  LazyFlowDiagram: ({ specId }: { specId: string }) => (
    <div data-testid="lazy-flow-diagram" data-spec-id={specId} />
  ),
}));

describe("markdown diagram fence dispatch", () => {
  it("dispatches ```diagram <spec-id> to the lazy flow viewer", () => {
    const { container } = render(<>{renderMarkdown("```diagram 09-agent-loop\n```")}</>);
    const diagram = container.querySelector("[data-testid='lazy-flow-diagram']");
    expect(diagram).toHaveAttribute("data-spec-id", "09-agent-loop");
    expect(container.querySelector(".mermaid-wrap")).toBeNull();
    expect(container.querySelector("pre.code-block")).toBeNull();
  });

  it("keeps mermaid fences on the existing renderer", async () => {
    const { container } = render(<>{renderMarkdown("```mermaid\ngraph TD; A-->B;\n```")}</>);
    expect(container.querySelector("[data-testid='lazy-flow-diagram']")).toBeNull();
    await waitFor(() => expect(container.querySelector("svg[data-mock='dispatch-mermaid']")).not.toBeNull());
  });

  it("keeps unknown fences as the exact styled pre/code fallback", () => {
    const { container } = render(<>{renderMarkdown("```flowchart\nA --> B\n```")}</>);
    expect(container.querySelector("pre.code-block code")?.textContent).toBe("A --> B");
    expect(container.querySelector("[data-testid='lazy-flow-diagram']")).toBeNull();
    expect(container.querySelector(".mermaid-wrap")).toBeNull();
  });
});
