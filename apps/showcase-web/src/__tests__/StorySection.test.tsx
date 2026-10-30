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
    const footer = document.querySelector(".figure-card-band")!;
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

  it("treats the legacy **Business implication:** marker as plain prose (fallback removed)", () => {
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
    expect(document.querySelector(".bi-card")).toBeNull();
    const prose = document.querySelector(".story-main .prose")!;
    expect(prose.textContent).toContain("Setup prose.");
    expect(prose.textContent).toContain("Business implication: legacy tail text.");
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

describe("StorySection **In plain terms:** marker", () => {
  const WITH_PLAIN = {
    ...BASE,
    text_md:
      "Framing paragraph with some *context*.\n\n" +
      "**In plain terms:** the model flags the customers most likely to leave.\n",
  };

  it("renders the trailing **In plain terms:** paragraph as the card", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection projectId="05-ml-pipeline-churn" section={WITH_PLAIN} index={0} metrics={null} />,
    );
    const card = document.querySelector(".bi-card");
    expect(card).not.toBeNull();
    expect(card?.getAttribute("aria-label")).toBe("In plain terms");
    expect(card?.querySelector(".bi-label")?.textContent).toBe("In plain terms");
    expect(card?.textContent).toContain("the model flags the customers most likely to leave");
    // the marker itself is stripped from the plain prose
    expect(document.querySelector(".story-main .prose")?.textContent).not.toContain(
      "In plain terms",
    );
  });

  it("prefers **In plain terms:** over a later **Business summary:** marker", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection
        projectId="05-ml-pipeline-churn"
        section={{
          ...BASE,
          text_md:
            "Setup prose.\n\n" +
            "**In plain terms:** preferred tail.\n\n" +
            "**Business summary:** later tail.\n",
        }}
        index={0}
        metrics={null}
      />,
    );
    const card = document.querySelector(".bi-card")!;
    expect(card.textContent).toContain("preferred tail");
    // the In-plain-terms tail (not the later Business summary marker) is the card content
    const prose = document.querySelector(".story-main .prose")!;
    expect(prose.textContent).not.toContain("preferred tail");
  });
});

describe("StorySection conclusions details block", () => {
  const CONCLUSIONS = {
    ...BASE,
    id: "conclusions",
    title: "Details",
    text_md: "Reproduction notes and revision log.\n\n**In plain terms:** the recipe is reusable.\n",
  };

  it("wraps the conclusions body in a native collapsed details block after the h2", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection projectId="01-rag-agent" section={CONCLUSIONS} index={7} metrics={null} />,
    );
    const details = document.querySelector("details.story-details");
    expect(details).not.toBeNull();
    // collapsed by default
    expect(details?.hasAttribute("open")).toBe(false);
    expect(details?.querySelector("summary")?.textContent).toBe(
      "Technical details, revision notes, and reproduction",
    );
    // existing prose renders inside the block
    expect(details?.querySelector(".story-main .prose")?.textContent).toContain(
      "Reproduction notes and revision log.",
    );
    // the takeaway card stays visible above the collapsed block
    expect(details?.querySelector(".bi-card")).toBeNull();
    const card = document.querySelector(".bi-card");
    expect(card).not.toBeNull();
    expect(card?.textContent).toContain("the recipe is reusable");
    // document order: h2, then the card, then the details block
    const h2 = document.querySelector("section > h2")!;
    expect(h2.textContent).toContain("Details");
    expect(h2.nextElementSibling).toBe(card);
    expect(card?.nextElementSibling).toBe(details);
  });

  it("keeps non-conclusions sections as the plain two-column layout", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(<StorySection projectId="01-rag-agent" section={BASE} index={0} metrics={null} />);
    expect(document.querySelector("details.story-details")).toBeNull();
    expect(document.querySelector(".story-cols")).not.toBeNull();
  });
});
