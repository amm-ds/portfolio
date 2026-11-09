import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { FlowDiagram } from "../components/diagrams/FlowDiagram";
import { AGENT_LOOP_SPEC, DIAGRAM_SPECS, ROUTING_SPEC, getDiagramSpec } from "../diagrams";
import { diagramSpecErrors, type DiagramSpec } from "../diagrams/types";

describe("diagram spec registry and schema", () => {
  it.each(Object.values(DIAGRAM_SPECS))("validates $id", (spec) => {
    expect(diagramSpecErrors(spec)).toEqual([]);
    expect(getDiagramSpec(spec.id)).toBe(spec);
    expect(new Set(spec.nodes.map((node) => node.id)).size).toBe(spec.nodes.length);
    if (!spec.id.startsWith("auto-")) {
      for (const node of spec.nodes) expect(node.facts.length).toBeGreaterThan(0);
    }
  });

  it("rejects duplicate nodes and dangling edges", () => {
    const invalid: DiagramSpec = {
      ...ROUTING_SPEC,
      nodes: [...ROUTING_SPEC.nodes, ROUTING_SPEC.nodes[0]],
      edges: [...ROUTING_SPEC.edges, { id: "broken", source: "input", target: "missing", kind: "task" }],
    };
    expect(diagramSpecErrors(invalid)).toEqual(
      expect.arrayContaining(["duplicate node id: input", "dangling edge: broken"]),
    );
  });

  it("keeps the exact pilot tool names and evidence in the specs", () => {
    expect(AGENT_LOOP_SPEC.nodes.map((node) => node.label)).toEqual(
      expect.arrayContaining([
        "search_documents · Wikipedia",
        "search_handbook · handbook",
        "calculator · locked-down AST",
      ]),
    );
    expect(JSON.stringify(AGENT_LOOP_SPEC)).toContain("400 requests and 4,000,000 total tokens");
    expect(JSON.stringify(ROUTING_SPEC)).toContain("4,477.8 predictions/s");
    expect(JSON.stringify(ROUTING_SPEC)).toContain("110.7 predictions/s");
    expect(JSON.stringify(ROUTING_SPEC)).toContain("$0.0656 (~$0.07) per 1,000 items");
  });

  it("registers the app architecture specs with their committed evidence", () => {
    const agentChat = getDiagramSpec("app-agent-chat-architecture");
    const docIntel = getDiagramSpec("app-document-intelligence-architecture");
    expect(agentChat?.title).toContain("chat agent");
    expect(docIntel?.title).toContain("document intelligence");
    expect(JSON.stringify(agentChat)).toContain("108/108 grader assertions");
    expect(JSON.stringify(agentChat)).toContain("default 120 s");
    expect(JSON.stringify(docIntel)).toContain("evidence resolvability is 1.00");
    expect(JSON.stringify(docIntel)).toContain("entity F1 0.68");
  });

  it("identifies unknown ids without exposing registry properties", () => {
    expect(getDiagramSpec("not-registered")).toBeUndefined();
    expect(getDiagramSpec("__proto__")).toBeUndefined();
  });
});

describe("case-study diagram placement and orientation", () => {
  const projectsBySpec: Record<string, string> = {
    "01-rag-pipeline": "01-rag-agent",
    "02-m5-pipeline": "02-demand-forecasting",
    "03-detection-pipeline": "03-anomaly-detection",
    "04-routing": "04-nlp-classification",
    "05-churn-cycle": "05-ml-pipeline-churn",
    "06-solver-ladder": "06-routing-optimization",
    "07-mobility-pipeline": "07-open-data-mobility",
    "08-serving-benchmark": "08-inference-serving",
    "09-agent-loop": "09-agentic-workflows",
    "10-uplift-judging": "10-uplift-experimentation",
    "11-engine-benchmark": "11-data-engineering",
    "12-lifecycle-pipeline": "12-tabular-ml-lifecycle",
    "13-serving-pipeline": "13-model-serving",
  };

  it("places every React Flow architecture diagram in Background", () => {
    const failures: string[] = [];
    for (const [specId, project] of Object.entries(projectsBySpec)) {
      const story = readFileSync(path.resolve(process.cwd(), "../../projects", project, "story.yaml"), "utf8");
      const background = /^[ \t]*- id: background\n([\s\S]*?)(?=^[ \t]*- id: )/m.exec(story)?.[1] ?? "";
      if (!background.includes(`\`\`\`diagram ${specId}`)) failures.push(`${project}: ${specId}`);
    }
    expect(failures).toEqual([]);
  });
});

// --- Render smoke over every registered spec ---------------------------------
// jsdom has no layout, so v12 measurement is stubbed the same way the
// FlowDiagram interaction tests do it: stable node dimensions let dagre run
// the same post-measure layout path the browser uses.
class ResizeObserverMock {
  constructor(private callback: ResizeObserverCallback) {}
  observe(target: Element) {
    queueMicrotask(() => {
      const entry = { target, contentRect: target.getBoundingClientRect() } as ResizeObserverEntry;
      this.callback([entry], this as unknown as ResizeObserver);
    });
  }
  unobserve() {}
  disconnect() {}
}

class DOMMatrixReadOnlyMock {
  m22 = 1;
  constructor(transform = "") {
    const scale = /scale\(([\d.]+)\)/.exec(transform);
    if (scale) this.m22 = Number(scale[1]);
  }
}

beforeAll(() => {
  vi.stubGlobal("ResizeObserver", ResizeObserverMock);
  vi.stubGlobal("DOMMatrixReadOnly", DOMMatrixReadOnlyMock);
  Object.defineProperties(HTMLElement.prototype, {
    offsetWidth: { configurable: true, get: () => 196 },
    offsetHeight: { configurable: true, get: () => 82 },
    clientWidth: { configurable: true, get: () => 1000 },
    clientHeight: { configurable: true, get: () => 520 },
    getBoundingClientRect: {
      configurable: true,
      value: function (this: HTMLElement) {
        const isNode = this.classList.contains("react-flow__node");
        const width = isNode ? 196 : 1000;
        const height = isNode ? 82 : 520;
        return { x: 0, y: 0, top: 0, left: 0, right: width, bottom: height, width, height, toJSON: () => ({}) };
      },
    },
  });
  Object.defineProperty(SVGElement.prototype, "getBBox", {
    configurable: true,
    value: () => ({ x: 0, y: 0, width: 100, height: 14 }),
  });
});

afterAll(() => {
  vi.unstubAllGlobals();
});

afterEach(() => {
  cleanup();
});

describe("diagram spec render smoke", () => {
  it.each(Object.values(DIAGRAM_SPECS))("renders $id end to end", async (spec) => {
    render(createElement(FlowDiagram, { spec }));
    expect(await screen.findByText(spec.nodes[0].label)).toBeInTheDocument();
    await waitFor(() => expect(document.querySelector(".frame-skeleton")).toBeNull());
    expect(document.querySelectorAll(".react-flow__node")).toHaveLength(spec.nodes.length);
    expect(document.querySelectorAll(".react-flow__edge")).toHaveLength(spec.edges.length);
    cleanup();
  });
});

// --- Fact evidence: every new spec carries committed numbers ------------------
const SPEC_PROJECT = {
  "01-rag-pipeline": "01-rag-agent",
  "02-m5-pipeline": "02-demand-forecasting",
  "03-detection-pipeline": "03-anomaly-detection",
  "05-churn-cycle": "05-ml-pipeline-churn",
  "06-solver-ladder": "06-routing-optimization",
  "07-mobility-pipeline": "07-open-data-mobility",
  "08-serving-benchmark": "08-inference-serving",
  "10-uplift-judging": "10-uplift-experimentation",
  "11-engine-benchmark": "11-data-engineering",
  "12-lifecycle-pipeline": "12-tabular-ml-lifecycle",
  "13-serving-pipeline": "13-model-serving",
} as const;

/** Numbers printed in fact strings, with the decimals they were printed at so
 *  committed full-precision values can be matched at the printed precision. */
function factNumbers(spec: DiagramSpec): { value: number; decimals: number }[] {
  const out: { value: number; decimals: number }[] = [];
  for (const node of spec.nodes) {
    for (const fact of node.facts) {
      const text = fact.replace(/[−–]/g, "-");
      for (const match of text.matchAll(/-?\d[\d,]*(?:\.\d+)?(?:e[+-]?\d+)?/gi)) {
        const raw = match[0].replace(/,/g, "");
        const value = Number(raw);
        if (!Number.isFinite(value)) continue;
        const decimals = (raw.split(".")[1] ?? "").replace(/e.*$/i, "").length;
        out.push({ value, decimals });
      }
    }
  }
  return out;
}

function collectNumbers(data: unknown, out: number[] = []): number[] {
  if (typeof data === "number") out.push(data);
  else if (Array.isArray(data)) for (const item of data) collectNumbers(item, out);
  else if (data && typeof data === "object")
    for (const value of Object.values(data)) collectNumbers(value, out);
  return out;
}

const metricsCache = new Map<string, number[]>();

/** Numbers a spec's facts may cite: the project's committed metrics when the
 *  project git-tracks them, otherwise its committed README (11/12 keep
 *  metrics as DVC outs, absent from a fresh CI checkout — READMEs carry the
 *  same printed numbers). */
function metricsNumbers(project: string): number[] {
  let numbers = metricsCache.get(project);
  if (!numbers) {
    const base = path.resolve(process.cwd(), "../../projects", project);
    const metricsFile = path.join(base, "reports", "metrics.json");
    if (existsSync(metricsFile)) {
      // Python-written metrics may carry NaN/Infinity tokens (invalid strict
      // JSON); they carry no fact-checkable numbers, so neutralize them.
      const raw = readFileSync(metricsFile, "utf8").replace(/\bNaN\b/g, "null").replace(/\bInfinity\b/g, "null");
      numbers = collectNumbers(JSON.parse(raw));
    } else {
      numbers = collectNumbersFromText(readFileSync(path.join(base, "README.md"), "utf8"));
    }
    metricsCache.set(project, numbers);
  }
  return numbers;
}

/** Every numeric token in prose, for matching printed facts against
 *  committed README text (thousands separators stripped). */
function collectNumbersFromText(text: string): number[] {
  const out: number[] = [];
  for (const match of text.matchAll(/-?\d[\d,]*(?:\.\d+)?/g)) {
    const value = Number(match[0].replace(/,/g, ""));
    if (Number.isFinite(value)) out.push(value);
  }
  return out;
}

function matchesPrintedPrecision(metric: number, value: number, decimals: number): boolean {
  if (decimals === 0) return Math.abs(metric - value) <= 0.501;
  return Math.abs(metric - value) <= 1.5 * 10 ** -decimals * Math.max(1, Math.abs(value));
}

describe("diagram spec facts trace to committed evidence", () => {
  for (const spec of Object.values(DIAGRAM_SPECS)) {
    const project = SPEC_PROJECT[spec.id as keyof typeof SPEC_PROJECT];
    if (!project) continue; // pilot specs carry their own evidence test above
    it(`${spec.id} has at least one fact with a digit`, () => {
      const nodesWithDigits = spec.nodes.filter((node) => node.facts.some((fact) => /\d/.test(fact)));
      expect(nodesWithDigits.length).toBeGreaterThan(0);
    });
    it(`${spec.id} prints a number committed in the project's metrics or README`, () => {
      const facts = factNumbers(spec);
      expect(facts.length).toBeGreaterThan(0);
      const metrics = metricsNumbers(project);
      expect(
        facts.some(({ value, decimals }) => metrics.some((metric) => matchesPrintedPrecision(metric, value, decimals))),
      ).toBe(true);
    });
  }
});
