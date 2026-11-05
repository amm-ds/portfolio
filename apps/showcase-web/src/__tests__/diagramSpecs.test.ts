import { describe, expect, it } from "vitest";
import { AGENT_LOOP_SPEC, DIAGRAM_SPECS, ROUTING_SPEC, getDiagramSpec } from "../diagrams";
import { diagramSpecErrors, type DiagramSpec } from "../diagrams/types";

describe("diagram spec registry and schema", () => {
  it.each(Object.values(DIAGRAM_SPECS))("validates $id", (spec) => {
    expect(diagramSpecErrors(spec)).toEqual([]);
    expect(getDiagramSpec(spec.id)).toBe(spec);
    expect(new Set(spec.nodes.map((node) => node.id)).size).toBe(spec.nodes.length);
    for (const node of spec.nodes) expect(node.facts.length).toBeGreaterThan(0);
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

  it("identifies unknown ids without exposing registry properties", () => {
    expect(getDiagramSpec("not-registered")).toBeUndefined();
    expect(getDiagramSpec("__proto__")).toBeUndefined();
  });
});
