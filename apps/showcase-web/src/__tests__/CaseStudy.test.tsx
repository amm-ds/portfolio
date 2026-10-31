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
    // the rail carries a small uppercase "index" label above the links
    expect(document.querySelector(".rail-label")!.textContent).toBe("index");
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

describe("CaseStudy key concepts card", () => {
  const CONCEPTS = [
    "**Retrieval** — finding the passages that answer the question.",
    "**Reranking** — rescoring candidates with a cross-encoder before answering.",
  ];

  it("renders the story's key_concepts as `**Term** — sentence` markdown, before the glossary card", () => {
    const story: ProjectStoryData = {
      ...STORY,
      key_concepts: CONCEPTS,
      sections: [
        { id: "background", title: "Background", text_md: "Context with a baseline model.", figures: [], metrics_keys: [] },
        { id: "results", title: "Results", text_md: "Numbers.", figures: [], metrics_keys: [] },
      ],
    };
    render(
      <MemoryRouter>
        <CaseStudy projectId={story.project_id} story={story} metrics={null} />
      </MemoryRouter>,
    );
    const card = document.querySelector(".key-concepts-card")!;
    expect(card).not.toBeNull();
    expect(card.getAttribute("aria-label")).toBe("Key concepts");
    expect(card.querySelector(".glossary-card-label")!.textContent).toBe("key concepts");
    const items = [...card.querySelectorAll(".key-concepts-list li")];
    expect(items).toHaveLength(2);
    // `**Term**` renders as bold lead, the rest as the sentence
    expect(items[0].querySelector("strong")!.textContent).toBe("Retrieval");
    expect(items[0].textContent).toContain("finding the passages");
    expect(items[1].querySelector("strong")!.textContent).toBe("Reranking");
    // sits right after the Background section, BEFORE the glossary card
    const background = document.getElementById("sec-background")!;
    const glossary = document.querySelector(".glossary-card:not(.key-concepts-card)")!;
    expect(
      background.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      card.compareDocumentPosition(glossary) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // same accent-left card pattern as the glossary card
    expect(card.classList.contains("accent-card") || card.classList.contains("glossary-card")).toBe(
      true,
    );
  });

  it("renders no key concepts card when key_concepts is absent or empty", () => {
    const absent = render(
      <MemoryRouter>
        <CaseStudy projectId={STORY.project_id} story={STORY} metrics={null} />
      </MemoryRouter>,
    );
    expect(document.querySelector(".key-concepts-card")).toBeNull();
    absent.unmount();
    render(
      <MemoryRouter>
        <CaseStudy
          projectId={STORY.project_id}
          story={{ ...STORY, key_concepts: [] }}
          metrics={null}
        />
      </MemoryRouter>,
    );
    expect(document.querySelector(".key-concepts-card")).toBeNull();
  });
});

describe("CaseStudy glossary card cap", () => {
  it("caps the background glossary card at 10 terms even when the story uses more", () => {
    const story: ProjectStoryData = {
      project_id: "02-demand-forecasting",
      sections: [
        {
          id: "background",
          title: "Background",
          text_md:
            "The study names a baseline, holdout, backtest, confidence interval, WAPE, MASE, " +
            "macro-F1, recall@5, uplift, Qini curve, optimality gap, p50/p95 latency, " +
            "calibration, and a seasonal naive reference.",
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
    const rows = document.querySelectorAll(".glossary-card .glossary-card-row");
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.length).toBeLessThanOrEqual(10);
  });
});
