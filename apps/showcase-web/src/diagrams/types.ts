export const DIAGRAM_NODE_KINDS = ["source", "agent", "model", "tool", "data", "api", "gate", "output"] as const;
export const DIAGRAM_MESSAGE_KINDS = ["task", "result", "error"] as const;

export type DiagramNodeKind = (typeof DIAGRAM_NODE_KINDS)[number];
export type DiagramMessageKind = (typeof DIAGRAM_MESSAGE_KINDS)[number];
export type DiagramDirection = "LR" | "TB";

export interface DiagramSpecNode {
  id: string;
  label: string;
  kind: DiagramNodeKind;
  facts: readonly string[];
}

export interface DiagramSpecEdge {
  id: string;
  source: string;
  target: string;
  kind: DiagramMessageKind;
  label?: string;
}

export interface DiagramSpec {
  id: string;
  title: string;
  direction: DiagramDirection;
  /** Upper cap in px for the measured, auto-sized canvas (maximum 560). */
  canvasHeight?: number;
  nodes: readonly DiagramSpecNode[];
  edges: readonly DiagramSpecEdge[];
}

/** Structural checks for the fence-facing spec registry and its unit tests. */
export function diagramSpecErrors(spec: DiagramSpec): string[] {
  const errors: string[] = [];
  if (!spec.id.trim()) errors.push("spec id is required");
  if (!spec.title.trim()) errors.push("spec title is required");
  if (spec.direction !== "LR" && spec.direction !== "TB") errors.push("direction must be LR or TB");
  if (spec.nodes.length === 0) errors.push("at least one node is required");

  const nodeIds = new Set<string>();
  for (const node of spec.nodes) {
    if (!node.id.trim() || !node.label.trim()) errors.push("node id and label are required");
    if (nodeIds.has(node.id)) errors.push(`duplicate node id: ${node.id}`);
    nodeIds.add(node.id);
    if (!DIAGRAM_NODE_KINDS.includes(node.kind)) errors.push(`invalid node kind: ${node.id}`);
    if (node.facts.some((fact) => !fact.trim())) {
      errors.push(`node facts must be non-blank: ${node.id}`);
    }
  }

  const edgeIds = new Set<string>();
  for (const edge of spec.edges) {
    if (!edge.id.trim()) errors.push("edge id is required");
    if (edgeIds.has(edge.id)) errors.push(`duplicate edge id: ${edge.id}`);
    edgeIds.add(edge.id);
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
      errors.push(`dangling edge: ${edge.id}`);
    }
    if (!DIAGRAM_MESSAGE_KINDS.includes(edge.kind)) errors.push(`invalid edge kind: ${edge.id}`);
  }
  return errors;
}
