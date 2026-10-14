import { readFileSync } from "node:fs";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Project } from "../api";
import { ProjectsIndex, groupByTopic, groupByUmbrella } from "../pages/ProjectsIndex";

const stylesCss = readFileSync("src/styles.css", "utf8");

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
    topic: "Agentic AI & LLM",
    techniques: ["RAG"],
    data: "docs",
    status: "flagship",
    order: 1,
    ...over,
  };
}

/** The seven real projects with their manifest topics/orders. */
const ALL_PROJECTS: Project[] = [
  project({ id: "01-rag-agent", topic: "Agentic AI & LLM", order: 1 }),
  project({ id: "02-demand-forecasting", title: "Demand Forecasting", topic: "Forecasting & Time Series", order: 2 }),
  project({ id: "03-anomaly-detection", title: "Anomaly", topic: "Anomaly Detection", order: 3 }),
  project({ id: "04-nlp-classification", title: "NLP Classification", topic: "NLP & Transformers", order: 4 }),
  project({ id: "05-ml-pipeline-churn", title: "Churn", topic: "ML Systems & Decisioning", order: 5 }),
  project({ id: "06-routing-optimization", title: "Routing", topic: "Optimization", order: 6 }),
  project({ id: "07-open-data-mobility", title: "Mobility", topic: "Large-Scale Data Engineering", order: 7 }),
];

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("groupByUmbrella", () => {
  it("nests topics under umbrellas in display order (AI, ML, Data Engineering)", () => {
    const umbrellas = groupByUmbrella(ALL_PROJECTS);
    expect(umbrellas.map((u) => u.name)).toEqual(["AI", "Machine Learning", "Data Engineering"]);
    expect(umbrellas[0].topics.map((t) => t.topic)).toEqual([
      "Agentic AI & LLM",
      "NLP & Transformers",
    ]);
    expect(umbrellas[1].topics.map((t) => t.topic)).toEqual([
      "Forecasting & Time Series",
      "Anomaly Detection",
      "ML Systems & Decisioning",
      "Optimization",
    ]);
    expect(umbrellas[2].topics.map((t) => t.topic)).toEqual([
      "Large-Scale Data Engineering",
    ]);
    // every project is placed exactly once
    expect(umbrellas.flatMap((u) => u.topics.flatMap((t) => t.projects))).toHaveLength(7);
  });

  it("drops umbrellas with no projects and orders topics by earliest project", () => {
    const partial = ALL_PROJECTS.filter((p) =>
      ["06-routing-optimization", "01-rag-agent"].includes(p.id),
    );
    const umbrellas = groupByUmbrella(partial);
    expect(umbrellas.map((u) => u.name)).toEqual(["AI", "Machine Learning"]);
    expect(umbrellas[1].topics.map((t) => t.topic)).toEqual(["Optimization"]);
  });

  it("groupByTopic stays available and unchanged", () => {
    const topics = groupByTopic([ALL_PROJECTS[6], ALL_PROJECTS[0]]);
    expect(topics.map((t) => t.topic)).toEqual(["Agentic AI & LLM", "Large-Scale Data Engineering"]);
  });
});

describe("ProjectsIndex", () => {
  it("places cards under the right umbrella/topic and keeps topic subheadings only for multi-topic umbrellas", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(ALL_PROJECTS)));
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("AI")).toBeInTheDocument());
    expect(screen.getByText("Machine Learning")).toBeInTheDocument();
    expect(screen.getByText("Data Engineering")).toBeInTheDocument();

    // AI has 2 topics → topic subheadings
    expect(screen.getByText("Agentic AI & LLM")).toBeInTheDocument();
    expect(screen.getByText("NLP & Transformers")).toBeInTheDocument();
    // ML has 4 topics → subheadings
    expect(screen.getByText("Optimization")).toBeInTheDocument();
    // Data Engineering has 1 topic → no topic subheading
    expect(screen.queryByText("Large-Scale Data Engineering")).toBeNull();

    // card-per-topic placement: 01 under AI, 06 under ML/Optimization, 07 under Data Engineering
    const cardOf = (title: string) =>
      [...document.querySelectorAll(".project-card")].find((c) =>
        c.querySelector("h3")?.textContent === title,
      )!;
    const sectionOf = (el: Element, cls: string): Element | null => {
      let cur: Element | null = el;
      while (cur && !cur.classList.contains(cls)) cur = cur.parentElement;
      return cur;
    };
    const routing = cardOf("Routing");
    const mlSection = sectionOf(routing, "umbrella")!;
    expect(mlSection.querySelector("h2")!.textContent).toBe("Machine Learning");
    expect(sectionOf(routing, "topic-group")!.querySelector("h3")!.textContent).toBe("Optimization");

    const rag = cardOf("RAG Agent");
    expect(sectionOf(rag, "umbrella")!.querySelector("h2")!.textContent).toBe("AI");

    const mobility = cardOf("Mobility");
    const deGroup = sectionOf(mobility, "topic-group")!;
    expect(deGroup.querySelector(":scope > h3")).toBeNull(); // single-topic umbrella: no subheading
  });

  it("renders every topic's cards inside the responsive project-grid", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(ALL_PROJECTS)));
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.querySelectorAll(".project-card")).toHaveLength(7));
    const grids = document.querySelectorAll(".project-grid");
    expect(grids).toHaveLength(7); // one grid per topic group
    grids.forEach((g) => expect(g.querySelectorAll(".project-card").length).toBeGreaterThan(0));
    // no status badges
    expect(document.querySelector(".badge")).toBeNull();
  });

  it("ships responsive grid breakpoints (1 / 2 / 3 columns)", () => {
    expect(stylesCss).toContain("grid-template-columns: 1fr;");
    expect(stylesCss).toContain("@media (min-width: 720px)");
    expect(stylesCss).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(stylesCss).toContain("@media (min-width: 1100px)");
    expect(stylesCss).toContain("grid-template-columns: repeat(3, minmax(0, 1fr));");
    expect(stylesCss).toContain("align-items: stretch;");
  });

  it("renders a live key number from metrics (first non-baseline run)", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith("/projects")) return Promise.resolve(jsonResponse([ALL_PROJECTS[0]]));
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
      if (url.endsWith("/projects")) return Promise.resolve(jsonResponse([ALL_PROJECTS[0]]));
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
