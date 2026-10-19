import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { StorySectionData } from "../api";
import { StorySection } from "../components/StorySection";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const BASE: StorySectionData = {
  id: "results",
  title: "Results",
  text_md: "Numbers.",
  figures: [],
  metrics_keys: [],
};

describe("StorySection figure layout (wave 4)", () => {
  it("renders a single figure full-width with an id-only footer (no grid)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection
        projectId="01-rag-agent"
        section={{ ...BASE, figures: ["retrieval_funnel"] }}
        index={4}
        metrics={null}
      />,
    );
    expect(document.querySelector(".figure-grid")).toBeNull();
    await waitFor(() =>
      expect(document.querySelectorAll(".figure-card")).toHaveLength(1),
    );
    const footer = document.querySelector(".figure-card-footer")!;
    expect(footer.querySelector(".figure-id")!.textContent).toBe(
      "fig :: retrieval_funnel",
    );
    expect(footer.querySelector(".figure-comment")).toBeNull();
  });

  it("stacks 2+ figures in a single column, each with its own footer", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection
        projectId="01-rag-agent"
        section={{
          ...BASE,
          figures: ["retrieval_funnel", "latency_histogram", "model_comparison"],
        }}
        index={4}
        metrics={null}
      />,
    );
    await waitFor(() =>
      expect(document.querySelectorAll(".figure-card")).toHaveLength(3),
    );
    expect(document.querySelector(".figure-grid")).toBeNull();
    const ids = [...document.querySelectorAll(".figure-id")].map(
      (el) => el.textContent,
    );
    expect(ids).toEqual([
      "fig :: retrieval_funnel",
      "fig :: latency_histogram",
      "fig :: model_comparison",
    ]);
  });

  it("renders the story figure_captions as commentary in the footers", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection
        projectId="01-rag-agent"
        section={{ ...BASE, figures: ["retrieval_funnel", "latency_histogram"] }}
        index={4}
        metrics={null}
        figureCaptions={{
          retrieval_funnel: "Recall@5 doubles after reranking.",
        }}
      />,
    );
    await waitFor(() =>
      expect(document.querySelectorAll(".figure-card")).toHaveLength(2),
    );
    const cards = document.querySelectorAll(".figure-card");
    expect(cards[0].querySelector(".figure-comment")!.textContent).toBe(
      "Recall@5 doubles after reranking.",
    );
    // no caption authored for the second figure → id-only footer
    expect(cards[1].querySelector(".figure-comment")).toBeNull();
    expect(cards[1].querySelector(".figure-id")!.textContent).toBe(
      "fig :: latency_histogram",
    );
  });

  it("renders no figure markup when the section references none", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(<StorySection projectId="01-rag-agent" section={BASE} index={4} metrics={null} />);
    expect(document.querySelector(".figure-frame")).toBeNull();
  });

  it("uses the two-column story layout structure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection
        projectId="01-rag-agent"
        section={{ ...BASE, figures: ["f"] }}
        index={0}
        metrics={null}
      />,
    );
    expect(document.querySelector(".story-cols")).not.toBeNull();
    expect(document.querySelector(".story-main")).not.toBeNull();
    expect(document.querySelector(".story-figs")).not.toBeNull();
    await waitFor(() => expect(document.querySelector("iframe")).not.toBeNull());
  });
});

describe("StorySection business-summary card", () => {
  const WITH_BI = {
    ...BASE,
    text_md:
      "Framing paragraph with some *context*.\n\n" +
      "A second paragraph before the takeaway.\n\n" +
      "**Business summary:** retention budget is a cost-minimization\n" +
      "problem, judged in money saved.\n",
  };

  it("renders the trailing **Business summary:** paragraph as a card", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(<StorySection projectId="05-ml-pipeline-churn" section={WITH_BI} index={0} metrics={null} />);
    const card = document.querySelector(".bi-card");
    expect(card).not.toBeNull();
    expect(card?.getAttribute("aria-label")).toBe("Business summary");
    expect(card?.querySelector(".bi-label")?.textContent).toBe("Business summary");
    expect(card?.textContent).toContain("retention budget is a cost-minimization");
  });

  it("still renders the legacy **Business implication:** marker as a card", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection
        projectId="05-ml-pipeline-churn"
        section={{
          ...BASE,
          text_md: "Setup prose.\n\n**Business implication:** legacy tail text.\n",
        }}
        index={0}
        metrics={null}
      />,
    );
    const card = document.querySelector(".bi-card");
    expect(card).not.toBeNull();
    expect(card?.getAttribute("aria-label")).toBe("Business summary");
    expect(card?.textContent).toContain("legacy tail text");
    expect(document.querySelector(".story-main .prose")?.textContent).toContain("Setup prose.");
  });

  it("keeps the rest of the section content unchanged outside the card", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(<StorySection projectId="05-ml-pipeline-churn" section={WITH_BI} index={0} metrics={null} />);
    const prose = document.querySelector(".story-main .prose");
    expect(prose?.textContent).toContain("Framing paragraph with some context.");
    expect(prose?.textContent).toContain("A second paragraph before the takeaway.");
    // the marker text is no longer part of the plain prose
    expect(prose?.textContent).not.toContain("Business implication");
    // only one card, holding only the tail
    expect(document.querySelectorAll(".bi-card")).toHaveLength(1);
    expect(document.querySelector(".bi-card")?.textContent).not.toContain("Framing paragraph");
  });

  it("renders no card when the section lacks the pattern", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(<StorySection projectId="01-rag-agent" section={BASE} index={0} metrics={null} />);
    expect(document.querySelector(".bi-card")).toBeNull();
    expect(document.querySelector(".story-main .prose")?.textContent).toBe("Numbers.");
  });
});
