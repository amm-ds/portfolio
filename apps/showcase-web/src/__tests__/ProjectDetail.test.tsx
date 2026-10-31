import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectDetail } from "../pages/ProjectDetail";

const PROJECT = {
  id: "01-rag-agent",
  title: "RAG Agent",
  domain: "NLP",
  techniques: ["RAG", "FastAPI"],
  data: "docs",
  status: "flagship",
  order: 1,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockFetch(handler: (path: string) => Response | Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    return Promise.resolve(handler(url));
  }));
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={["/projects/01-rag-agent"]}>
      <Routes>
        <Route path="/projects/:id" element={<ProjectDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ProjectDetail story handling", () => {
  it("renders the case study when /story returns 200", async () => {
    mockFetch((path) => {
      if (path.endsWith("/projects")) return Promise.resolve(jsonResponse([PROJECT]));
      if (path.endsWith("/story")) {
        return Promise.resolve(
          jsonResponse({
            project_id: "01-rag-agent",
            short_version: "A question-answering assistant that cites every claim.",
            figure_captions: {
              retrieval_eval: "Verified answers beat the naive baseline on faithfulness.",
            },
            roadmap: [
              { status: "delivered", text: "Baseline retrieval with citations" },
              { status: "remaining", text: "Streaming UX polish" },
              { status: "deferred", text: "Multilingual corpus — licensing" },
            ],
            sections: [
              {
                id: "background",
                title: "Background",
                text_md: "A **retrieval** assistant with `citations`.",
                figures: ["retrieval_eval"],
                metrics_keys: ["naive_last", "tuned"],
              },
              {
                id: "results",
                title: "Results",
                text_md: "End to end numbers.",
                figures: [],
                metrics_keys: [],
              },
            ],
          }),
        );
      }
      if (path.endsWith("/metrics")) {
        return Promise.resolve(
          jsonResponse({ naive_last: { faithfulness: 0.5 }, tuned: { faithfulness: 0.75 } }),
        );
      }
      return Promise.resolve(jsonResponse({}, 404));
    });

    renderDetail();
    await waitFor(() => expect(screen.getByText("Background")).toBeInTheDocument());
    expect(screen.getByText("Results")).toBeInTheDocument();
    // the story's short_version leads the header as a muted lead paragraph
    expect(document.querySelector(".detail-lead")!.textContent).toBe(
      "A question-answering assistant that cites every claim.",
    );
    // rail renders both section links
    expect(screen.getByRole("navigation", { name: "Case study sections" })).toBeInTheDocument();
    // markdown rendered
    expect(screen.getByText("retrieval").tagName).toBe("STRONG");
    // story results table with delta (baseline matched, +50% faithfulness)
    expect(screen.getByText("tuned")).toBeInTheDocument();
    expect(screen.getByText(/\+50% vs naive_last/)).toBeInTheDocument();
    // figures: story 200 case fetches plotly JSON (404 in this mock) → iframe fallback renders async
    await waitFor(() => expect(document.querySelector("iframe")).not.toBeNull());
    // roadmap renders at the end of the case study as a timeline of delivered milestones
    expect(screen.getByText("Baseline retrieval with citations")).toBeInTheDocument();
    // open/deferred items are authoring state, not visitor content
    expect(screen.queryByText("Streaming UX polish")).toBeNull();
    expect(screen.queryByText(/Multilingual corpus/)).toBeNull();
    expect(document.querySelectorAll(".roadmap-node.delivered .roadmap-dot")).toHaveLength(1);
    // figure_captions from the story payload thread through to the figure footer
    expect(document.querySelector(".figure-comment")!.textContent).toContain(
      "Verified answers beat the naive baseline on faithfulness.",
    );
  });

  it("falls back to the metrics table + figures view when /story returns 404", async () => {
    mockFetch((path) => {
      if (path.endsWith("/projects")) return Promise.resolve(jsonResponse([PROJECT]));
      if (path.endsWith("/story")) return Promise.resolve(jsonResponse({ detail: "no story" }, 404));
      if (path.endsWith("/metrics")) return Promise.resolve(jsonResponse({ baseline: { f1: 0.5 } }));
      if (path.endsWith("/figures")) return Promise.resolve(jsonResponse(["eval_fig"]));
      return Promise.resolve(jsonResponse({}, 404));
    });

    renderDetail();
    await waitFor(() => expect(screen.getByText("baseline")).toBeInTheDocument());
    // fallback metrics table rendered, no case-study rail
    expect(screen.queryByRole("navigation", { name: "Case study sections" })).toBeNull();
    expect(screen.getByText("0.5000")).toBeInTheDocument();
    // code chip links to the project's directory in the repo (fallback branch too)
    expect(screen.getByRole("link", { name: "[code]" })).toHaveAttribute(
      "href",
      "https://github.com/amm-ds/portfolio/tree/main/projects/01-rag-agent",
    );
    // header links use the spaced chip pattern
    const metaLinks = document.querySelectorAll(".meta-links .chip-link");
    expect(metaLinks).toHaveLength(3);
  });

  it("shows the run-pipeline hint when both story and metrics are missing", async () => {
    mockFetch((path) => {
      if (path.endsWith("/projects")) return Promise.resolve(jsonResponse([PROJECT]));
      return Promise.resolve(jsonResponse({ detail: "not found" }, 404));
    });

    renderDetail();
    await waitFor(() => expect(screen.getAllByText(/run the pipeline/i).length).toBeGreaterThan(0));
    expect(screen.queryByRole("navigation", { name: "Case study sections" })).toBeNull();
  });

  it("shows an unknown-project state for ids not in the index", async () => {
    mockFetch((path) => {
      if (path.endsWith("/projects")) return Promise.resolve(jsonResponse([PROJECT]));
      return Promise.resolve(jsonResponse({ detail: "not found" }, 404));
    });

    render(
      <MemoryRouter initialEntries={["/projects/99-nope"]}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/unknown project/i)).toBeInTheDocument());
  });

  it("renders a prominent demo banner between the header and the case study when a demo is registered", async () => {
    const manifest = {
      id: "rag-playground",
      title: "RAG playground",
      hook: "Shuffle the retrieval knobs and watch the judged faithfulness answer update.",
      project: "01-rag-agent",
      group: "ask your documents",
      skills: [],
      modes: [],
      hero: null,
      scenarios: [],
      live_endpoints: [],
      payload: { path: "/demos/rag-playground/payload", schema_version: 1, required_keys: [] },
    };
    mockFetch((path) => {
      if (path.endsWith("/projects")) return Promise.resolve(jsonResponse([PROJECT]));
      if (path.endsWith("/demos")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: "rag-playground",
              title: "RAG playground",
              hook: "Registry hook line for the RAG demo.",
              group: "ask your documents",
              href: "/demos/rag-playground",
              project: "01-rag-agent",
              status: "live",
              hero: null,
            },
          ]),
        );
      }
      if (path.endsWith("/demos/rag-playground/manifest")) {
        return Promise.resolve(jsonResponse(manifest));
      }
      if (path.endsWith("/story")) {
        return Promise.resolve(
          jsonResponse({
            project_id: "01-rag-agent",
            sections: [
              {
                id: "background",
                title: "Background",
                text_md: "Context.",
                figures: [],
                metrics_keys: [],
              },
            ],
          }),
        );
      }
      return Promise.resolve(jsonResponse({}, 404));
    });

    renderDetail();
    await waitFor(() =>
      expect(document.querySelector(".demo-banner")).not.toBeNull(),
    );
    const banner = document.querySelector(".demo-banner")!;
    // accent-bordered card, primary CTA to the demo route
    expect(banner.classList.contains("accent-card")).toBe(true);
    const cta = banner.querySelector(".demo-banner-cta")!;
    expect(cta.textContent).toContain("▶ try the live demo");
    expect(cta.getAttribute("href")).toBe("/demos/rag-playground");
    // the description line comes from the demo manifest
    expect(banner.querySelector(".demo-banner-line")!.textContent).toBe(manifest.hook);
    // banner sits between the detail header and the case study
    const header = document.querySelector(".detail-header")!;
    const layout = document.querySelector(".story-layout")!;
    expect(
      header.compareDocumentPosition(banner) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      banner.compareDocumentPosition(layout) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // the header action row keeps its own demo chip-link alongside the banner CTA
    expect(screen.getAllByRole("link", { name: "▶ try the live demo" })).toHaveLength(2);
  });

  it("falls back to the registry hook line when the demo manifest is unreachable", async () => {
    mockFetch((path) => {
      if (path.endsWith("/projects")) return Promise.resolve(jsonResponse([PROJECT]));
      if (path.endsWith("/demos")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: "rag-playground",
              title: "RAG playground",
              hook: "Registry hook line for the RAG demo.",
              group: "ask your documents",
              href: "/demos/rag-playground",
              project: "01-rag-agent",
              status: "live",
              hero: null,
            },
          ]),
        );
      }
      if (path.endsWith("/story")) {
        return Promise.resolve(
          jsonResponse({
            project_id: "01-rag-agent",
            sections: [
              {
                id: "background",
                title: "Background",
                text_md: "Context.",
                figures: [],
                metrics_keys: [],
              },
            ],
          }),
        );
      }
      return Promise.resolve(jsonResponse({ detail: "no manifest" }, 404));
    });

    renderDetail();
    await waitFor(() =>
      expect(document.querySelector(".demo-banner-line")).not.toBeNull(),
    );
    expect(document.querySelector(".demo-banner-line")!.textContent).toBe(
      "Registry hook line for the RAG demo.",
    );
  });
});
