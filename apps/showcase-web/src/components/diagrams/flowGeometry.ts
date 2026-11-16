import dagre from "@dagrejs/dagre";
import {
  getNodesBounds,
  getSmoothStepPath,
  Position,
  type Edge,
  type Node,
  type Rect,
} from "@xyflow/react";
import type { DiagramSpec, DiagramSpecEdge } from "../../diagrams/types";

export const NODE_WIDTH = 196;
const DEFAULT_NODE_HEIGHT = 80;
const MAX_LABEL_WIDTH = 260;
const LABEL_CHAR_WIDTH = 7.2;
const LABEL_LINE_HEIGHT = 16;

export function labelDimensions(label: string): { width: number; height: number } {
  const width = Math.min(MAX_LABEL_WIDTH, Math.max(40, label.length * LABEL_CHAR_WIDTH + 18));
  const lines = Math.max(1, Math.ceil((label.length * LABEL_CHAR_WIDTH) / (width - 18)));
  return { width, height: lines * LABEL_LINE_HEIGHT + 8 };
}

/** Dagre positions use measured v12 node dimensions and reserve space for
 * named parallel edges and their labels. */
export function layoutMeasuredNodes<NodeType extends Node>(
  nodes: NodeType[],
  spec: DiagramSpec,
): NodeType[] {
  const graph = new dagre.graphlib.Graph({ multigraph: true });
  graph.setGraph({
    rankdir: spec.direction,
    nodesep: 80,
    ranksep: 144,
    marginx: 64,
    marginy: 112,
  });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const node of nodes) {
    graph.setNode(node.id, {
      width: node.measured?.width ?? NODE_WIDTH,
      height: node.measured?.height ?? DEFAULT_NODE_HEIGHT,
    });
  }
  for (const edge of spec.edges) {
    graph.setEdge(edge.source, edge.target, edge.label ? labelDimensions(edge.label) : {}, edge.id);
  }
  dagre.layout(graph);

  return nodes.map((node) => {
    const width = node.measured?.width ?? NODE_WIDTH;
    const height = node.measured?.height ?? DEFAULT_NODE_HEIGHT;
    const point = graph.node(node.id);
    return {
      ...node,
      position: { x: point.x - width / 2, y: point.y - height / 2 },
      sourcePosition: spec.direction === "LR" ? Position.Right : Position.Bottom,
      targetPosition: spec.direction === "LR" ? Position.Left : Position.Top,
    };
  });
}

export function selfLoopGeometry(
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
  sourcePosition: Position,
): [string, number, number] {
  const horizontal = sourcePosition === Position.Left || sourcePosition === Position.Right;
  if (horizontal) {
    const direction = sourcePosition === Position.Right ? 1 : -1;
    const archY = Math.min(sourceY, targetY) - 88;
    return [
      `M ${sourceX} ${sourceY} C ${sourceX + 64 * direction} ${archY}, ${targetX - 64 * direction} ${archY}, ${targetX} ${targetY}`,
      (sourceX + targetX) / 2,
      archY - 16,
    ];
  }
  const direction = sourcePosition === Position.Bottom ? 1 : -1;
  const archX = Math.max(sourceX, targetX) + 88;
  return [
    `M ${sourceX} ${sourceY} C ${archX} ${sourceY + 64 * direction}, ${archX} ${targetY - 64 * direction}, ${targetX} ${targetY}`,
    archX + 8,
    (sourceY + targetY) / 2,
  ];
}

function nodeDimensions(node: Node): { width: number; height: number } {
  return {
    width:
      node.measured?.width ??
      (typeof node.style?.width === "number" ? node.style.width : NODE_WIDTH),
    height: node.measured?.height ?? DEFAULT_NODE_HEIGHT,
  };
}

function handlePoint(
  node: Node,
  edge: Edge,
  edges: readonly Edge[],
  type: "source" | "target",
): { x: number; y: number; position: Position } {
  const { width, height } = nodeDimensions(node);
  const position =
    type === "source"
      ? (node.sourcePosition ?? Position.Right)
      : (node.targetPosition ?? Position.Left);
  const siblings = edges.filter((candidate) => candidate[type] === node.id);
  const index = Math.max(0, siblings.findIndex((candidate) => candidate.id === edge.id));
  const ratio = (index + 1) / (siblings.length + 1);
  const horizontal = position === Position.Left || position === Position.Right;
  return {
    x:
      node.position.x +
      (horizontal ? (position === Position.Right ? width : 0) : width * ratio),
    y:
      node.position.y +
      (horizontal ? height * ratio : position === Position.Bottom ? height : 0),
    position,
  };
}

/** Fit labels and self-loop control extents as well as nodes. Label dimensions
 * deliberately mirror the CSS chip constraints so overview never clips text. */
export function getFlowBounds<NodeType extends Node>(
  nodes: NodeType[],
  spec: DiagramSpec,
  edges: readonly Edge[],
  measuredBounds?: Rect,
): Rect {
  const nodeBounds = measuredBounds ?? getNodesBounds(nodes, { nodeOrigin: [0, 0] });
  let minX = nodeBounds.x;
  let minY = nodeBounds.y;
  let maxX = nodeBounds.x + nodeBounds.width;
  let maxY = nodeBounds.y + nodeBounds.height;
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const include = (x: number, y: number, width = 0, height = 0) => {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x + width);
    maxY = Math.max(maxY, y + height);
  };
  const includeLabel = (label: string | undefined, x: number, y: number) => {
    if (!label) return;
    const { width, height } = labelDimensions(label);
    include(x - width / 2, y - height / 2, width, height);
  };

  for (const edge of spec.edges) {
    const flowEdge = edges.find((candidate) => candidate.id === edge.id);
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    if (!flowEdge || !source || !target) continue;
    const sourcePoint = handlePoint(source, flowEdge, edges, "source");
    const targetPoint = handlePoint(target, flowEdge, edges, "target");
    const offset = edge.offset ?? Number(flowEdge.data?.offset ?? 0);
    if (edge.source === edge.target) {
      const [, labelX, labelY] = selfLoopGeometry(
        sourcePoint.x,
        sourcePoint.y,
        targetPoint.x,
        targetPoint.y,
        sourcePoint.position,
      );
      // Conservative control-point bounds include the whole cubic loop.
      if (sourcePoint.position === Position.Left || sourcePoint.position === Position.Right) {
        const direction = sourcePoint.position === Position.Right ? 1 : -1;
        include(
          Math.min(sourcePoint.x, targetPoint.x, sourcePoint.x + 64 * direction, targetPoint.x - 64 * direction),
          labelY,
          Math.abs(targetPoint.x - sourcePoint.x) + 128,
          Math.max(sourcePoint.y, targetPoint.y) - labelY,
        );
      } else {
        include(
          Math.min(sourcePoint.x, targetPoint.x),
          Math.min(sourcePoint.y, targetPoint.y),
          labelX - Math.min(sourcePoint.x, targetPoint.x),
          Math.abs(targetPoint.y - sourcePoint.y) + 128,
        );
      }
      includeLabel(edge.label, labelX, labelY);
      continue;
    }
    const horizontal =
      sourcePoint.position === Position.Left || sourcePoint.position === Position.Right;
    const backwards = horizontal
      ? targetPoint.x < sourcePoint.x
      : targetPoint.y < sourcePoint.y;
    const routeOffset = offset || (backwards ? 48 : 0);
    const [, baseLabelX, baseLabelY] = getSmoothStepPath({
      sourceX: sourcePoint.x,
      sourceY: sourcePoint.y,
      sourcePosition: sourcePoint.position,
      targetX: targetPoint.x,
      targetY: targetPoint.y,
      targetPosition: targetPoint.position,
      borderRadius: 14,
      offset: 0,
    });
    includeLabel(
      edge.label,
      baseLabelX + (horizontal ? 0 : routeOffset),
      baseLabelY + (horizontal ? routeOffset : 0),
    );
  }
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

export function parallelEdgeOffset(
  edge: DiagramSpecEdge,
  occurrence: number,
  pairSize: number,
): number {
  return edge.offset ?? (occurrence - (pairSize - 1) / 2) * 34;
}
