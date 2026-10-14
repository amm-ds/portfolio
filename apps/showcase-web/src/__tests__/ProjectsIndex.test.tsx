import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectsIndex } from "../pages/ProjectsIndex";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const RAG = {
  id: "01-rag-agent",
  title: "RAG Agent",
  domain: "NLP",
  techniques: ["RAG"],
  data: "docs",
  status: "flagship",
  order: 1,
};

const DEMAND = {
  id: "02-demand-forecasting",
  title: "Demand Forecasting",
  domain: "time series",
  techniques: ["LightGBM"],
  data: "retail",
  status: "working",
  order: 2,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ProjectsIndex", () => {
  it("groups projects under flagships and working showcases", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([DEMAND, RAG])));
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("RAG Agent")).toBeInTheDocument());
    expect(screen.getByText("flagships")).toBeInTheDocument();
    expect(screen.getByText("working showcases")).toBeInTheDocument();
    // flagship before working group; each card keeps its badge
    const flagshipGroup = screen.getByText("flagships").nextElementSibling!;
    expect(flagshipGroup.querySelector(".project-card h3")?.textContent).toBe("RAG Agent");
    expect(screen.getByText("[flagship]")).toBeInTheDocument();
    expect(screen.getByText("[working]")).toBeInTheDocument();
  });

  it("renders a live key number from metrics (first non-baseline run)", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith("/projects")) return Promise.resolve(jsonResponse([RAG]));
      if (url.endsWith("/metrics")) {
        return Promise.resolve(
          jsonResponse({ naive_last: { mae: 100 }, tuned: { mae: 72.34567 } }),
        );
      }
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("mae: 72.3457")).toBeInTheDocument());
  });

  it("renders no key number when metrics are missing", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith("/projects")) return Promise.resolve(jsonResponse([RAG]));
      return Promise.resolve(jsonResponse({ detail: "no" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("RAG Agent")).toBeInTheDocument());
    expect(document.querySelector(".key-number")).toBeNull();
  });

  it("shows an empty state when /projects returns []", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/no projects published yet/i)).toBeInTheDocument());
  });

  it("shows an error state when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/could not load/i)).toBeInTheDocument());
  });
});
