import { Component, Suspense, lazy, useEffect, useRef, useState, type ReactNode } from "react";
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
  // The chunk is ~337 kB (react-flow + dagre): start loading it only when the
  // diagram scrolls near the viewport instead of on story render — on detail
  // pages the architecture diagram sits below the fold (audit: 1.29 s of
  // main-thread script eval on mobile attributed to this chunk).
  const ref = useRef<HTMLDivElement | null>(null);
  const [nearViewport, setNearViewport] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || nearViewport) return;
    if (typeof IntersectionObserver === "undefined") {
      setNearViewport(true); // jsdom / very old engines: render immediately
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setNearViewport(true);
          io.disconnect();
        }
      },
      { rootMargin: "800px" }, // warm the import shortly before it is visible
    );
    io.observe(el);
    return () => io.disconnect();
  }, [nearViewport]);

  return (
    <div ref={ref}>
      <FlowDiagramBoundary key={specId} specId={specId}>
        {nearViewport ? (
          <Suspense fallback={<DiagramSkeleton />}>
            <FlowDiagram specId={specId} />
          </Suspense>
        ) : (
          <DiagramSkeleton />
        )}
      </FlowDiagramBoundary>
    </div>
  );
}
