import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderMarkdown } from "../lib/markdown";

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
    expect(container.querySelector("pre.code-block")).toBeNull();
  });

  it("keeps unknown fences, including mermaid, as the exact styled pre/code fallback", () => {
    const { container } = render(<>{renderMarkdown("```flowchart\nA --> B\n```")}</>);
    expect(container.querySelector("pre.code-block code")?.textContent).toBe("A --> B");
    expect(container.querySelector("[data-testid='lazy-flow-diagram']")).toBeNull();
  });
});
