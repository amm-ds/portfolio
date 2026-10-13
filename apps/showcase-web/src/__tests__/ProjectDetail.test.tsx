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
    // rail renders both section links
    expect(screen.getByRole("navigation", { name: "Case study sections" })).toBeInTheDocument();
    // markdown rendered
    expect(screen.getByText("retrieval").tagName).toBe("STRONG");
    // metric callouts with delta chip (baseline matched, +50% faithfulness)
    expect(screen.getByText("[tuned]")).toBeInTheDocument();
    expect(screen.getByText(/\+50% vs naive_last/)).toBeInTheDocument();
    // figures: story 200 case fetches plotly JSON (404 in this mock) → iframe fallback renders async
    await waitFor(() => expect(document.querySelector("iframe")).not.toBeNull());
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
});
