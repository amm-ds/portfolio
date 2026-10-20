import { readFileSync } from "node:fs";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Project } from "../api";
import { ProjectsIndex, groupByTopic, groupByRow, TOPIC_ROWS } from "../pages/ProjectsIndex";

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

/** The seven real projects with their manifest topics/orders (07 now "Data Engineering"). */
const ALL_PROJECTS: Project[] = [
  project({ id: "01-rag-agent", topic: "Agentic AI & LLM", order: 1 }),
  project({ id: "02-demand-forecasting", title: "Demand Forecasting", topic: "Forecasting & Time Series", order: 2 }),
  project({ id: "03-anomaly-detection", title: "Anomaly", topic: "Anomaly Detection", order: 3 }),
  project({ id: "04-nlp-classification", title: "NLP Classification", topic: "NLP & Transformers", order: 4 }),
  project({ id: "05-ml-pipeline-churn", title: "Churn", topic: "ML Systems & Decisioning", order: 5 }),
  project({ id: "06-routing-optimization", title: "Routing", topic: "Optimization", order: 6 }),
  project({ id: "07-open-data-mobility", title: "Mobility", topic: "Data Engineering", order: 7 }),
];

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("groupByRow", () => {
  it("nests topics under impact-ordered rows (Agentic AI & LLM … Data Engineering)", () => {
    const rows = groupByRow(ALL_PROJECTS);
    expect(rows.map((r) => r.name)).toEqual([
      "Agentic AI & LLM",
      "Machine Learning",
      "Optimization",
      "Data Engineering",
    ]);
    expect(rows[0].topics.map((t) => t.topic)).toEqual(["Agentic AI & LLM"]);
    expect(rows[1].topics.map((t) => t.topic)).toEqual([
      "Forecasting & Time Series",
      "Anomaly Detection",
      "NLP & Transformers",
      "ML Systems & Decisioning",
    ]);
    // every project is placed exactly once
    expect(rows.flatMap((r) => r.topics.flatMap((t) => t.projects))).toHaveLength(7);
  });

  it("places 07 under the Data Engineering row", () => {
    const rows = groupByRow(ALL_PROJECTS);
    const de = rows.find((r) => r.name === "Data Engineering")!;
    expect(de.topics.flatMap((t) => t.projects).map((p) => p.id)).toEqual([
      "07-open-data-mobility",
    ]);
  });

  it("drops empty rows and maps unmapped topics to their own trailing row", () => {
    const partial = ALL_PROJECTS.filter((p) =>
      ["06-routing-optimization", "01-rag-agent"].includes(p.id),
    );
    const rows = groupByRow(partial);
    expect(rows.map((r) => r.name)).toEqual(["Agentic AI & LLM", "Optimization"]);

    const withUnknown = [...partial, project({ id: "99-x", topic: "Something New", order: 9 })];
    const rows2 = groupByRow(withUnknown);
    expect(rows2[rows2.length - 1].name).toBe("Something New");
  });

  it("groupByTopic stays available and unchanged", () => {
    const topics = groupByTopic([ALL_PROJECTS[6], ALL_PROJECTS[0]]);
    expect(topics.map((t) => t.topic)).toEqual(["Agentic AI & LLM", "Data Engineering"]);
  });

  it("TOPIC_ROWS lists every topic used by the ten portfolio.yaml manifests", () => {
    const mapped = new Set(TOPIC_ROWS.flatMap((r) => r.topics));
    for (const topic of [
      "Agentic AI & LLM",
      "Forecasting & Time Series",
      "Anomaly Detection",
      "NLP & Transformers",
      "ML Systems & Decisioning",
      "Optimization",
      "Decision Science",
      "Data Engineering",
    ]) {
      expect(mapped.has(topic)).toBe(true);
    }
  });
});

describe("ProjectsIndex", () => {
  it("renders the projects heading and places cards under the right topic rows", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(ALL_PROJECTS)));
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("projects"),
    );
    // the experiments block label sits above the topic rows
    const experimentsBlock = document.querySelector(".experiments-block")!;
    expect(experimentsBlock).not.toBeNull();
    expect(
      experimentsBlock.querySelector(":scope > .section-title")!.textContent,
    ).toBe("experiments");
    expect(screen.getByText("Machine Learning")).toBeInTheDocument();
    // row heading plus 07's sub-topic chip both carry the name
    expect(screen.getAllByText("Data Engineering").length).toBeGreaterThan(0);

    const cardOf = (title: string) =>
      [...document.querySelectorAll(".project-card")].find(
        (c) => c.querySelector("h3")?.textContent === title,
      )!;
    const rowOf = (el: Element): Element => {
      let cur: Element | null = el;
      while (cur && !cur.classList.contains("topic-row")) cur = cur.parentElement;
      return cur!;
    };
    // 07 must sit under Data Engineering, 06 under Optimization, 01+04 under their rows
    expect(rowOf(cardOf("Mobility")).querySelector("h2")!.textContent).toBe("Data Engineering");
    expect(rowOf(cardOf("Routing")).querySelector("h2")!.textContent).toBe("Optimization");
    expect(rowOf(cardOf("RAG Agent")).querySelector("h2")!.textContent).toBe("Agentic AI & LLM");
    expect(rowOf(cardOf("NLP Classification")).querySelector("h2")!.textContent).toBe(
      "Machine Learning",
    );
  });

  it("renders every row's cards inside a responsive 2-column project-grid", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(ALL_PROJECTS)));
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.querySelectorAll(".project-card")).toHaveLength(7));
    const grids = document.querySelectorAll(".topic-row .project-grid");
    expect(grids).toHaveLength(4); // one grid per non-empty row (Decision Science has no fixture project)
    grids.forEach((g) => expect(g.querySelectorAll(".project-card").length).toBeGreaterThan(0));
  });

  it("ships a 1-column grid on mobile and 2 columns from 720px up", () => {
    expect(stylesCss).toContain("@media (min-width: 720px)");
    expect(stylesCss).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(stylesCss).toContain("align-items: stretch;");
    // project cards top out at 2 columns; no 3-column project-grid rule remains
    const projectGridRules = [...stylesCss.matchAll(/\.project-grid\s*\{[^}]*\}/g)].map((m) => m[0]);
    expect(projectGridRules.join("\n")).not.toContain("repeat(3");
    expect(projectGridRules.join("\n")).toContain("grid-template-columns: 1fr;");
    // rows are full-width sections; cards never straddle them
    expect(stylesCss).toContain(".topic-row {");
  });

  it("renders a demos block above the topic rows with the live tape demo first", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(ALL_PROJECTS)));
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("Machine Learning")).toBeInTheDocument());
    expect(screen.getByText("Demos — interactive experiments")).toBeInTheDocument();
    expect(screen.getByText("play with the live systems behind the experiments")).toBeInTheDocument();
    const demos = document.querySelector(".demos")!;
    expect(demos).not.toBeNull();
    const demoCards = demos.querySelectorAll(".demo-card");
    expect(demoCards).toHaveLength(4);
    expect(demoCards[0].textContent).toContain("btc orderflow lab");
    expect(demoCards[0].textContent).toContain("live");
    expect(demoCards[0].querySelector("a")!.getAttribute("href")).toBe(
      "/demos/tape-forecast/",
    );
    demoCards.forEach((c) => expect(c.textContent).toMatch(/live|coming soon/));
    expect(demos.textContent).toContain("RAG ask-a-question");
    expect(demos.textContent).toContain("churn threshold sandbox");
    expect(demos.textContent).toContain("uplift policy simulator");
    // demos block renders before the experiments block with the topic rows
    const demosSection = document.querySelector("section.demos")!;
    const experimentsBlock = document.querySelector(".experiments-block")!;
    expect(
      demosSection.compareDocumentPosition(experimentsBlock) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const firstRow = document.querySelector(".topic-row")!;
    expect(
      demosSection.compareDocumentPosition(firstRow) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // and the experiments block wraps all topic rows
    expect(experimentsBlock.querySelectorAll(".topic-row")).toHaveLength(4);
  });

  it("renders a what-it-achieves summary plus sub-topic, dataset, and status chips on each card", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(ALL_PROJECTS)));
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.querySelectorAll(".project-card .summary")).toHaveLength(7));
    const cardOf = (title: string) =>
      [...document.querySelectorAll(".project-card")].find(
        (c) => c.querySelector("h3")?.textContent === title,
      )!;
    const rag = cardOf("RAG Agent");
    expect(rag.querySelector(".summary")!.textContent).toContain("retrieval-augmented agent");
    // sub-topic chip, dataset tag, status chip
    expect(rag.textContent).toContain("Agentic AI & LLM");
    expect(rag.textContent).toContain("data: docs");
    expect(rag.querySelector(".chip-status")!.textContent).toBe("flagship");
    const mobility = cardOf("Mobility");
    expect(mobility.querySelector(".chip-status")!.textContent).toBe("flagship");
    expect(mobility.textContent).toContain("Data Engineering");
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

  it("renders a one-line impact statement on each card (wording from docs/projects/index.md)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(ALL_PROJECTS)));
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.querySelectorAll(".project-card .impact")).toHaveLength(7));
    // exact wording of the "Impact in one line" column for project 01
    expect(
      screen.getByText(
        "retrieval recall@5 0.83 vs 0.03 random; verify loop cuts unsupported claims 18→14",
      ),
    ).toBeInTheDocument();
    const cardOf = (title: string) =>
      [...document.querySelectorAll(".project-card")].find(
        (c) => c.querySelector("h3")?.textContent === title,
      )!;
    expect(cardOf("Routing").querySelector(".impact")?.textContent).toContain(
      "within 4.23% of best-known solutions",
    );
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
