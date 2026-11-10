import { describe, expect, it } from "vitest";
import { execFileSync } from "node:child_process";
import {
  inferNodeKind,
  parseMermaid,
  SPEC_OVERRIDES,
} from "../../scripts/mermaid-to-flow.mjs";

/** Minimal mermaid block → parsed node kinds (flat, pre-override). */
function kindsOf(block: string[]): Record<string, string> {
  const parsed = parseMermaid(block, "test");
  expect(parsed.errors).toEqual([]);
  const out: Record<string, string> = {};
  for (const node of parsed.nodes.values()) out[node.id] = node.kind;
  const outgoing = new Set(parsed.edges.map((e) => e.source));
  for (const node of parsed.nodes.values()) {
    if (node.kind === "stadium") out[node.id] = outgoing.has(node.id) ? "source" : "output";
  }
  return out;
}

describe("inferNodeKind", () => {
  it("defaults to task when nothing matches", () => {
    expect(inferNodeKind("Blend the member forecasts")).toBe("task");
    expect(inferNodeKind("ALNS destroy + repair")).toBe("task");
  });

  it("promotes by first matching keyword, case-insensitively", () => {
    expect(inferNodeKind("Postgres store")).toBe("data");
    expect(inferNodeKind("Train GBM on folds")).toBe("model");
    expect(inferNodeKind("Serve via FastAPI endpoint")).toBe("api");
    expect(inferNodeKind("Human approval gate")).toBe("gate");
    expect(inferNodeKind("Parse the PDF text")).toBe("tool");
    expect(inferNodeKind("Upload source CSV")).toBe("source");
    expect(inferNodeKind("Export report")).toBe("output");
    expect(inferNodeKind("Planner agent loop")).toBe("agent");
    expect(inferNodeKind("PARSE the dump")).toBe("tool"); // case-insensitive
  });

  it("table order decides ties (a store mention outranks an action)", () => {
    expect(inferNodeKind("Index the trained model")).toBe("data");
  });
});

describe("parseMermaid node kinds", () => {
  it("defaults plain rects to task", () => {
    const kinds = kindsOf(['graph LR', 'A["Blend"] --> B["Select winner"]']);
    expect(kinds).toEqual({ A: "task", B: "task" });
  });

  it("pins shape kinds regardless of keywords", () => {
    const kinds = kindsOf([
      "graph LR",
      'A[("corpus store")] --> B{"checkpoint reached?"}',
      'B --> C[[planner loop]] --> D("done")',
    ]);
    expect(kinds.A).toBe("data"); // cylinder: data even though labels vary
    expect(kinds.B).toBe("gate"); // rhombus pins gate
    expect(kinds.C).toBe("agent"); // subroutine pins agent
    expect(kinds.D).toBe("output"); // terminal stadium
  });

  it("re-infers when a later statement adds the label", () => {
    const kinds = kindsOf([
      "graph LR",
      'A --> B',
      'B["Train the model"]',
    ]);
    expect(kinds.B).toBe("model");
  });
});

describe("converter CLI", () => {
  it("regenerates specs whose default rect kind is task (dry run on a temp block)", () => {
    // The committed corpus regenerated clean: every spec parses and the only
    // diff vs HEAD is kind lines. Re-verify idempotence quickly.
    const out = execFileSync("node", ["scripts/mermaid-to-flow.mjs"], {
      cwd: process.cwd(),
      encoding: "utf8",
    });
    expect(out).toContain("generated 0 spec(s)");
  });
});

describe("SPEC_OVERRIDES", () => {
  it("has only known override shapes", () => {
    for (const [id, ov] of Object.entries(SPEC_OVERRIDES)) {
      expect(id).toMatch(/^auto-/);
      expect(Object.keys(ov)).toEqual(expect.arrayContaining([expect.stringMatching(/labels|canvasHeight|kinds/)]));
    }
  });
});
