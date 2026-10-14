import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Project } from "../api";
import { ProjectsIndex, groupByTopic } from "../pages/ProjectsIndex";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function project(over: Partial<Project>): Project {
  return {
    id: "01-rag-agent",
    title: "RAG Agent",
    domain: "NLP",
    topic: "agentic ai",
    techniques: ["RAG"],
    data: "docs",
    status: "flagship",
    order: 1,
    ...over,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("groupByTopic", () => {
  it("groups by topic, topics by earliest order, projects by order", () => {
    const groups = groupByTopic([
      project({ id: "03-x", topic: "detection", order: 3 }),
      project({ id: "01-a", topic: "agents", order: 1 }),
      project({ id: "02-b", topic: "agents", order: 2 }),
    ]);
    expect(groups.map((g) => g.topic)).toEqual(["agents", "detection"]);
    expect(groups[0].projects.map((p) => p.id)).toEqual(["01-a", "02-b"]);
  });
});

describe("ProjectsIndex", () => {
  it("renders topic groups and no status badges", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse([
          project({ id: "03-anomaly", title: "Anomaly", topic: "anomaly detection", order: 3, status: "working" }),
          project({ id: "01-rag-agent", title: "RAG Agent", topic: "agentic ai", order: 1 }),
          project({ id: "07-mobility", title: "Mobility", topic: "agentic ai", order: 7, status: "working" }),
        ]),
      ),
    );
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("agentic ai")).toBeInTheDocument());
    expect(screen.getByText("anomaly detection")).toBeInTheDocument();
    // agentic ai group first (earliest order) and holds its two projects in order
    const agenticHeading = screen.getByText("agentic ai");
    const grid = agenticHeading.nextElementSibling!;
    const titles = [...grid.querySelectorAll(".project-card h3")].map((el) => el.textContent);
    expect(titles).toEqual(["RAG Agent", "Mobility"]);
    // no status badges anywhere
    expect(document.querySelector(".badge")).toBeNull();
    expect(screen.queryByText("[flagship]")).toBeNull();
  });

  it("renders a live key number from metrics (first non-baseline run)", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith("/projects")) return Promise.resolve(jsonResponse([project({})]));
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
      if (url.endsWith("/projects")) return Promise.resolve(jsonResponse([project({})]));
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
