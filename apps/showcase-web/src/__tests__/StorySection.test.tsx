import { readStylesCss } from "./helpers/css";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { StorySectionData } from "../api";
import { StorySection } from "../components/StorySection";
import { SECTION_SUBTITLES } from "../lib/sectionMeta";

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
    render(<StorySection projectId="01-rag-agent" section={BASE} metrics={null} />);
    expect(document.querySelector(".figure-frame")).toBeNull();
  });

  it("uses the two-column story layout structure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection
        projectId="01-rag-agent"
        section={{ ...BASE, figures: ["f"] }}
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
    render(<StorySection projectId="05-ml-pipeline-churn" section={WITH_BI} metrics={null} />);
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
    render(<StorySection projectId="05-ml-pipeline-churn" section={WITH_BI} metrics={null} />);
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
    render(<StorySection projectId="01-rag-agent" section={BASE} metrics={null} />);
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
      <StorySection projectId="05-ml-pipeline-churn" section={WITH_PLAIN} metrics={null} />,
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

describe("StorySection subtitles", () => {
  it("renders the mapped one-line muted subtitle under each known section h2", () => {
    for (const [id, text] of Object.entries(SECTION_SUBTITLES)) {
      cleanup();
      render(
        <StorySection
          projectId="01-rag-agent"
          section={{ ...BASE, id, title: id }}
          metrics={null}
        />,
      );
      const sub = document.querySelector("section > .section-subtitle");
      expect(sub, `subtitle for ${id}`).not.toBeNull();
      expect(sub!.textContent).toBe(text);
    }
  });

  it("renders no subtitle for unknown (legacy) section ids", () => {
    render(
      <StorySection
        projectId="01-rag-agent"
        section={{ ...BASE, id: "appendix", title: "Appendix" }}
        metrics={null}
      />,
    );
    expect(document.querySelector(".section-subtitle")).toBeNull();
  });
});

describe("StorySection h2 title styling", () => {
  it("paints a green title behind a green > marker with a blue section number, no glow", () => {
    const css = readStylesCss();
    const h2Rule = css.match(/\.story-section h2 \{[\s\S]*?\n\}/)![0];
    expect(h2Rule).toContain("color: var(--accent);");
    expect(h2Rule).not.toContain("text-shadow");
    // the heading and the left-rail index share one numbering: the number is
    // real markup (.sec-num), not a generated-content trick
    expect(css).not.toContain(".story-section h2 .rail-num");
    expect(css).not.toMatch(/counter-(reset|increment)/);
    expect(css).not.toContain('content: counter(');
    const h2BeforeRules = [...css.matchAll(/\.story-section h2::before \{[\s\S]*?\n\}/g)].map(
      (m) => m[0],
    );
    expect(h2BeforeRules).toHaveLength(1);
    // the "> " prompt marker stays green with no glow of its own
    const beforeRule = h2BeforeRules[0];
    expect(beforeRule).toContain('content: "> ";');
    expect(beforeRule).toContain("color: var(--accent);");
    expect(beforeRule).not.toContain("accent-glow");
    // the number renders in the rail's blue family
    const numRule = css.match(/\.story-section h2 \.sec-num \{[\s\S]*?\n\}/)![0];
    expect(numRule).toContain("color: var(--secondary);");
    // no other rule re-paints the story h2 title color (the ::before marker
    // rule is excluded — only the plain h2 rule may carry a color)
    const otherColorRules = [...css.matchAll(/\.story-section h2\s*\{[^}]*color:[^;}]+;/g)].map(
      (m) => m[0],
    );
    expect(otherColorRules).toHaveLength(1);
    expect(otherColorRules[0]).toContain("var(--accent)");
  });

  it("renders the h2 as the numbered section title — the same number the rail shows", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection
        projectId="01-rag-agent"
        section={{ ...BASE, title: "Background" }}
        metrics={null}
        index={1}
      />,
    );
    const h2 = document.querySelector(".story-section h2")!;
    expect(h2.querySelector(".rail-num")).toBeNull();
    expect(h2.querySelector(".sec-num")!.textContent).toBe("01");
    expect(h2.textContent).toBe("01Background");
  });
});

describe("StorySection conclusions details block", () => {
  const CONCLUSIONS = {
    ...BASE,
    id: "conclusions",
    title: "Details",
    text_md: "Reproduction notes and revision log.\n\n**In plain terms:** the recipe is reusable.\n",
  };

  it("legacy conclusions (no skeleton heading) keep the collapsed-body fallback", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection projectId="01-rag-agent" section={CONCLUSIONS} metrics={null} />,
    );
    const details = document.querySelector("details.story-details");
    expect(details).not.toBeNull();
    expect(details?.hasAttribute("open")).toBe(false);
    expect(details?.querySelector("summary")?.textContent).toBe(
      "Technical details — exact numbers and protocol",
    );
    expect(details?.querySelector(".story-main .prose")?.textContent).toContain(
      "Reproduction notes and revision log.",
    );
    expect(details?.querySelector(".bi-card")).toBeNull();
    const card = document.querySelector(".bi-card");
    expect(card).not.toBeNull();
    expect(card?.textContent).toContain("the recipe is reusable");
  });

  it("skeleton conclusions render the narrative visibly and only exact numbers + protocol in the dropdown", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    const skeleton = {
      ...CONCLUSIONS,
      text_md:
        "## Results summary\n\nThe final numbers with a link onward.\n\n" +
        "## What the experiment taught\n\n- The honest negative mattered.\n\n" +
        "## Limits\n\n- One machine, one run.\n\n" +
        "## Exact numbers\n\n| candidate | score |\n|---|---|\n| champion | 0.6161 |\n\n" +
        "## Protocol\n\n- 3 origins, scored once.\n\n" +
        "**Business summary:** the wrap-up in plain words.\n",
    };
    render(
      <StorySection projectId="01-rag-agent" section={skeleton} metrics={null} />,
    );
    // narrative visible outside the dropdown
    const visible = document.querySelector("section > .story-cols .prose")!;
    expect(visible.textContent).toContain("The final numbers with a link onward.");
    expect(visible.textContent).toContain("The honest negative mattered.");
    expect(visible.textContent).toContain("One machine, one run.");
    expect(visible.textContent).not.toContain("0.6161");
    // the takeaway card sits with the visible narrative, like other sections
    const card = document.querySelector("section > .story-cols .bi-card")!;
    expect(card.textContent).toContain("the wrap-up in plain words");
    // the dropdown carries ONLY the technical record
    const details = document.querySelector("details.story-details")!;
    expect(details.hasAttribute("open")).toBe(false);
    expect(details.querySelector("summary")?.textContent).toBe(
      "Technical details — exact numbers and protocol",
    );
    expect(details.textContent).toContain("champion");
    expect(details.textContent).not.toContain("The honest negative");
    // document order: h2, subtitle, visible body, then the dropdown
    const h2 = document.querySelector("section > h2")!;
    expect(h2.nextElementSibling?.classList.contains("section-subtitle")).toBe(true);
    expect(h2.nextElementSibling?.nextElementSibling?.classList.contains("story-cols")).toBe(true);
    expect(h2.nextElementSibling?.nextElementSibling?.nextElementSibling).toBe(details);
  });

  it("keeps non-conclusions sections as the plain two-column layout", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(<StorySection projectId="01-rag-agent" section={BASE} metrics={null} />);
    expect(document.querySelector("details.story-details")).toBeNull();
    expect(document.querySelector(".story-cols")).not.toBeNull();
  });
});
