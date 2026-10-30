import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ProjectStoryData } from "../api";
import { CaseStudy } from "../components/CaseStudy";

const STORY: ProjectStoryData = {
  project_id: "01-rag-agent",
  // Optional schema fields — authored content leads the Background section
  // prose; the layout must not surface a standalone summary region.
  headline: "Measured answer quality improved; the judged subset remains uncertain.",
  data_note: "A bounded, licensed Wikipedia slice.",
  limits: "Does not establish quality beyond this corpus.",
  sections: [
    { id: "background", title: "Background", text_md: "Context.", figures: [], metrics_keys: [] },
    { id: "results", title: "Results", text_md: "Numbers.", figures: [], metrics_keys: [] },
  ],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("CaseStudy section rail", () => {
  it("renders the section rail and marks the active section", () => {
    let callback: IntersectionObserverCallback | null = null;
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(cb: IntersectionObserverCallback) {
          callback = cb;
        }
        observe() {}
        disconnect() {}
      },
    );

    render(<CaseStudy projectId={STORY.project_id} story={STORY} metrics={null} />);

    // no standalone summary region: the authored fields lead the Background prose
    expect(screen.queryByRole("region", { name: "Case study summary" })).toBeNull();
    // the rail and sections render in the story layout
    const layout = document.querySelector(".story-layout")!;
    expect(layout).not.toBeNull();
    expect(screen.getByRole("navigation", { name: "Case study sections" })).not.toBeNull();
    expect(screen.getByRole("heading", { name: /Background/ })).not.toBeNull();

    const background = screen.getByRole("link", { name: "01 background" });
    const results = screen.getByRole("link", { name: "02 results" });
    expect(background).not.toHaveAttribute("aria-current");
    act(() => {
      callback!(
        [
          {
            target: document.getElementById("sec-background"),
            isIntersecting: true,
            intersectionRatio: 0.75,
          } as unknown as IntersectionObserverEntry,
        ],
        {} as IntersectionObserver,
      );
    });
    expect(background).toHaveAttribute("aria-current", "location");
    expect(results).not.toHaveAttribute("aria-current");
  });

  it("renders sections without summary fields authored", () => {
    const story = { ...STORY, headline: null, data_note: null, limits: null };
    render(<CaseStudy projectId={story.project_id} story={story} metrics={null} />);
    expect(screen.queryByRole("region", { name: "Case study summary" })).toBeNull();
    expect(screen.getByRole("heading", { name: /Results/ })).not.toBeNull();
  });

  it("links each glossary term only at its first page-wide occurrence", () => {
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        observe() {}
        disconnect() {}
      },
    );
    const story: ProjectStoryData = {
      project_id: "01-rag-agent",
      sections: [
        {
          id: "background",
          title: "Background",
          text_md: "A baseline model anchors the comparison.",
          figures: [],
          metrics_keys: [],
        },
        {
          id: "results",
          title: "Results",
          text_md: "Back to the baseline in the results section.",
          figures: [],
          metrics_keys: [],
        },
      ],
    };
    render(
      <MemoryRouter>
        <CaseStudy projectId={story.project_id} story={story} metrics={null} />
      </MemoryRouter>,
    );
    // one shared Set threads both sections: the second occurrence stays plain
    const links = document.querySelectorAll("a.glossary-term");
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("href")).toBe("/glossary#baseline");
    expect(links[0].textContent).toContain("baseline");
  });
});
