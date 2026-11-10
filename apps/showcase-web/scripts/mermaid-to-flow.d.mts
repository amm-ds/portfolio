/** Type surface of the dev-time mermaid converter, resolved by TypeScript for
 *  both the unit tests (src/__tests__/mermaidToFlow.test.ts) and editors. */
export interface ParsedMermaidNode {
  id: string;
  label: string;
  shape: string;
  kind: string;
  subgraph: string | null;
}

export interface ParsedMermaidSubgraph {
  id: string;
  label: string;
  members: string[];
  internalEdges: unknown[];
}

export interface ParsedMermaidEdge {
  source: string;
  target: string;
  kind: string;
  label?: string;
}

export interface ParsedMermaid {
  nodes: Map<string, ParsedMermaidNode>;
  subgraphs: Map<string, ParsedMermaidSubgraph>;
  edges: ParsedMermaidEdge[];
  direction: string;
  errors: string[];
}

export function inferNodeKind(label: string, id?: string): string;
export function parseMermaid(block: string[], where: string): ParsedMermaid;
export const SPEC_OVERRIDES: Record<string, Record<string, unknown>>;
