import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { RoadmapItemData } from "../api";
import { RoadmapBlock, shortMilestone } from "../components/RoadmapBlock";

afterEach(cleanup);

const ROADMAP: RoadmapItemData[] = [
  { status: "shipped", title: "Baseline retrieval with citations.", detail: "Recall@5 0.831 on the tuning set." },
  { status: "shipped", title: "Reranked index with eval harness.", detail: "Cross-encoder reranker adopted." },
  { status: "next", title: "Stream answers token by token.", detail: "Needs a latency budget decision." },
  { status: "blocked", title: "Add a multilingual corpus.", detail: "Blocked on the owner licence decision." },
];

describe("shortMilestone", () => {
  it("returns the full milestone text — roadmap labels never truncate", () => {
    expect(shortMilestone("Baseline retrieval with citations.")).toBe(
      "Baseline retrieval with citations.",
    );
    const long =
      "End-to-end agentic workflow with retrieval, verification loops, tool use and full traceability across every single turn of the conversation";
    expect(shortMilestone(long)).toBe(long);
  });
});

describe("RoadmapBlock", () => {
  it("renders one timeline node per shipped milestone with the title as label", () => {
    render(<RoadmapBlock roadmap={ROADMAP} />);
    expect(screen.getByText("roadmap")).toBeInTheDocument();
    const nodes = document.querySelectorAll(".roadmap-node");
    expect(nodes).toHaveLength(2);
    expect(nodes[0].classList.contains("shipped")).toBe(true);
    expect(nodes[1].classList.contains("shipped")).toBe(true);
    // labels carry the card title; the hover title adds the detail
    expect(nodes[0].textContent).toContain("Baseline retrieval with citations.");
    expect(nodes[1].getAttribute("title")).toBe(
      "Reranked index with eval harness. Cross-encoder reranker adopted.",
    );
    // nodes sit on the horizontal track
    expect(document.querySelector(".roadmap-track")).not.toBeNull();
    // container is the shared Card
    expect(document.querySelector(".roadmap")!.classList.contains("accent-card")).toBe(true);
  });

  it("does not render next or blocked cards — visitors see finalized steps only", () => {
    render(<RoadmapBlock roadmap={ROADMAP} />);
    expect(document.querySelector(".roadmap-pending")).toBeNull();
    expect(screen.queryByText("Stream answers token by token.")).toBeNull();
    expect(screen.queryByText("Needs a latency budget decision.")).toBeNull();
    expect(screen.queryByText("Multilingual corpus.")).toBeNull();
    expect(screen.queryByText("Blocked on the owner licence decision.")).toBeNull();
  });

  it("never renders a status counter", () => {
    render(<RoadmapBlock roadmap={ROADMAP} />);
    expect(screen.queryByText(/^(shipped|next|blocked): \d+$/)).toBeNull();
  });

  it("renders nothing when only next/blocked cards exist", () => {
    const { container } = render(
      <RoadmapBlock
        roadmap={[{ status: "next", title: "First milestone.", detail: "Needs a gate." }]}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when the roadmap is empty or absent", () => {
    const { container: c1 } = render(<RoadmapBlock roadmap={[]} />);
    expect(c1.firstChild).toBeNull();
    cleanup();
    const { container: c2 } = render(<RoadmapBlock roadmap={undefined} />);
    expect(c2.firstChild).toBeNull();
  });
});
