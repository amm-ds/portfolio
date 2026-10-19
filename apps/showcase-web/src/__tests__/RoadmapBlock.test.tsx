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
  it("keeps the first sentence when the text is short", () => {
    expect(shortMilestone("Baseline retrieval with citations.")).toBe(
      "Baseline retrieval with citations.",
    );
    expect(shortMilestone("No punctuation at all")).toBe("No punctuation at all");
  });

  it("truncates long text to about 60 chars with an ellipsis", () => {
    const long =
      "End-to-end agentic workflow with retrieval, verification loops, tool use and full traceability across every single turn of the conversation";
    const label = shortMilestone(long);
    expect(label.length).toBeLessThanOrEqual(61);
    expect(label.endsWith("…")).toBe(true);
  });
});

describe("RoadmapBlock", () => {
  it("renders one timeline node per milestone with short labels and status classes", () => {
    render(<RoadmapBlock roadmap={ROADMAP} />);
    expect(screen.getByText("roadmap")).toBeInTheDocument();
    const nodes = document.querySelectorAll(".roadmap-node");
    expect(nodes).toHaveLength(4);
    // delivered dots are accent-filled, others hollow (class-driven)
    expect(document.querySelectorAll(".roadmap-node.delivered .roadmap-dot")).toHaveLength(2);
    expect(document.querySelectorAll(".roadmap-node.remaining .roadmap-dot")).toHaveLength(1);
    expect(document.querySelectorAll(".roadmap-node.deferred .roadmap-dot")).toHaveLength(1);
    // labels are the short forms, full text lives on the title attribute
    expect(nodes[0].textContent).toContain("Baseline retrieval with citations.");
    expect(nodes[3].textContent).toContain("Multilingual corpus");
    expect(nodes[1].getAttribute("title")).toBe("Reranked index with eval harness");
    expect(nodes[3].getAttribute("title")).toContain("licensing unclear");
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

  it("renders nothing for an empty or missing roadmap", () => {
    const { container: c1 } = render(<RoadmapBlock roadmap={[]} />);
    expect(c1.firstChild).toBeNull();
    cleanup();
    const { container: c2 } = render(<RoadmapBlock roadmap={undefined} />);
    expect(c2.firstChild).toBeNull();
  });
});
