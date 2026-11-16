import { memo, useEffect, useId, useMemo, useRef, useState } from "react";
import {
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
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
import {
  getFlowBounds,
  layoutMeasuredNodes,
  NODE_WIDTH,
  parallelEdgeOffset,
  selfLoopGeometry,
} from "./flowGeometry";
import type { FlowDiagramProps, FlowDiagramRegistryProps } from "./LazyFlowDiagram";
/** Mermaid-logic shapes make a node's role readable before its label is:
 *  stadium for terminals, cylinder for stores, subroutine for tools,
 *  hexagon for APIs, rhombus for decision gates. */
const KIND_SHAPES: Record<DiagramNodeKind, string> = {
  source: "stadium",
  output: "stadium",
  data: "cylinder",
  tool: "subroutine",
  task: "rect",
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
  sourceHandleCount: number;
  targetHandleCount: number;
  preview?: string;
};
type FlowNode = Node<FlowNodeData, "diagram">;
type FlowEdgeData = {
  kind: DiagramMessageKind;
  label?: string;
  /** Perpendicular shift of the mid segment and its portaled label. */
  offset: number;
  lit: boolean;
  dim: boolean;
  pinned: boolean;
};
type FlowEdge = Edge<FlowEdgeData>;

function DiagramHandles({
  type,
  count,
  position,
}: {
  type: "source" | "target";
  count: number;
  position: Position;
}) {
  const horizontal = position === Position.Left || position === Position.Right;
  return Array.from({ length: count }, (_, index) => (
    <Handle
      key={`${type}-${index}`}
      id={`${type}-${index}`}
      type={type}
      position={position}
      isConnectable={false}
      style={horizontal
        ? { top: `${((index + 1) / (count + 1)) * 100}%` }
        : { left: `${((index + 1) / (count + 1)) * 100}%` }}
    />
  ));
}

const DiagramNodeView = memo(function DiagramNodeView({
  data,
  sourcePosition,
  targetPosition,
}: NodeProps<FlowNode>) {
  const shape = KIND_SHAPES[data.kind];
  const source = sourcePosition ?? Position.Right;
  const target = targetPosition ?? Position.Left;
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
      <DiagramHandles type="target" count={data.targetHandleCount} position={target} />
      <span className="flow-node__kind">{data.kind}</span>{" "}
      <span className="flow-node__label">{data.label}</span>
      <DiagramHandles type="source" count={data.sourceHandleCount} position={source} />
    </div>
  );
});

/** Custom edge: separated smooth-step paths, explicit self-loops, and HTML
 *  labels above the node layer. Portaled labels receive focus state directly;
 *  selectors on the SVG edge cannot reach EdgeLabelRenderer's DOM subtree. */
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
  const horizontal = sourcePosition === Position.Left || sourcePosition === Position.Right;
  const backwards = source !== target && (horizontal ? targetX < sourceX : targetY < sourceY);
  const labelShift = data?.offset || (backwards ? 48 : 0);
  const middleX = (sourceX + targetX) / 2;
  const middleY = (sourceY + targetY) / 2;
  const sourceDirection = sourcePosition === Position.Right || sourcePosition === Position.Bottom ? 1 : -1;
  const targetDirection = targetPosition === Position.Right || targetPosition === Position.Bottom ? 1 : -1;
  // Reviewed offsets are lanes, not diagonal arcs: leave both nodes outward,
  // travel outside intermediate columns, then enter the target from outside.
  const sourceExit = horizontal ? sourceX + sourceDirection * 32 : sourceY + sourceDirection * 32;
  const targetExit = horizontal ? targetX + targetDirection * 32 : targetY + targetDirection * 32;
  const routedPath = horizontal
    ? `M ${sourceX} ${sourceY} L ${sourceExit} ${sourceY} L ${sourceExit} ${middleY + labelShift} L ${targetExit} ${middleY + labelShift} L ${targetExit} ${targetY} L ${targetX} ${targetY}`
    : `M ${sourceX} ${sourceY} L ${sourceX} ${sourceExit} L ${middleX + labelShift} ${sourceExit} L ${middleX + labelShift} ${targetExit} L ${targetX} ${targetExit} L ${targetX} ${targetY}`;
  const [path, baseLabelX, baseLabelY] =
    source === target
      ? selfLoopGeometry(sourceX, sourceY, targetX, targetY, sourcePosition)
      : labelShift !== 0
        ? [routedPath, middleX, middleY]
        : getSmoothStepPath({
            sourceX,
            sourceY,
            sourcePosition,
            targetX,
            targetY,
            targetPosition,
            borderRadius: 14,
            offset: 0,
          });
  // Move each portaled label to the midpoint of its routed/stepped path.
  const labelX = baseLabelX + (horizontal ? 0 : labelShift);
  const labelY = baseLabelY + (horizontal ? labelShift : 0);
  const label = data?.label;
  const labelState = data?.pinned ? " is-pinned" : data?.lit ? " is-lit" : data?.dim ? " is-dim" : "";
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        className="flow-edge__path"
        markerEnd={markerEnd}
        data-source={source}
        data-target={target}
        style={{
          strokeDasharray: data?.kind === "result" ? "8 4" : data?.kind === "error" ? "2 5" : undefined,
        }}
      />
      {label ? (
        <EdgeLabelRenderer>
          <div
            className={`flow-edge__label flow-edge__label--${data?.kind ?? "task"}${labelState}`}
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
            aria-hidden="true"
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
  "edge.a11yDescription.default": "Directed edges show solid task, dashed result, and dotted error messages. Edges are read-only.",
};

function toFlow(spec: DiagramSpec): { nodes: FlowNode[]; edges: FlowEdge[] } {
  const pairKey = (a: string, b: string) => [a, b].sort().join("→");
  const pairSizes = new Map<string, number>();
  const pairOccurrences = new Map<string, number>();
  const sourceCounts = new Map<string, number>();
  const targetCounts = new Map<string, number>();
  for (const edge of spec.edges) {
    const key = pairKey(edge.source, edge.target);
    pairSizes.set(key, (pairSizes.get(key) ?? 0) + 1);
    sourceCounts.set(edge.source, (sourceCounts.get(edge.source) ?? 0) + 1);
    targetCounts.set(edge.target, (targetCounts.get(edge.target) ?? 0) + 1);
  }
  const sourceOccurrences = new Map<string, number>();
  const targetOccurrences = new Map<string, number>();
  const labels = new Map(spec.nodes.map((node) => [node.id, node.label]));
  return {
    nodes: spec.nodes.map((node) => ({
      id: node.id,
      type: "diagram",
      position: { x: 0, y: 0 },
      data: {
        label: node.label,
        kind: node.kind,
        facts: node.facts,
        sourceHandleCount: sourceCounts.get(node.id) ?? 0,
        targetHandleCount: targetCounts.get(node.id) ?? 0,
      },
      style: { width: node.kind === "gate" ? 236 : NODE_WIDTH },
      ariaRole: node.facts.length > 0 ? "button" : "group",
      ariaLabel: `${node.kind} ${node.label}`,
      focusable: node.facts.length > 0,
      selectable: node.facts.length > 0,
      deletable: false,
    })),
    edges: spec.edges.map((edge) => {
      const key = pairKey(edge.source, edge.target);
      const occurrence = pairOccurrences.get(key) ?? 0;
      pairOccurrences.set(key, occurrence + 1);
      const sourceIndex = sourceOccurrences.get(edge.source) ?? 0;
      sourceOccurrences.set(edge.source, sourceIndex + 1);
      const targetIndex = targetOccurrences.get(edge.target) ?? 0;
      targetOccurrences.set(edge.target, targetIndex + 1);
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: `source-${sourceIndex}`,
        targetHandle: `target-${targetIndex}`,
        type: "diagram",
        data: {
          kind: edge.kind,
          label: edge.label,
          offset: parallelEdgeOffset(edge, occurrence, pairSizes.get(key) ?? 1),
          lit: false,
          dim: false,
          pinned: false,
        },
        className: `flow-edge flow-edge--${edge.kind}`,
        style: {
          strokeDasharray: edge.kind === "result" ? "8 4" : edge.kind === "error" ? "2 5" : undefined,
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLORS[edge.kind], width: 22, height: 22 },
        ariaLabel: `${edge.kind} edge${edge.label ? ` “${edge.label}”` : ""}: ${labels.get(edge.source)} to ${labels.get(edge.target)}`,
        focusable: false,
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

const MIN_CANVAS_HEIGHT = 240;
const MAX_CANVAS_HEIGHT = 560;
const MIN_ZOOM = 0.05;
const INITIAL_ZOOM = 1;
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
  const viewportAdjustedRef = useRef(false);
  // The inspector follows the nodes' own selection flag — one source of
  // truth, so closing it cannot disagree with the canvas selection ring.
  const selectedNode = nodes.find((node) => node.selected) ?? null;
  const { fitBounds, getNodesBounds, setViewport } = useReactFlow<FlowNode, FlowEdge>();
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
          data: {
            kind: edge.data?.kind ?? "task",
            label: edge.data?.label,
            offset: edge.data?.offset ?? 0,
            lit,
            dim: connected !== null && !lit,
            pinned,
          },
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
    // Position once, after nodes and portaled labels can be bounded.
    const raf = requestAnimationFrame(() => {
      const canvas = canvasRef.current;
      if (cancelled || !canvas || canvas.clientWidth === 0 || canvas.clientHeight === 0) return;

      const bounds = getFlowBounds(nodes, spec, edges, getNodesBounds(nodes));
      // Every diagram opens at 100% for readable labels. Users can pan, focus
      // a node, or explicitly choose the fit control for a scaled overview.
      const firstViewport = getViewportForBounds(
        bounds,
        canvas.clientWidth,
        canvas.clientHeight,
        INITIAL_ZOOM,
        INITIAL_ZOOM,
        FIT_PADDING,
      );
      const nextHeight = autoCanvasHeight(bounds.height, firstViewport.zoom, spec);
      const viewport = getViewportForBounds(
        bounds,
        canvas.clientWidth,
        nextHeight,
        INITIAL_ZOOM,
        INITIAL_ZOOM,
        FIT_PADDING,
      );
      setCanvasHeight(nextHeight);
      void setViewport(viewport, { duration: 0 });
      setReady(true);
    });
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
  }, [edges, getNodesBounds, laidOut, nodes, ready, setViewport, spec]);

  useEffect(() => {
    if (!ready) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    let previousWidth = Math.round(canvas.clientWidth);
    let resizeFrame = 0;
    const onResize = () => {
      const width = Math.round(canvas.clientWidth);
      if (!width || width === previousWidth) return;
      previousWidth = width;
      // Listen to the window, not the resized canvas: writing canvas height
      // inside a ResizeObserver can trigger WebKit's loop-detection error.
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => {
        // Preserve both frame and viewport after deliberate interaction. This
        // also avoids resize feedback while the reader is exploring a detail.
        if (viewportAdjustedRef.current) return;
        const bounds = getFlowBounds(nodes, spec, edges, getNodesBounds(nodes));
        const firstViewport = getViewportForBounds(
          bounds,
          width,
          canvas.clientHeight,
          INITIAL_ZOOM,
          INITIAL_ZOOM,
          FIT_PADDING,
        );
        const nextHeight = autoCanvasHeight(bounds.height, firstViewport.zoom, spec);
        setCanvasHeight(nextHeight);
        void setViewport(
          getViewportForBounds(bounds, width, nextHeight, INITIAL_ZOOM, INITIAL_ZOOM, FIT_PADDING),
          { duration: 0 },
        );
      });
    };
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(resizeFrame);
      window.removeEventListener("resize", onResize);
    };
  }, [edges, getNodesBounds, nodes, ready, setViewport, spec]);

  return (
    <section className="flow-diagram" aria-label={spec.title}>
      <div className="flow-diagram__heading">
        <span className="flow-diagram__title">{spec.title}</span>
        <span className="flow-diagram__zoom-hint" id={instructionsId}>
          Pinch or use controls to zoom · drag to pan · Fit for overview
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
            onKeyDown={(event) => {
              if (event.key === "Escape") clearSelection();
            }}
            onNodeClick={(_, node) => {
              if (node.data.facts.length === 0) return;
              setNodes((current) =>
                current.map((n) => ({ ...n, selected: n.id === node.id })),
              );
            }}
            onNodeMouseEnter={(_, node) => setHoveredId(node.id)}
            onNodeMouseLeave={() => setHoveredId(null)}
            onEdgeClick={(_, edge) =>
              setPinnedEdgeId((current) => (current === edge.id ? null : edge.id))
            }
            onPaneClick={clearSelection}
            onMoveStart={(event) => {
              if (event) viewportAdjustedRef.current = true;
            }}
            nodesDraggable={false}
            nodesConnectable={false}
            nodesFocusable={false}
            autoPanOnNodeFocus
            edgesFocusable={false}
            edgesReconnectable={false}
            elementsSelectable
            deleteKeyCode={null}
            selectionOnDrag={false}
            panOnDrag
            zoomOnScroll={false}
            zoomOnPinch
            preventScrolling={false}
            minZoom={MIN_ZOOM}
            maxZoom={1.75}
            onlyRenderVisibleElements={false}
            aria-label={`${spec.title} interactive diagram`}
            aria-describedby={instructionsId}
            ariaLabelConfig={ARIA_LABEL_CONFIG}
          >
            <Controls
              position="bottom-right"
              showInteractive={false}
              onZoomIn={() => {
                viewportAdjustedRef.current = true;
              }}
              onZoomOut={() => {
                viewportAdjustedRef.current = true;
              }}
              onFitView={() => {
                viewportAdjustedRef.current = true;
                void fitBounds(getFlowBounds(nodes, spec, edges, getNodesBounds(nodes)), {
                  padding: FIT_PADDING,
                  duration: 0,
                });
              }}
            />
          </ReactFlow>
        </div>
        {selectedNode && selectedNode.data.facts.length > 0 && (
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
        <span className="flow-legend--task">— task (solid)</span>
        <span className="flow-legend--result">┄ result (dashed)</span>
        <span className="flow-legend--error">⋯ error / repair (dotted)</span>
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
