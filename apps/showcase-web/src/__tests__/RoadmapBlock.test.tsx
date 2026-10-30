import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { RoadmapItemData } from "../api";
import { RoadmapBlock, shortMilestone } from "../components/RoadmapBlock";

afterEach(cleanup);

const ROADMAP: RoadmapItemData[] = [
  { status: "delivered", text: "Baseline retrieval with citations." },
  { status: "delivered", text: "Reranked index with eval harness" },
  { status: "remaining", text: "Streaming UX polish" },
  { status: "deferred", text: "Multilingual corpus — parked: licensing unclear" },
];

describe("shortMilestone", () => {
  it("returns the full milestone text — roadmap nodes never truncate", () => {
    expect(shortMilestone("Baseline retrieval with citations.")).toBe(
      "Baseline retrieval with citations.",
    );
    const long =
      "End-to-end agentic workflow with retrieval, verification loops, tool use and full traceability across every single turn of the conversation";
    expect(shortMilestone(long)).toBe(long);
  });
});

describe("RoadmapBlock", () => {
  it("renders one timeline node per delivered milestone with full labels", () => {
    render(<RoadmapBlock roadmap={ROADMAP} />);
    expect(screen.getByText("roadmap")).toBeInTheDocument();
    const nodes = document.querySelectorAll(".roadmap-node");
    // open/deferred items are authoring state; visitors see shipped work only
    expect(nodes).toHaveLength(2);
    expect(nodes[0].classList.contains("delivered")).toBe(true);
    expect(nodes[1].classList.contains("delivered")).toBe(true);
    // labels contain the full milestone, also available on the title attribute
    expect(nodes[0].textContent).toContain("Baseline retrieval with citations.");
    expect(nodes[1].getAttribute("title")).toBe("Reranked index with eval harness");
    // nodes sit on the horizontal track
    expect(document.querySelector(".roadmap-track")).not.toBeNull();
    // container is the shared Card
    expect(document.querySelector(".roadmap")!.classList.contains("accent-card")).toBe(true);
  });

  it("never renders a delivered counter (redundant with the all-delivered dots)", () => {
    render(
      <RoadmapBlock
        roadmap={[
          { status: "delivered", text: "First milestone" },
          { status: "delivered", text: "Second milestone" },
        ]}
      />,
    );
    expect(screen.queryByText(/delivered$/)).toBeNull();
    expect(document.querySelectorAll(".roadmap-node.delivered")).toHaveLength(2);
  });

  it("hides the counter while work remains", () => {
    render(<RoadmapBlock roadmap={ROADMAP} />);
    expect(screen.queryByText(/delivered$/)).toBeNull();
  });

  it("renders nothing when no milestone is delivered yet", () => {
    const { container: c1 } = render(<RoadmapBlock roadmap={[]} />);
    expect(c1.firstChild).toBeNull();
    cleanup();
    const { container: c2 } = render(<RoadmapBlock roadmap={undefined} />);
    expect(c2.firstChild).toBeNull();
    cleanup();
    // open/deferred-only roadmaps have nothing to show visitors yet
    const { container: c3 } = render(
      <RoadmapBlock roadmap={[{ status: "remaining", text: "Open thing" }]} />,
    );
    expect(c3.firstChild).toBeNull();
  });
});
