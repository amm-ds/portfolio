import { memo, useEffect, useId, useMemo, useState } from "react";
import dagre from "@dagrejs/dagre";
import {
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useNodesData,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { getDiagramSpec } from "../../diagrams";
import { diagramSpecErrors, type DiagramMessageKind, type DiagramNodeKind, type DiagramSpec } from "../../diagrams/types";
import { DiagramFallback } from "./DiagramFallback";
import type { FlowDiagramProps, FlowDiagramRegistryProps } from "./LazyFlowDiagram";

const NODE_WIDTH = 196;
const EDGE_COLORS: Record<DiagramMessageKind, string> = {
  task: "var(--secondary)",
  result: "var(--accent)",
  error: "var(--danger)",
};

type FlowNodeData = {
  label: string;
  kind: DiagramNodeKind;
  facts: readonly string[];
};
type FlowNode = Node<FlowNodeData, "diagram">;
type FlowEdge = Edge<{ kind: DiagramMessageKind }>;

const DiagramNodeView = memo(function DiagramNodeView({
  data,
  sourcePosition,
  targetPosition,
}: NodeProps<FlowNode>) {
  return (
    <div className={`flow-node flow-node--${data.kind}`}>
      <Handle type="target" position={targetPosition ?? Position.Left} isConnectable={false} />
      <span className="flow-node__kind">{data.kind}</span>
      <span className="flow-node__label">{data.label}</span>
      <span className="flow-node__action">select for facts →</span>
      <Handle type="source" position={sourcePosition ?? Position.Right} isConnectable={false} />
    </div>
  );
});

const nodeTypes: NodeTypes = { diagram: DiagramNodeView };
const NODE_A11Y_DESCRIPTION = "Press enter or space to inspect a node. Press escape to close the inspector.";
const ARIA_LABEL_CONFIG = {
  "node.a11yDescription.default": NODE_A11Y_DESCRIPTION,
  "node.a11yDescription.keyboardDisabled": NODE_A11Y_DESCRIPTION,
  "edge.a11yDescription.default": "Directed edges show task, result, and error messages. Edges are read-only.",
};

function toFlow(spec: DiagramSpec): { nodes: FlowNode[]; edges: FlowEdge[] } {
  return {
    nodes: spec.nodes.map((node) => ({
      id: node.id,
      type: "diagram",
      position: { x: 0, y: 0 },
      data: { label: node.label, kind: node.kind, facts: node.facts },
      style: { width: NODE_WIDTH },
      ariaRole: "button",
      deletable: false,
    })),
    edges: spec.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      label: edge.label,
      data: { kind: edge.kind },
      className: `flow-edge flow-edge--${edge.kind}`,
      style: {
        stroke: EDGE_COLORS[edge.kind],
        strokeWidth: 1.8,
        strokeDasharray: edge.kind === "error" ? "7 4" : undefined,
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLORS[edge.kind], width: 18, height: 18 },
      labelStyle: { fill: "var(--text)", fontFamily: "var(--mono)", fontSize: 10 },
      labelBgStyle: { fill: "var(--bg)", fillOpacity: 0.96 },
      labelBgPadding: [6, 3],
      labelBgBorderRadius: 4,
      ariaLabel: `${edge.label ?? edge.kind}: ${edge.source} to ${edge.target}`,
      focusable: false,
    })),
  };
}

/** Dagre positions use measured v12 node dimensions, never guessed heights. */
function layoutMeasuredNodes(nodes: FlowNode[], spec: DiagramSpec): FlowNode[] {
  const graph = new dagre.graphlib.Graph();
  graph.setGraph({ rankdir: spec.direction, nodesep: 42, ranksep: 72, marginx: 24, marginy: 24 });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const node of nodes) {
    graph.setNode(node.id, {
      width: node.measured?.width ?? NODE_WIDTH,
      height: node.measured?.height ?? 80,
    });
  }
  for (const edge of spec.edges) graph.setEdge(edge.source, edge.target);
  dagre.layout(graph);

  return nodes.map((node) => {
    const width = node.measured?.width ?? NODE_WIDTH;
    const height = node.measured?.height ?? 80;
    const point = graph.node(node.id);
    return {
      ...node,
      position: { x: point.x - width / 2, y: point.y - height / 2 },
      sourcePosition: spec.direction === "LR" ? Position.Right : Position.Bottom,
      targetPosition: spec.direction === "LR" ? Position.Left : Position.Top,
    };
  });
}

function FlowCanvas({ spec }: FlowDiagramProps) {
  const initial = useMemo(() => toFlow(spec), [spec]);
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>(initial.nodes);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [laidOut, setLaidOut] = useState(false);
  const [ready, setReady] = useState(false);
  const selectedNode = useNodesData<FlowNode>(selectedId ?? "");
  const { fitView } = useReactFlow();
  const instructionsId = useId();

  useEffect(() => {
    if (laidOut || nodes.length === 0) return;
    if (!nodes.every((node) => node.measured?.width && node.measured?.height)) return;
    setNodes((current) => layoutMeasuredNodes(current, spec));
    setLaidOut(true);
  }, [laidOut, nodes, setNodes, spec]);

  useEffect(() => {
    if (!laidOut) return;
    let cancelled = false;
    // Let the positioned nodes commit and the canvas settle before fitting:
    // a macrotask timeout alone can fire before the layout pass paints,
    // leaving the viewport zoomed at the origin while the graph sits
    // bottom-right. Re-fit whenever nodes change (idempotent).
    const raf = requestAnimationFrame(() => {
      if (cancelled) return;
      void fitView({ padding: 0.2, maxZoom: 1, duration: 0 });
      setReady(true);
    });
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
  }, [fitView, laidOut, nodes]);

  return (
    <section className="flow-diagram" aria-label={spec.title}>
      <div className="flow-diagram__heading">
        <span className="flow-diagram__title">{spec.title}</span>
        <span className="flow-diagram__hint" id={instructionsId}>
          Select a node for committed facts · scroll to zoom
        </span>
      </div>
      <div className={`flow-diagram__body${selectedNode ? " has-inspector" : ""}`}>
        <div
          className="flow-diagram__canvas"
          style={{ height: spec.canvasHeight ?? 360 }}
        >
          {!ready && (
            <div className="frame-skeleton" aria-hidden="true">
              <span>rendering diagram…</span>
            </div>
          )}
          <ReactFlow<FlowNode, FlowEdge>
            nodes={nodes}
            edges={initial.edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onNodeClick={(_, node) => setSelectedId(node.id)}
            onSelectionChange={({ nodes: selected }) => setSelectedId(selected[0]?.id ?? null)}
            onPaneClick={() => setSelectedId(null)}
            nodesDraggable={false}
            nodesConnectable={false}
            nodesFocusable
            edgesFocusable={false}
            edgesReconnectable={false}
            elementsSelectable
            deleteKeyCode={null}
            selectionOnDrag={false}
            panOnDrag
            zoomOnScroll
            zoomOnPinch
            minZoom={0.25}
            maxZoom={1.75}
            onlyRenderVisibleElements={false}
            fitView
            fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
            aria-label={`${spec.title} interactive diagram`}
            aria-describedby={instructionsId}
            ariaLabelConfig={ARIA_LABEL_CONFIG}
          >
            <Controls position="bottom-right" showInteractive={false} />
          </ReactFlow>
        </div>
        {selectedNode && (
          <aside className="flow-inspector" aria-live="polite" aria-label={`Facts for ${selectedNode.data.label}`}>
            <div className="flow-inspector__header">
              <div>
                <span className="flow-inspector__kind">{selectedNode.data.kind}</span>
                <h3>{selectedNode.data.label}</h3>
              </div>
              <button type="button" className="flow-inspector__close" onClick={() => setSelectedId(null)} aria-label="Close inspector">
                ×
              </button>
            </div>
            <p className="flow-inspector__source">Committed project evidence</p>
            <ul>
              {selectedNode.data.facts.map((fact) => (
                <li key={fact}>{fact}</li>
              ))}
            </ul>
          </aside>
        )}
      </div>
      <div className="flow-diagram__legend" aria-label="Edge message kinds">
        <span className="flow-legend--task">→ task</span>
        <span className="flow-legend--result">→ result</span>
        <span className="flow-legend--error">⇢ error / repair</span>
      </div>
    </section>
  );
}

export function FlowDiagram({ spec }: FlowDiagramProps) {
  const errors = diagramSpecErrors(spec);
  if (errors.length > 0) throw new Error(`Invalid diagram spec ${spec.id}: ${errors.join(", ")}`);

  return (
    <ReactFlowProvider>
      <FlowCanvas spec={spec} />
    </ReactFlowProvider>
  );
}

export function FlowDiagramFromRegistry({ specId }: FlowDiagramRegistryProps) {
  const spec = getDiagramSpec(specId);
  return spec ? <FlowDiagram spec={spec} /> : <DiagramFallback specId={specId} reason="Unknown diagram spec." />;
}
