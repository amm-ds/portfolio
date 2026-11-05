import { Component, Suspense, lazy, type ReactNode } from "react";
import type { DiagramSpec } from "../../diagrams/types";
import { DiagramFallback } from "./DiagramFallback";

export interface FlowDiagramProps {
  spec: DiagramSpec;
}

export interface FlowDiagramRegistryProps {
  specId: string;
}

function UnavailableFlowDiagram({ specId }: FlowDiagramRegistryProps) {
  return <DiagramFallback specId={specId} />;
}

// A failed dynamic-import fetch resolves to the same source fallback as a
// renderer failure; the specs and renderer stay out of the entry bundle.
const FlowDiagram = lazy(() =>
  import("./FlowDiagram")
    .then((module) => ({ default: module.FlowDiagramFromRegistry }))
    .catch(() => ({ default: UnavailableFlowDiagram })),
);

class FlowDiagramBoundary extends Component<{ children: ReactNode; specId: string }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? <DiagramFallback specId={this.props.specId} /> : this.props.children;
  }
}

export function DiagramSkeleton() {
  return (
    <div className="flow-diagram flow-diagram--loading">
      <div className="frame-skeleton" aria-hidden="true">
        <span>rendering diagram…</span>
      </div>
    </div>
  );
}

export function LazyFlowDiagram({ specId }: { specId: string }) {
  return (
    <FlowDiagramBoundary key={specId} specId={specId}>
      <Suspense fallback={<DiagramSkeleton />}>
        <FlowDiagram specId={specId} />
      </Suspense>
    </FlowDiagramBoundary>
  );
}
