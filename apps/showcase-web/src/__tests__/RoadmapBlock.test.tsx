import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { RoadmapItemData } from "../api";
import { RoadmapBlock } from "../components/RoadmapBlock";

afterEach(cleanup);

const ROADMAP: RoadmapItemData[] = [
  { status: "delivered", text: "Baseline retrieval with citations" },
  { status: "delivered", text: "Reranked index with eval harness" },
  { status: "remaining", text: "Streaming UX polish" },
  { status: "deferred", text: "Multilingual corpus — parked: licensing unclear" },
];

describe("RoadmapBlock", () => {
  it("renders delivered under 'delivered' and remaining+deferred under 'what's next'", () => {
    render(<RoadmapBlock roadmap={ROADMAP} />);
    expect(screen.getByText("roadmap")).toBeInTheDocument();
    expect(screen.getByText("Milestones achieved")).toBeInTheDocument();
    expect(screen.getByText("what's next")).toBeInTheDocument();
    expect(screen.getByText("Baseline retrieval with citations")).toBeInTheDocument();
    expect(screen.getByText("Reranked index with eval harness")).toBeInTheDocument();
    expect(screen.getByText("Streaming UX polish")).toBeInTheDocument();
    expect(screen.getByText(/Multilingual corpus/)).toBeInTheDocument();
    // status markers with distinct styling hooks
    expect(document.querySelectorAll(".roadmap-mark.delivered")).toHaveLength(2);
    expect(document.querySelectorAll(".roadmap-mark.remaining")).toHaveLength(1);
    expect(document.querySelectorAll(".roadmap-mark.deferred")).toHaveLength(1);
    // container is the shared Card
    expect(document.querySelector(".roadmap")!.classList.contains("accent-card")).toBe(true);
  });

  it("renders nothing for an empty or missing roadmap", () => {
    const { container: c1 } = render(<RoadmapBlock roadmap={[]} />);
    expect(c1.firstChild).toBeNull();
    cleanup();
    const { container: c2 } = render(<RoadmapBlock roadmap={undefined} />);
    expect(c2.firstChild).toBeNull();
  });

  it("omits the milestones group when nothing was delivered", () => {
    render(<RoadmapBlock roadmap={[{ status: "remaining", text: "v2 model sweep" }]} />);
    expect(screen.queryByText("Milestones achieved")).toBeNull();
    expect(screen.getByText("what's next")).toBeInTheDocument();
  });
});
