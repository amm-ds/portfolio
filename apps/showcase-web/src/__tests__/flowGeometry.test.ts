import { Position, type Edge, type Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";
import {
  getFlowBounds,
  layoutMeasuredNodes,
  parallelEdgeOffset,
} from "../components/diagrams/flowGeometry";
import type { DiagramSpec, DiagramSpecEdge } from "../diagrams/types";

const nodes: Node[] = [
  {
    id: "a",
    position: { x: 0, y: 100 },
    measured: { width: 196, height: 82 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {},
  },
  {
    id: "b",
    position: { x: 400, y: 100 },
    measured: { width: 196, height: 82 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {},
  },
];

function edge(specEdge: DiagramSpecEdge): Edge {
  return { ...specEdge, data: { offset: specEdge.offset ?? 0 } };
}

describe("flow geometry", () => {
  it("centers parallel routes without duplicate offsets and honors reviewed routes", () => {
    const base: DiagramSpecEdge = { id: "a-b", source: "a", target: "b", kind: "task" };
    expect([0, 1, 2, 3].map((index) => parallelEdgeOffset(base, index, 4))).toEqual([-51, -17, 17, 51]);
    expect(parallelEdgeOffset({ ...base, offset: -40 }, 0, 2)).toBe(-40);
  });

  it("lays out reciprocal named edges and reserves label dimensions", () => {
    const spec: DiagramSpec = {
      id: "feedback",
      title: "Feedback",
      direction: "LR",
      nodes: [
        { id: "a", label: "A", kind: "task", facts: [] },
        { id: "b", label: "B", kind: "task", facts: [] },
      ],
      edges: [
        { id: "a-b", source: "a", target: "b", kind: "task", label: "forward" },
        { id: "b-a", source: "b", target: "a", kind: "error", label: "feedback" },
      ],
    };
    const initial: Node[] = [
      { id: "a", position: { x: 0, y: 0 }, measured: { width: 196, height: 82 }, data: {} },
      { id: "b", position: { x: 0, y: 0 }, measured: { width: 196, height: 82 }, data: {} },
    ];
    const laidOut = layoutMeasuredNodes(initial, spec);
    expect(laidOut[0].position).not.toEqual(laidOut[1].position);
    expect(laidOut[0].sourcePosition).toBe(Position.Right);
  });

  it("includes self-loop arches and offset label extents in fit bounds", () => {
    const loopSpec: DiagramSpec = {
      id: "loop",
      title: "Loop",
      direction: "LR",
      nodes: [{ id: "a", label: "A", kind: "task", facts: [] }],
      edges: [{ id: "a-a", source: "a", target: "a", kind: "task", label: "retry" }],
    };
    const loopBounds = getFlowBounds([nodes[0]], loopSpec, [edge(loopSpec.edges[0])]);
    expect(loopBounds.y).toBeLessThan(100);
    expect(loopBounds.height).toBeGreaterThan(82);

    const labelSpec: DiagramSpec = {
      id: "labels",
      title: "Labels",
      direction: "LR",
      nodes: [
        { id: "a", label: "A", kind: "task", facts: [] },
        { id: "b", label: "B", kind: "task", facts: [] },
      ],
      edges: [
        { id: "a-b", source: "a", target: "b", kind: "task", label: "offset label", offset: 120 },
      ],
    };
    const labelBounds = getFlowBounds(nodes, labelSpec, labelSpec.edges.map(edge));
    expect(labelBounds.y + labelBounds.height).toBeGreaterThan(182);
  });
});
