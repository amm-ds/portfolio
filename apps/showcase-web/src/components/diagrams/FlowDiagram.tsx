import { memo, useEffect, useId, useMemo, useRef, useState } from "react";
import dagre from "@dagrejs/dagre";
import {
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  getNodesBounds,
  getSmoothStepPath,
  getViewportForBounds,
  Handle,
  MarkerType,
  NodeToolbar,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge,
  type EdgeProps,
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
/** Mermaid-logic shapes make a node's role readable before its label is:
 *  stadium for terminals, cylinder for stores, subroutine for tools,
 *  hexagon for APIs, rhombus for decision gates. */
const KIND_SHAPES: Record<DiagramNodeKind, string> = {
  source: "stadium",
  output: "stadium",
  data: "cylinder",
  tool: "subroutine",
  api: "hexagon",
  gate: "rhombus",
  model: "rect",
  agent: "rect",
};
const EDGE_COLORS: Record<DiagramMessageKind, string> = {
  task: "var(--secondary)",
  result: "var(--accent)",
  error: "var(--danger)",
};

type FlowNodeData = {
  label: string;
  kind: DiagramNodeKind;
  facts: readonly string[];
  preview?: string;
};
type FlowNode = Node<FlowNodeData, "diagram">;
type FlowEdgeData = {
  kind: DiagramMessageKind;
  label?: string;
  /** Vertical shift of the mid segment — parallel call/result pairs bend
   *  apart instead of drawing on top of each other. */
  offset: number;
};
type FlowEdge = Edge<FlowEdgeData>;

const DiagramNodeView = memo(function DiagramNodeView({
  data,
  sourcePosition,
  targetPosition,
}: NodeProps<FlowNode>) {
  const shape = KIND_SHAPES[data.kind];
  return (
    <div className={`flow-node flow-node--${data.kind} flow-node--${shape}`}>
      {data.preview && (
        <NodeToolbar isVisible position={Position.Top} offset={8} className="flow-node__preview" role="tooltip">
          {data.preview}
        </NodeToolbar>
      )}
      {shape === "cylinder" && (
        <svg className="flow-node__cylinder" viewBox="0 0 196 82" preserveAspectRatio="none" aria-hidden="true">
          <path
            d="M8 14 C8 6 46 2 98 2 C150 2 188 6 188 14 L188 68 C188 76 150 80 98 80 C46 80 8 76 8 68 Z M8 14 C8 22 46 26 98 26 C150 26 188 22 188 14"
            fill="var(--surface)"
            stroke="currentColor"
          />
        </svg>
      )}
      <Handle type="target" position={targetPosition ?? Position.Left} isConnectable={false} />
      <span className="flow-node__kind">{data.kind}</span>
      <span className="flow-node__label">{data.label}</span>
      <Handle type="source" position={sourcePosition ?? Position.Right} isConnectable={false} />
    </div>
  );
});

function selfLoopGeometry(
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
      archY - 8,
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

/** Custom edge: separated smooth-step paths, explicit self-loops, and HTML
 *  labels above the node layer. Legibility states (muted/lit/dim) are driven
 *  by class names computed in FlowCanvas from hover/selection. */
const DiagramEdgeView = memo(function DiagramEdgeView({
  id,
  source,
  target,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
}: EdgeProps<FlowEdge>) {
  const [path, baseLabelX, baseLabelY] =
    source === target
      ? selfLoopGeometry(sourceX, sourceY, targetX, targetY, sourcePosition)
      : getSmoothStepPath({
          sourceX,
          sourceY,
          sourcePosition,
          targetX,
          targetY,
          targetPosition,
          borderRadius: 14,
          offset: data?.offset ?? 0,
        });
  // getSmoothStepPath bends reciprocal edges but keeps their label anchors
  // together. Move each label with its path so call/repair text stays apart.
  const horizontal = sourcePosition === Position.Left || sourcePosition === Position.Right;
  const labelShift = data?.offset ?? 0;
  const labelX = baseLabelX + (horizontal ? 0 : labelShift);
  const labelY = baseLabelY + (horizontal ? labelShift : 0);
  const label = data?.label;
  return (
    <>
      <BaseEdge id={id} path={path} className="flow-edge__path" markerEnd={markerEnd} />
      {label ? (
        <EdgeLabelRenderer>
          <div
            className="flow-edge__label"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
});

const nodeTypes: NodeTypes = { diagram: DiagramNodeView };
const edgeTypes = { diagram: DiagramEdgeView };
const NODE_A11Y_DESCRIPTION = "Press enter or space to inspect a node. Press escape to close the inspector.";
const ARIA_LABEL_CONFIG = {
  "node.a11yDescription.default": NODE_A11Y_DESCRIPTION,
  "node.a11yDescription.keyboardDisabled": NODE_A11Y_DESCRIPTION,
  "edge.a11yDescription.default": "Directed edges show task, result, and error messages. Edges are read-only.",
};

function toFlow(spec: DiagramSpec): { nodes: FlowNode[]; edges: FlowEdge[] } {
  // Parallel edges between the same pair draw on top of each other at offset
  // 0; bend the mid segment alternately so call and result paths separate.
  const pairCounts = new Map<string, number>();
  const pairKey = (a: string, b: string) => [a, b].sort().join("→");
  return {
    nodes: spec.nodes.map((node) => ({
      id: node.id,
      type: "diagram",
      position: { x: 0, y: 0 },
      data: { label: node.label, kind: node.kind, facts: node.facts },
      style: { width: node.kind === "gate" ? 236 : NODE_WIDTH },
      ariaRole: "button",
      deletable: false,
    })),
    edges: spec.edges.map((edge) => {
      const key = pairKey(edge.source, edge.target);
      const occurrence = pairCounts.get(key) ?? 0;
      pairCounts.set(key, occurrence + 1);
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: "diagram",
        data: {
          kind: edge.kind,
          label: edge.label,
          offset: occurrence === 0 ? 0 : occurrence % 2 === 1 ? 26 : -26,
        },
        className: `flow-edge flow-edge--${edge.kind}`,
        style: {
          strokeDasharray: edge.kind === "error" ? "7 4" : undefined,
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLORS[edge.kind], width: 22, height: 22 },
        ariaLabel: `${edge.label ?? edge.kind}: ${edge.source} to ${edge.target}`,
        focusable: true,
      };
    }),
  };
}

/** True when nodeId sits at either end of any edge touching focusId. */
function touchesNode(edges: FlowEdge[], nodeId: string, focusId: string): boolean {
  return edges.some(
    (edge) =>
      (edge.source === focusId && edge.target === nodeId) ||
      (edge.target === focusId && edge.source === nodeId),
  );
}

/** Dagre positions use measured v12 node dimensions, never guessed heights. */
function layoutMeasuredNodes(nodes: FlowNode[], spec: DiagramSpec): FlowNode[] {
  const graph = new dagre.graphlib.Graph();
  graph.setGraph({
    rankdir: spec.direction,
    nodesep: 80,
    ranksep: 128,
    marginx: 64,
    marginy: 112,
  });
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

const MIN_CANVAS_HEIGHT = 240;
const MAX_CANVAS_HEIGHT = 560;
const MIN_ZOOM = 0.1;
const MOBILE_INITIAL_ZOOM = 0.65;
const MOBILE_BREAKPOINT = 640;
const FIT_PADDING = 0.12;

function canvasHeightCap(spec: DiagramSpec): number {
  return Math.min(spec.canvasHeight ?? MAX_CANVAS_HEIGHT, MAX_CANVAS_HEIGHT);
}

function autoCanvasHeight(boundsHeight: number, fittedZoom: number, spec: DiagramSpec): number {
  return Math.min(
    canvasHeightCap(spec),
    Math.max(MIN_CANVAS_HEIGHT, Math.min(MAX_CANVAS_HEIGHT, boundsHeight * fittedZoom + 64)),
  );
}

function FlowCanvas({ spec }: FlowDiagramProps) {
  const initial = useMemo(() => toFlow(spec), [spec]);
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>(initial.nodes);
  const [edges] = useEdgesState<FlowEdge>(initial.edges);
  const [laidOut, setLaidOut] = useState(false);
  const [ready, setReady] = useState(false);
  const [canvasHeight, setCanvasHeight] = useState(() => canvasHeightCap(spec));
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [pinnedEdgeId, setPinnedEdgeId] = useState<string | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  // The inspector follows the nodes' own selection flag — one source of
  // truth, so closing it cannot disagree with the canvas selection ring.
  const selectedNode = nodes.find((node) => node.selected) ?? null;
  const { setViewport } = useReactFlow();
  const instructionsId = useId();

  const clearSelection = () => {
    setPinnedEdgeId(null);
    setNodes((current) =>
      current.some((node) => node.selected)
        ? current.map((node) => ({ ...node, selected: false }))
        : current,
    );
  };

  // Neighborhood focus: hover or selection lights the node's connections and
  // fades the rest, so dense loops read one relationship at a time.
  const focusId = hoveredId ?? selectedNode?.id ?? null;
  const connected = useMemo(() => {
    if (!focusId) return null;
    const ids = new Set<string>();
    for (const edge of edges) {
      if (edge.source === focusId || edge.target === focusId) ids.add(edge.id);
    }
    return ids;
  }, [edges, focusId]);

  const styledEdges = useMemo(
    () =>
      edges.map((edge) => {
        const lit = connected ? connected.has(edge.id) : false;
        const pinned = edge.id === pinnedEdgeId;
        return {
          ...edge,
          className:
            `flow-edge flow-edge--${edge.data?.kind ?? "task"}` +
            (connected ? (lit ? " is-lit" : " is-dim") : "") +
            (pinned ? " is-pinned" : ""),
          selected: pinned,
        };
      }),
    [edges, connected, pinnedEdgeId],
  );

  const styledNodes = useMemo(
    () =>
      nodes.map((node) => {
        const preview = !selectedNode && hoveredId === node.id ? node.data.facts[0] : undefined;
        return {
          ...node,
          data: { ...node.data, preview },
          zIndex: preview ? 10 : node.zIndex,
          className:
            connected && focusId && node.id !== focusId && !touchesNode(edges, node.id, focusId)
              ? "is-dim"
              : undefined,
        };
      }),
    [nodes, edges, connected, focusId, hoveredId, selectedNode],
  );

  useEffect(() => {
    if (laidOut || nodes.length === 0) return;
    if (!nodes.every((node) => node.measured?.width && node.measured?.height)) return;
    setNodes((current) => layoutMeasuredNodes(current, spec));
    setLaidOut(true);
  }, [laidOut, nodes, setNodes, spec]);

  useEffect(() => {
    if (!laidOut || ready) return;
    let cancelled = false;
    // Fit once, after the positioned nodes commit. Selection and hover updates
    // re-run this effect's dependencies but the ready guard prevents a re-fit.
    const raf = requestAnimationFrame(() => {
      const canvas = canvasRef.current;
      if (cancelled || !canvas || canvas.clientWidth === 0 || canvas.clientHeight === 0) return;

      const bounds = getNodesBounds(nodes, { nodeOrigin: [0, 0] });
      // A fitted horizontal graph is unreadable on a phone. Keep its existing
      // layout, but open at a readable zoom and let touch users pan across it.
      const mobile = canvas.clientWidth <= MOBILE_BREAKPOINT;
      const minInitialZoom = mobile ? MOBILE_INITIAL_ZOOM : MIN_ZOOM;
      const firstViewport = getViewportForBounds(
        bounds,
        canvas.clientWidth,
        canvas.clientHeight,
        minInitialZoom,
        1,
        FIT_PADDING,
      );
      const nextHeight = autoCanvasHeight(bounds.height, firstViewport.zoom, spec);
      // Recenter against the auto-height canvas without changing the initial zoom.
      const viewport = getViewportForBounds(
        bounds,
        canvas.clientWidth,
        nextHeight,
        minInitialZoom,
        1,
        FIT_PADDING,
      );
      setCanvasHeight(autoCanvasHeight(bounds.height, viewport.zoom, spec));
      void setViewport(viewport, { duration: 0 });
      setReady(true);
    });
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
  }, [laidOut, nodes, ready, setViewport, spec]);

  return (
    <section className="flow-diagram" aria-label={spec.title}>
      <div className="flow-diagram__heading">
        <span className="flow-diagram__title">{spec.title}</span>
        <span className="flow-diagram__zoom-hint" id={instructionsId}>
          Scroll or pinch to zoom · drag to pan
        </span>
      </div>
      <div className={`flow-diagram__body${selectedNode ? " has-inspector" : ""}`}>
        <div ref={canvasRef} className="flow-diagram__canvas" style={{ height: canvasHeight }}>
          {!ready && (
            <div className="frame-skeleton" aria-hidden="true">
              <span>rendering diagram…</span>
            </div>
          )}
          <ReactFlow<FlowNode, FlowEdge>
            nodes={styledNodes}
            edges={styledEdges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onNodesChange={onNodesChange}
            onNodeClick={(_, node) =>
              setNodes((current) =>
                current.map((n) => ({ ...n, selected: n.id === node.id })),
              )
            }
            onNodeMouseEnter={(_, node) => setHoveredId(node.id)}
            onNodeMouseLeave={() => setHoveredId(null)}
            onEdgeClick={(_, edge) =>
              setPinnedEdgeId((current) => (current === edge.id ? null : edge.id))
            }
            onPaneClick={clearSelection}
            nodesDraggable={false}
            nodesConnectable={false}
            nodesFocusable
            autoPanOnNodeFocus
            edgesFocusable
            edgesReconnectable={false}
            elementsSelectable
            deleteKeyCode={null}
            selectionOnDrag={false}
            panOnDrag
            zoomOnScroll
            zoomOnPinch
            minZoom={MIN_ZOOM}
            maxZoom={1.75}
            onlyRenderVisibleElements={false}
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
              <button type="button" className="flow-inspector__close" onClick={clearSelection} aria-label="Close inspector">
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
      <FlowCanvas key={spec.id} spec={spec} />
    </ReactFlowProvider>
  );
}

export function FlowDiagramFromRegistry({ specId }: FlowDiagramRegistryProps) {
  const spec = getDiagramSpec(specId);
  return spec ? <FlowDiagram spec={spec} /> : <DiagramFallback specId={specId} reason="Unknown diagram spec." />;
}
