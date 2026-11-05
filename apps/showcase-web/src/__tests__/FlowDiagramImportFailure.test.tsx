import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LazyFlowDiagram } from "../components/diagrams/LazyFlowDiagram";

vi.mock("../components/diagrams/FlowDiagram", () => {
  throw new Error("simulated lazy chunk fetch failure");
});

afterEach(cleanup);

describe("LazyFlowDiagram failure posture", () => {
  it("shows a skeleton, then a styled spec pre when the lazy chunk fetch fails", async () => {
    const { container } = render(<LazyFlowDiagram specId="04-routing" />);
    expect(screen.getByText("rendering diagram…")).toBeInTheDocument();
    await waitFor(() => {
      expect(container.querySelector("pre.flow-diagram-fallback code")?.textContent).toContain(
        "diagram 04-routing",
      );
    });
    expect(screen.queryByText("rendering diagram…")).not.toBeInTheDocument();
  });

  it("uses a styled fallback rather than crashing on an unknown spec", async () => {
    const { container } = render(<LazyFlowDiagram specId="missing" />);
    await waitFor(() => {
      expect(container.querySelector("pre.flow-diagram-fallback code")?.textContent).toContain(
        "diagram missing",
      );
    });
  });
});
