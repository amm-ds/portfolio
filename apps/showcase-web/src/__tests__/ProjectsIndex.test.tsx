import { readFileSync } from "node:fs";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Project } from "../api";
import {
  ProjectsIndex,
  groupByTopic,
  groupByRow,
  rowAnchor,
  TOPIC_ROWS,
} from "../pages/ProjectsIndex";

const stylesCss = readFileSync("src/styles.css", "utf8");

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Fetch stub that answers /projects and 404s everything else (e.g. /demos → static fallback). */
function projectsOnlyFetch(): ReturnType<typeof vi.fn> {
  return vi.fn((input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.endsWith("/projects")) return Promise.resolve(jsonResponse(ALL_PROJECTS));
    return Promise.resolve(jsonResponse({ detail: "no" }, 404));
  });
}

/** One registry entry, shaped per the fixed /demos contract. */
const CHURN_DEMO_ENTRY = {
  id: "churn-sandbox",
  title: "churn threshold sandbox",
  hook: "Move the alarm threshold and the missed-churner cost — watch the saved budget change.",
  group: "retain customers",
  href: "/demos/churn-sandbox",
  project: "05-ml-pipeline-churn",
  status: "live",
  hero: { label: "decision cost per 1,400 customers", value: "$601 vs $1,035 naive" },
};

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
  it("nests topics under offering-named rows (Agentic AI & LLM systems … Data engineering)", () => {
    const rows = groupByRow(ALL_PROJECTS);
    expect(rows.map((r) => r.name)).toEqual([
      "Agentic AI & LLM systems",
      "Machine learning",
      "Optimization",
      "Data engineering",
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

  it("places 07 under the Data engineering row and 08's topic under APIs & model serving", () => {
    const rows = groupByRow(ALL_PROJECTS);
    const de = rows.find((r) => r.name === "Data engineering")!;
    expect(de.topics.flatMap((t) => t.projects).map((p) => p.id)).toEqual([
      "07-open-data-mobility",
    ]);
    // Inference & Serving maps to the APIs & model serving row
    const serving = project({ id: "08-inference-serving", topic: "Inference & Serving", order: 8 });
    const rows2 = groupByRow([...ALL_PROJECTS, serving]);
    expect(rows2.find((r) => r.name === "APIs & model serving")!.topics.map((t) => t.topic)).toEqual([
      "Inference & Serving",
    ]);
  });

  it("drops empty rows and maps unmapped topics to their own trailing row", () => {
    const partial = ALL_PROJECTS.filter((p) =>
      ["06-routing-optimization", "01-rag-agent"].includes(p.id),
    );
    const rows = groupByRow(partial);
    expect(rows.map((r) => r.name)).toEqual(["Agentic AI & LLM systems", "Optimization"]);

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
      "Inference & Serving",
      "Decision Science",
      "Data Engineering",
    ]) {
      expect(mapped.has(topic)).toBe(true);
    }
  });

  it("rowAnchor slugifies row names for the on-page index", () => {
    expect(rowAnchor("Agentic AI & LLM systems")).toBe("agentic-ai-llm-systems");
    expect(rowAnchor("APIs & model serving")).toBe("apis-model-serving");
    expect(rowAnchor("Machine learning")).toBe("machine-learning");
  });
});

describe("ProjectsIndex", () => {
  it("opens with a title paragraph and a small index of anchors", async () => {
    vi.stubGlobal("fetch", projectsOnlyFetch());
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("projects"),
    );
    expect(
      screen.getByText(/Ten public experiments with live demos — real datasets/i),
    ).toBeInTheDocument();
    // every anchor target exists once rows render
    await waitFor(() => expect(document.getElementById("machine-learning")).not.toBeNull());
    expect(document.getElementById("demos")).not.toBeNull();
    expect(document.getElementById("agentic-ai-llm-systems")).not.toBeNull();
    expect(document.getElementById("optimization")).not.toBeNull();
    expect(document.getElementById("data-engineering")).not.toBeNull();
    const index = screen.getByRole("navigation", { name: "On this page" });
    const anchors = [...index.querySelectorAll("a")].map((a) => [
      a.textContent,
      a.getAttribute("href"),
    ]);
    expect(anchors).toEqual([
      ["live demos", "#demos"],
      ["Agentic AI & LLM systems", "#agentic-ai-llm-systems"],
      ["Machine learning", "#machine-learning"],
      ["Optimization", "#optimization"],
      ["Data engineering", "#data-engineering"],
    ]);
  });

  it("renders the projects heading and places cards under the right topic rows", async () => {
    vi.stubGlobal("fetch", projectsOnlyFetch());
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
    // row heading plus the on-page index anchor both carry the names
    expect(screen.getAllByText("Machine learning").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Data engineering").length).toBeGreaterThanOrEqual(2);

    const cardOf = (title: string) =>
      [...document.querySelectorAll(".project-card")].find(
        (c) => c.querySelector("h3")?.textContent === title,
      )!;
    const rowOf = (el: Element): Element => {
      let cur: Element | null = el;
      while (cur && !cur.classList.contains("topic-row")) cur = cur.parentElement;
      return cur!;
    };
    // 07 must sit under Data engineering, 06 under Optimization, 01+04 under their rows
    expect(rowOf(cardOf("Mobility")).querySelector("h3")!.textContent).toBe("Data engineering");
    expect(rowOf(cardOf("Routing")).querySelector("h3")!.textContent).toBe("Optimization");
    expect(rowOf(cardOf("RAG Agent")).querySelector("h3")!.textContent).toBe(
      "Agentic AI & LLM systems",
    );
    expect(rowOf(cardOf("NLP Classification")).querySelector("h3")!.textContent).toBe(
      "Machine learning",
    );
  });

  it("renders every row's cards inside a responsive 2-column project-grid", async () => {
    vi.stubGlobal("fetch", projectsOnlyFetch());
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.querySelectorAll(".project-card")).toHaveLength(7));
    const grids = document.querySelectorAll(".topic-row .project-grid");
    expect(grids).toHaveLength(4); // one grid per non-empty row (APIs & model serving has no fixture project)
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

  it("renders the live-demos section from the registry as a single row with hero line and href", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith("/demos")) return Promise.resolve(jsonResponse([CHURN_DEMO_ENTRY]));
      if (url.endsWith("/projects")) return Promise.resolve(jsonResponse(ALL_PROJECTS));
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getAllByText("Machine learning").length).toBeGreaterThanOrEqual(2),
    );
    // prominent section with title + subtitle
    expect(
      screen.getByRole("heading", { level: 2, name: "live demos" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/play with the live systems behind the experiments/i)).toBeInTheDocument();
    const demos = document.querySelector(".demos")!;
    expect(demos).not.toBeNull();
    // all demo cards in ONE row container — no per-group sub-headings
    const demoCards = demos.querySelectorAll(".demo-card");
    expect(demoCards).toHaveLength(1);
    expect(demos.querySelector(".demo-group")).toBeNull();
    expect(demos.querySelectorAll(".demo-grid")).toHaveLength(1);
    expect(demoCards[0].textContent).toContain("churn threshold sandbox");
    expect(demoCards[0].querySelector(".demo-status")).toBeNull();
    expect(demoCards[0].getAttribute("aria-label")).toBe("churn threshold sandbox");
    // hero line rendered from the registry entry (currency values untouched)
    expect(demoCards[0].textContent).toContain("decision cost per 1,400 customers");
    expect(demoCards[0].textContent).toContain("$601 vs $1,035 naive");
    expect(demoCards[0].querySelector("a")!.getAttribute("href")).toBe("/demos/churn-sandbox");
    // demos block renders before the experiments block with the topic rows
    const experimentsBlock = document.querySelector(".experiments-block")!;
    expect(
      demos.compareDocumentPosition(experimentsBlock) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const firstRow = document.querySelector(".topic-row")!;
    expect(
      demos.compareDocumentPosition(firstRow) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(experimentsBlock.querySelectorAll(".topic-row")).toHaveLength(4);
  });

  it("keeps the demos in a single horizontally-scrolling row on desktop", () => {
    const gridRule = stylesCss.match(/\.demo-grid \{[\s\S]*?\n\}/)![0];
    expect(gridRule).toContain("display: flex;");
    expect(gridRule).toContain("overflow-x: auto;");
    // no multi-column demo grid remains
    expect(stylesCss).not.toContain(".demo-grid {\n  display: grid;");
  });

  it("falls back to the static demo cards when the registry fetch fails", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith("/projects")) return Promise.resolve(jsonResponse(ALL_PROJECTS));
      return Promise.resolve(jsonResponse({ detail: "registry down" }, 503));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getAllByText("Machine learning").length).toBeGreaterThanOrEqual(2),
    );
    const demos = document.querySelector(".demos")!;
    const demoCards = demos.querySelectorAll(".demo-card");
    expect(demoCards).toHaveLength(2);
    expect(demos.querySelectorAll(".demo-grid")).toHaveLength(1);
    expect(demoCards[0].textContent).toContain("churn threshold sandbox");
    expect(demoCards[0].querySelector(".demo-status")).toBeNull();
    expect(demoCards[0].querySelector("a")!.getAttribute("href")).toBe("/demos/churn-sandbox");
    expect(demoCards[1].textContent).toContain("demand forecast workbench");
    expect(demoCards[1].querySelector("a")!.getAttribute("href")).toBe("/demos/forecast-workbench");
  });

  it("renders a rewritten objective/data/result summary and exactly 4 technique tags per card", async () => {
    vi.stubGlobal("fetch", projectsOnlyFetch());
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
    expect(rag.querySelector(".summary")!.textContent).toContain(
      "Built a question-answering agent",
    );
    // exactly four short technique tags (labels), no status or dataset chips
    const chips = [...rag.querySelectorAll(".chip")].map((el) => el.textContent);
    expect(chips).toHaveLength(4);
    expect(chips).toContain("RAG");
    expect(chips).toContain("FAISS");
    expect(rag.textContent).not.toContain("data: docs");
    expect(rag.querySelector(".chip-status")).toBeNull();
    expect(rag.textContent).not.toContain("flagship");
    const mobility = cardOf("Mobility");
    expect(mobility.querySelector(".chip-status")).toBeNull();
    expect([...mobility.querySelectorAll(".chip")].map((el) => el.textContent)).toHaveLength(4);
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

  it("keeps the rewritten card copy on every card and no hand-maintained impact line", async () => {
    vi.stubGlobal("fetch", projectsOnlyFetch());
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.querySelectorAll(".project-card .summary")).toHaveLength(7));
    // exact rewritten description for project 01 (objective + data + result)
    expect(
      screen.getByText(/Built a question-answering agent that answers only from a pinned 593-article/),
    ).toBeInTheDocument();
    const cardOf = (title: string) =>
      [...document.querySelectorAll(".project-card")].find(
        (c) => c.querySelector("h3")?.textContent === title,
      )!;
    expect(cardOf("Routing").querySelector(".summary")?.textContent).toContain(
      "within 4.2% of best-known",
    );
    expect(cardOf("Churn").querySelector(".summary")?.textContent).toContain(
      "cutting decision cost 42%",
    );
    // single-source copy: no separate impact line remains on cards
    expect(document.querySelectorAll(".project-card .impact")).toHaveLength(0);
  });

  it("shows an empty state when /projects returns []", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        if (url.endsWith("/projects")) return Promise.resolve(jsonResponse([]));
        return Promise.resolve(jsonResponse({ detail: "no" }, 404));
      }),
    );
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/no projects published yet/i)).toBeInTheDocument());
  });

  it("renders the experiment cards from the static snapshot when the registry is unreachable", async () => {
    // fetch rejects for every endpoint (projects, demos, per-card metrics…)
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(
        screen.getByText(/the live registry is unreachable — showing the last published snapshot/i),
      ).toBeInTheDocument(),
    );
    // heading outline: one h2 "live demos" + one h2 "experiments"; topic rows are h3
    expect(
      screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent),
    ).toEqual(["live demos", "experiments"]);
    expect(screen.getByRole("heading", { level: 3, name: "Machine learning" })).toBeInTheDocument();
    // all ten snapshot projects render as cards
    await waitFor(() => expect(document.querySelectorAll(".project-card")).toHaveLength(10));
    // Retry re-fetches (the failing mock is called again)
    const callsBefore = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.length;
    screen.getByRole("button", { name: "Retry" }).click();
    await waitFor(() =>
      expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBeGreaterThan(
        callsBefore,
      ),
    );
  });

  it("keeps the plain error state when only /projects fails", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith("/projects")) return Promise.reject(new Error("down"));
      if (url.endsWith("/demos")) return Promise.resolve(jsonResponse([]));
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/could not load/i)).toBeInTheDocument());
    expect(document.querySelector(".experiments-block")).toBeNull();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });
});
