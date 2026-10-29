import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ProjectStoryData } from "../api";
import { CaseStudy } from "../components/CaseStudy";

const STORY: ProjectStoryData = {
  project_id: "01-rag-agent",
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

describe("CaseStudy summary and section rail", () => {
  it("renders authored summary fields before the rail and marks the active section", () => {
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

    const summary = screen.getByRole("region", { name: "Case study summary" });
    expect(summary).toHaveTextContent(STORY.headline!);
    expect(summary).toHaveTextContent(STORY.data_note!);
    expect(summary).toHaveTextContent(STORY.limits!);
    const layout = document.querySelector(".story-layout")!;
    expect(summary.compareDocumentPosition(layout) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

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

  it("omits the summary when no summary fields are authored", () => {
    const story = { ...STORY, headline: null, data_note: null, limits: null };
    render(<CaseStudy projectId={story.project_id} story={story} metrics={null} />);
    expect(screen.queryByRole("region", { name: "Case study summary" })).toBeNull();
  });
});
