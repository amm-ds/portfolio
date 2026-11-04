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

  it("TOPIC_ROWS lists every topic used by the portfolio.yaml manifests", () => {
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
      screen.getByText(/A growing set of public, reproducible case studies with live demos/i),
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

  it("opens with the kicker-format page title and a descriptive subtitle line", async () => {
    const css = readFileSync("src/styles.css", "utf8");
    // the page title renders like the /services and /about kickers: small
    // green mono "> " prompt (marker via ::before), no glow
    const titleRule = css.match(/\.page-title \{[\s\S]*?\n\}/)![0];
    expect(titleRule).toContain("font-family: var(--mono);");
    expect(titleRule).toContain("font-size: 0.85rem;");
    expect(titleRule).toContain("color: var(--accent);");
    expect(titleRule).not.toContain("accent-glow");
    const subRule = css.match(/\.page-subtitle \{[\s\S]*?\n\}/)![0];
    expect(subRule).toContain("font-family: var(--mono);");
    expect(subRule).toContain("color: var(--text);");
    vi.stubGlobal("fetch", projectsOnlyFetch());
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("projects"),
    );
    // subtitle sits between the title and the intro paragraph
    const h1 = screen.getByRole("heading", { level: 1 });
    const subtitle = h1.nextElementSibling!;
    expect(subtitle.classList.contains("page-subtitle")).toBe(true);
    expect(subtitle.textContent).toBe("projects and demos repository");
    expect(subtitle.nextElementSibling!.classList.contains("section-intro")).toBe(true);
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
    ).toBe("02 experiments");
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
    expect(rowOf(cardOf("Mobility")).querySelector("h3")!.textContent).toBe(
      "04 Data engineering",
    );
    expect(rowOf(cardOf("Routing")).querySelector("h3")!.textContent).toBe("03 Optimization");
    expect(rowOf(cardOf("RAG Agent")).querySelector("h3")!.textContent).toBe(
      "01 Agentic AI & LLM systems",
    );
    expect(rowOf(cardOf("NLP Classification")).querySelector("h3")!.textContent).toBe(
      "02 Machine learning",
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

  it("renders the live-demos section from the registry with a labeled description block, a results chip and href", async () => {
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
    // prominent section with numbered title + subtitle
    expect(
      screen.getByRole("heading", { level: 2, name: "01 live demos" }),
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
    // the card link's accessible name is its visible text (no aria-label
    // override — axe label-content-name-mismatch)
    expect(demoCards[0].getAttribute("aria-label")).toBeNull();
    // demos keep only the labeled "description" block — no "results" text block
    const labels = [...demoCards[0].querySelectorAll(".study-block-label")].map(
      (el) => el.textContent,
    );
    expect(labels).toEqual(["description"]);
    expect(demoCards[0].querySelector(".study-does")!.textContent).toContain(
      "Move the alarm threshold",
    );
    expect(demoCards[0].querySelector(".study-achieves")).toBeNull();
    // the measured result renders as a tag/chip — label plus accent metric value
    const chip = demoCards[0].querySelector(".study-result-chip")!;
    expect(chip).not.toBeNull();
    expect(chip.classList.contains("chip")).toBe(true);
    expect(chip.textContent).toContain("decision cost per 1,400 customers");
    expect(chip.querySelector(".study-metric")!.textContent).toBe("$601 vs $1,035 naive");
    // chip result: the numbers live only inside the results chip — nothing
    // else on a demo card carries a digit
    const clone = demoCards[0].cloneNode(true) as Element;
    clone.querySelectorAll(".study-result-chip").forEach((c) => c.remove());
    expect(clone.textContent).not.toMatch(/[0-9]/);
    // the whole card is the link to the demo route
    expect(demoCards[0].getAttribute("href")).toBe("/demos/churn-sandbox");
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

  it("lays the demos out full width: one shared row on desktop, stacked on mobile", () => {
    const gridRule = stylesCss.match(/\.demo-grid \{[\s\S]*?\n\}/)![0];
    expect(gridRule).toContain("display: grid;");
    expect(gridRule).toContain("grid-template-columns: 1fr;");
    expect(gridRule).toContain("align-items: stretch;");
    // the two cards share the row edge-to-edge from 720px up…
    expect(stylesCss).toContain("@media (min-width: 720px)");
    const twoCol = stylesCss.match(
      /@media \(min-width: 720px\) \{\s*\.demo-grid \{[\s\S]*?\n  \}/,
    )![0];
    expect(twoCol).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    // …and the horizontally-scrolling flex row is gone
    expect(gridRule).not.toContain("overflow-x: auto;");
    expect(gridRule).not.toContain("display: flex;");
  });

  it("falls back to the static demo cards when the registry fetch fails — same description block and results chip", async () => {
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
    expect(demoCards[0].getAttribute("href")).toBe("/demos/churn-sandbox");
    expect(demoCards[1].textContent).toContain("demand forecast workbench");
    expect(demoCards[1].getAttribute("href")).toBe("/demos/forecast-workbench");
    // both static fallback cards carry the same structure: the labeled
    // "description" block only, plus the results chip with the headline
    // metric (churn hero "$601 vs $1,035 naive", forecast hero
    // "0.6161 vs 0.8929")
    const metrics = ["$601 vs $1,035 naive", "0.6161 vs 0.8929"];
    demoCards.forEach((card, i) => {
      const blockLabels = [...card.querySelectorAll(".study-block-label")].map(
        (el) => el.textContent,
      );
      expect(blockLabels).toEqual(["description"]);
      expect(card.querySelector(".study-achieves")).toBeNull();
      expect(card.querySelector(".study-result-chip")!.textContent).toContain(metrics[i]);
      expect(card.querySelector(".study-metric")!.textContent).toBe(metrics[i]);
    });
    // the chip LABEL is short — the source registry label reads "official WRMSSE"
    // (the previous long sentence was shortened at the source; the metric value
    // stays intact)
    const forecastChip = demoCards[1].querySelector(".study-result-chip")!;
    const labelText = forecastChip.childNodes[0].textContent!.replace(/:\s*$/, "");
    expect(labelText.split(/\s+/).filter(Boolean).length).toBeLessThanOrEqual(6);
    expect(labelText).toBe("official WRMSSE");
    expect(forecastChip.textContent).toContain("0.6161 vs 0.8929");
  });

  it("renders two muted blocks per experiment card — what it does / what it achieves — and exactly 4 technique tags", async () => {
    vi.stubGlobal("fetch", projectsOnlyFetch());
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.querySelectorAll(".project-card .study-does")).toHaveLength(7));
    expect(document.querySelectorAll(".project-card .study-achieves")).toHaveLength(7);
    const cardOf = (title: string) =>
      [...document.querySelectorAll(".project-card")].find(
        (c) => c.querySelector("h3")?.textContent === title,
      )!;
    const rag = cardOf("RAG Agent");
    expect(rag.querySelector(".study-does")!.textContent).toContain(
      "Built a question-answering agent",
    );
    expect(rag.querySelector(".study-achieves")!.textContent).toContain(
      "right passage 83% of the time",
    );
    // two stacked metadata lines: topics/domain over data/source
    const metaItems = rag.querySelectorAll(".study-meta-item");
    expect(metaItems).toHaveLength(2);
    expect(metaItems[0].querySelector(".study-meta-label")!.textContent).toBe("topics");
    expect(metaItems[0].querySelector(".study-sub")!.textContent).toBe("NLP");
    expect(metaItems[1].querySelector(".study-meta-label")!.textContent).toBe("data");
    expect(metaItems[1].querySelector(".study-sub")!.textContent).toBe("docs");
    // exactly four short technique tags (labels), no status or dataset chips
    const chips = [...rag.querySelectorAll(".chip")].map((el) => el.textContent);
    expect(chips).toEqual(["RAG", "vector search", "reranking", "RAG evals"]);
    expect(rag.textContent).not.toContain("data: docs");
    expect(rag.querySelector(".chip-status")).toBeNull();
    expect(rag.textContent).not.toContain("flagship");
    // no card tag — experiment or demo — names a framework or library
    for (const chip of document.querySelectorAll(".project-card .chip, .demo-card .chip")) {
      expect(chip.textContent!).not.toMatch(
        /faiss|ragas|optuna|pytorch|polars|distilbert|scikit|sklearn|\bdvc\b|fastapi|ollama|\bmlx\b|pydantic|react|plotly|docker/i,
      );
    }
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

  it("renders no results chip when metrics are missing", async () => {
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
    // the slot stays empty (and hidden) until a live metric loads
    expect(document.querySelector(".project-card .study-result-chip")).toBeNull();
    expect(document.querySelector(".project-card .study-result:empty")).not.toBeNull();
  });

  it("keeps the does/achieves card copy on every card and no hand-maintained impact line", async () => {
    vi.stubGlobal("fetch", projectsOnlyFetch());
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.querySelectorAll(".project-card .study-does")).toHaveLength(7));
    // exact rewritten "what it does" for project 01 (objective + data); the
    // **bold** 593-article fact splits the paragraph into text + <strong>,
    // so match on the flattened textContent
    expect(
      [...document.querySelectorAll(".project-card .study-does")].some((el) =>
        el.textContent!.includes(
          "Built a question-answering agent that answers only from a pinned 593-article",
        ),
      ),
    ).toBe(true);
    const cardOf = (title: string) =>
      [...document.querySelectorAll(".project-card")].find(
        (c) => c.querySelector("h3")?.textContent === title,
      )!;
    expect(cardOf("Routing").querySelector(".study-achieves")?.textContent).toContain(
      "within 4.2% of best-known",
    );
    expect(cardOf("Churn").querySelector(".study-achieves")?.textContent).toContain(
      "Cutting decision cost 42%",
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
    // heading outline: one numbered h2 "01 live demos" + one "02 experiments"; topic rows are numbered h3s
    expect(
      screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent),
    ).toEqual(["01 live demos", "02 experiments"]);
    expect(
      screen.getByRole("heading", { level: 3, name: "02 Machine learning" }),
    ).toBeInTheDocument();
    // all eleven snapshot projects render as cards
    await waitFor(() => expect(document.querySelectorAll(".project-card")).toHaveLength(11));
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

  it("renders demo and experiment cards with the SAME shared study-card structure", async () => {
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
      expect(document.querySelectorAll(".project-card")).toHaveLength(7),
    );
    const structureOf = (card: Element) => ({
      shared: card.classList.contains("study-card"),
      title: card.querySelector("h3")?.textContent ?? null,
      meta: [...card.querySelectorAll(".study-meta-item")].map((m) => [
        m.querySelector(".study-meta-label")?.textContent,
        m.querySelector(".study-sub")?.textContent,
      ]),
      labels: [...card.querySelectorAll(".study-block-label")].map((el) => el.textContent),
      does: card.querySelector(".study-does")?.textContent ?? null,
      achieves: card.querySelector(".study-achieves")?.textContent ?? null,
      resultChip: card.querySelector(".study-result-chip")?.textContent ?? null,
      metric: card.querySelector(".study-metric")?.textContent ?? null,
      resultSlot: card.querySelector(".study-result"),
      chips: card.querySelectorAll(":scope > .chips .chip").length,
    });
    const demo = structureOf(document.querySelector(".demo-card")!);
    const experiment = structureOf(
      [...document.querySelectorAll(".project-card")].find(
        (c) => c.querySelector("h3")?.textContent === "Churn",
      )!,
    );
    // identical layout: shared class, title, stacked metadata, does block, four tags
    for (const s of [demo, experiment]) {
      expect(s.shared).toBe(true);
      expect(s.title).not.toBeNull();
      expect(s.meta.length).toBeGreaterThan(0);
      expect(s.does).not.toBeNull();
      expect(s.chips).toBe(4);
    }
    // demo copy comes from the registry: use case/domain metadata, the
    // labeled "description" block only, and the headline metric as the
    // results chip — the SAME chip slot the experiment's live key number
    // renders through
    expect(demo.meta).toEqual([
      ["use case", "retain customers"],
      ["domain", "NLP"],
    ]);
    expect(demo.labels).toEqual(["description"]);
    expect(demo.does).toContain("Move the alarm threshold");
    expect(demo.achieves).toBeNull();
    expect(demo.resultChip).toContain("decision cost per 1,400 customers");
    expect(demo.metric).toBe("$601 vs $1,035 naive");
    // experiment keeps the labeled "description" + "results" blocks, the
    // stacked topics/data metadata, the results-chip slot for the live key
    // number (this fixture serves no metrics, so the chip stays empty) and
    // no "results" text on demos
    expect(experiment.meta).toEqual([
      ["topics", "NLP"],
      ["data", "docs"],
    ]);
    expect(experiment.labels).toEqual(["description", "results"]);
    expect(experiment.does).toContain("Scores churn on IBM telco data");
    expect(experiment.achieves).toContain("Cutting decision cost 42%");
    expect(experiment.resultChip).toBeNull();
    expect(experiment.resultSlot).not.toBeNull();
  });

  it("links the glossary from the experiments section description", async () => {
    vi.stubGlobal("fetch", projectsOnlyFetch());
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 2, name: "02 experiments" }),
      ).toBeInTheDocument(),
    );
    const intro = document.querySelector(".experiments-block > .section-intro")!;
    expect(intro.textContent).toMatch(/grouped by discipline/i);
    expect(intro.textContent).toMatch(/terms are defined in the glossary/i);
    const glossary = intro.querySelector("a")!;
    expect(glossary.getAttribute("href")).toBe("/glossary");
  });

  it("makes demos and experiments the two big numbered sections and demotes topic rows to numbered group labels", async () => {
    const css = readFileSync("src/styles.css", "utf8");
    // registry unreachable → the static snapshot renders the rows
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    // big section titles with extra weight
    expect(css.match(/\.section-title--major \{[\s\S]*?\n\}/)![0]).toContain("font-size: 1.6rem;");
    // topic rows are stepped-up mono labels — bigger than the card metadata,
    // still below the 1.6rem section titles
    const labelRule = css.match(/\.row-label \{[\s\S]*?\n\}/)![0];
    expect(labelRule).toContain("font-family: var(--mono);");
    expect(labelRule).toContain("font-size: 1.05rem;");
    expect(labelRule).not.toContain("border-bottom");
    // the numbered prefix is blue and the title text green — the page-index
    // color family; the old "> " marker is gone from the group labels
    expect(css.match(/\.title-num \{[\s\S]*?\n\}/)![0]).toContain("color: var(--secondary);");
    expect(css.match(/\.row-label \{[\s\S]*?\n\}/)![0]).toContain("color: var(--accent);");
    expect(css).not.toContain(".row-label::before");
    // the two big section titles keep the "> " prompt marker (no `content:
    // none` suppression) and carry no glow — green title, blue number
    expect(css).not.toContain(".demos > .section-title::before");
    expect(css).not.toContain(".experiments-block > .section-title::before");
    const majorTitleRule = css.match(
      /\.demos > \.section-title,\n\.experiments-block > \.section-title \{[\s\S]*?\n\}/,
    )![0];
    expect(majorTitleRule).toContain("color: var(--accent);");
    expect(majorTitleRule).toContain("text-shadow: none;");
    expect(majorTitleRule).not.toContain("accent-glow");
    // no fixed experiment count anywhere in the page copy
    const { container } = render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(document.querySelectorAll(".row-label .title-num")).toHaveLength(5),
    );
    expect(container.textContent).not.toMatch(/\bten\b (public )?(reproducible )?(experiments|case studies)/i);
    expect(container.textContent).not.toMatch(/\b10 reproducible experiments\b/);
    // live demos and experiments both carry the major-title modifier with a
    // numbered prefix, and every group label is numbered in the same family
    expect(document.querySelector(".demos > .section-title--major")!.textContent).toBe(
      "01 live demos",
    );
    expect(
      document.querySelector(".experiments-block > .section-title--major")!.textContent,
    ).toBe("02 experiments");
    const rowNums = [...document.querySelectorAll(".row-label .title-num")].map(
      (el) => el.textContent,
    );
    expect(rowNums).toEqual(["01", "02", "03", "04", "05"]);
  });

  it("restyles the page index to terminal labels: mono, accent label, muted items behind green >-markers", () => {
    const css = readFileSync("src/styles.css", "utf8");
    const linkRule = css.match(/\.page-index a \{[\s\S]*?\n\}/)![0];
    expect(linkRule).toContain("color: var(--muted);");
    const beforeRule = css.match(/\.page-index a::before \{[\s\S]*?\n\}/)![0];
    expect(beforeRule).toContain('content: "> ";');
    // only the ">" marker is green; the item text stays muted
    expect(beforeRule).toContain("color: var(--accent);");
    const hoverRule = css.match(/\.page-index a:hover \{[\s\S]*?\n\}/)![0];
    expect(hoverRule).toContain("color: var(--accent);");
    // the "index" label keeps the accent
    expect(css.match(/\.page-index \.page-index-label \{[\s\S]*?\n\}/)![0]).toContain(
      "color: var(--accent);",
    );
    expect(css.match(/\.page-index \{[\s\S]*?\n\}/)![0]).toContain("font-family: var(--mono);");
  });

  it("splits the card body into two equal white text columns under one uniform small-label style", () => {
    const css = readFileSync("src/styles.css", "utf8");
    const colsRule = css.match(/\.study-cols \{[\s\S]*?\n\}/)![0];
    expect(colsRule).toContain("display: grid;");
    expect(colsRule).toContain("repeat(auto-fit, minmax(0, 1fr));");
    expect(colsRule).toContain("gap: 0.9rem;");
    // both blocks render in the default text color (--text); the small
    // section labels above them stay muted
    const doesRule = css.match(/\.study-does,\n\.study-achieves \{[\s\S]*?\n\}/)![0];
    expect(doesRule).toContain("color: var(--text);");
    expect(doesRule).not.toContain("text-transform");
    // all four card labels (topics / data / description / results) share ONE
    // uniform small-label rule — mono, uppercase, muted
    const labelRule = css.match(/\.study-meta-label,\n\.study-block-label \{[\s\S]*?\n\}/)![0];
    expect(labelRule).toContain("font-family: var(--mono);");
    expect(labelRule).toContain("font-size: 0.72rem;");
    expect(labelRule).toContain("text-transform: uppercase;");
    expect(labelRule).toContain("letter-spacing: 0.08em;");
    expect(labelRule).toContain("color: var(--muted);");
    // the metadata label has no standalone rule anymore; the block-label rule
    // only adds block spacing on top of the shared label style
    expect(css).not.toMatch(/\.study-meta-label \{[^,]*\}/);
    // the standalone block-label rule only adds block spacing on top of the
    // shared label style (the combined selector above ends with a comma)
    const blockLabelRule = css.match(/\.study-block-label \{\n  display: block;[\s\S]*?\n\}/)![0];
    expect(blockLabelRule).toContain("margin: 0 0 0.3rem;");
    expect(blockLabelRule).not.toContain("font-family");
    // the old single description line is gone
    expect(css).not.toContain(".study-built");
    // and the labels are all present in the DOM: topics/data on the metadata
    // lines, description/results on the experiment-card blocks
    vi.stubGlobal("fetch", projectsOnlyFetch());
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    return waitFor(() =>
      expect(document.querySelectorAll(".project-card")).toHaveLength(7),
    ).then(() => {
      const rag = [...document.querySelectorAll(".project-card")].find(
        (c) => c.querySelector("h3")?.textContent === "RAG Agent",
      )!;
      const metaLabels = [...rag.querySelectorAll(".study-meta-label")].map(
        (el) => el.textContent,
      );
      expect(metaLabels).toEqual(["topics", "data"]);
      const blockLabels = [...rag.querySelectorAll(".study-block-label")].map(
        (el) => el.textContent,
      );
      expect(blockLabels).toEqual(["description", "results"]);
    });
  });

  it("renders the results as one shared GREEN chip design on demo and experiment cards", async () => {
    const css = readFileSync("src/styles.css", "utf8");
    // ONE rule paints the results chip green on both card kinds — with enough
    // specificity to beat the blue tag treatment below it
    const chipRule = css.match(/\.study-card \.chip\.study-result-chip \{[\s\S]*?\n\}/)![0];
    expect(chipRule).toContain("color: var(--accent);");
    expect(chipRule).toContain("background: rgba(45, 212, 191, 0.08);");
    expect(chipRule).toContain("border-color: rgba(45, 212, 191, 0.35);");
    expect(chipRule).toContain("font-family: var(--mono);");
    // the slot hides entirely while a live metric has not loaded
    expect(css.match(/\.study-result:empty \{[\s\S]*?\n\}/)![0]).toContain("display: none;");
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith("/demos")) return Promise.resolve(jsonResponse([CHURN_DEMO_ENTRY]));
      if (url.endsWith("/projects")) return Promise.resolve(jsonResponse([ALL_PROJECTS[4]]));
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
    // both card kinds render their result through the same chip class…
    await waitFor(() =>
      expect(document.querySelector(".project-card .study-result-chip")!.textContent).toBe(
        "mae: 72.3457",
      ),
    );
    const demoChip = document.querySelector(".demo-card .study-result-chip")!;
    expect(demoChip.textContent).toContain("decision cost per 1,400 customers");
    // …and the chip is the ONLY numbered element on a demo card
    for (const card of document.querySelectorAll(".demo-card")) {
      const clone = card.cloneNode(true) as Element;
      clone.querySelectorAll(".study-result-chip").forEach((c) => c.remove());
      expect(clone.textContent).not.toMatch(/[0-9]/);
    }
  });

  it("paints card subtitles blue, stacked and one step below the old 1rem scale", async () => {
    const css = readFileSync("src/styles.css", "utf8");
    const subRule = css.match(/\.study-sub \{[\s\S]*?\n\}/)![0];
    expect(subRule).toContain("color: var(--secondary);");
    // below the old 1rem subtitle scale, clearly smaller than the 1.6rem
    // section titles
    expect(subRule).toContain("font-size: 0.85rem;");
    expect(css.match(/\.section-title--major \{[\s\S]*?\n\}/)![0]).toContain("font-size: 1.6rem;");
    // the inline "·"-separated subtitle is gone — two stacked label-over-value
    // lines carry topics/data instead
    expect(css).not.toContain(".study-sep");
    vi.stubGlobal("fetch", projectsOnlyFetch());
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.querySelectorAll(".project-card")).toHaveLength(7));
    const metaItems = document.querySelectorAll(".project-card .study-meta-item");
    expect(metaItems.length).toBeGreaterThan(0);
    for (const item of metaItems) {
      expect(item.querySelector(".study-meta-label")).not.toBeNull();
      expect(item.querySelector(".study-sub")).not.toBeNull();
    }
  });

  it("paints all card tags blue — no per-tag hue rotation remains", () => {
    const css = readFileSync("src/styles.css", "utf8");
    const chipRule = css.match(/\.study-card \.chip,\n\.offering-card \.chip \{[\s\S]*?\n\}/)![0];
    expect(chipRule).toContain("color: #7dd3fc;");
    expect(chipRule).toContain("background: rgba(56, 189, 248, 0.08);");
    for (const hue of ["teal", "sky", "violet", "amber"]) {
      expect(css).not.toContain(`.chip--${hue}`);
    }
    // …while the results chip keeps its own green rule, positioned so its
    // specificity (0,3,0) beats the blue tag rule (0,2,0)
    const greenIdx = css.indexOf(".study-card .chip.study-result-chip {");
    const blueIdx = css.indexOf(".study-card .chip,\n.offering-card .chip {");
    expect(greenIdx).toBeGreaterThan(-1);
    expect(blueIdx).toBeGreaterThan(-1);
  });

  it("renders **bold** inline markdown in the card description and results copy", async () => {
    vi.stubGlobal("fetch", projectsOnlyFetch());
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.querySelectorAll(".project-card")).toHaveLength(7));
    const cardOf = (title: string) =>
      [...document.querySelectorAll(".project-card")].find(
        (c) => c.querySelector("h3")?.textContent === title,
      )!;
    const rag = cardOf("RAG Agent");
    // the authored **bold** key facts render as <strong> inside the muted
    // paragraphs, and the flattened text keeps the plain copy intact
    const doesStrong = rag.querySelector(".study-does strong")!;
    expect(doesStrong.textContent).toBe("593-article");
    const achievesStrong = rag.querySelector(".study-achieves strong")!;
    expect(achievesStrong.textContent).toBe("83% of the time");
    expect(rag.querySelector(".study-does")!.textContent).toContain(
      "a pinned 593-article Wikipedia corpus",
    );
    expect(rag.querySelector(".study-achieves")!.textContent).toContain(
      "right passage 83% of the time",
    );
    // every card's copy renders — no raw ** markers leak into the DOM
    for (const el of document.querySelectorAll(".study-does, .study-achieves")) {
      expect(el.textContent).not.toContain("**");
    }
  });

  it("left-aligns the tags row exactly with the card's outer padding — no indent", () => {
    const css = readFileSync("src/styles.css", "utf8");
    const chipsRule = css.match(/\.study-card \.chips \{[\s\S]*?\n\}/)![0];
    expect(chipsRule).toContain("margin: 0.9rem 0 0;");
    expect(chipsRule).toContain("padding-left: 0;");
    expect(chipsRule).not.toContain("margin-left");
    // …and the chip grids share one card gap (the spacing scale token)
    expect(css).toContain("gap: var(--gap-card);");
    expect(css.match(/\.demo-grid \{[\s\S]*?\n\}/)![0]).toContain("gap: var(--gap-card);");
  });
});
