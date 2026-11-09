import { useEffect, useRef, useState } from "react";
import {
  plotlyToECharts,
  supportsECharts,
  type EChartsOption,
} from "../lib/plotlyToECharts";
import { useTheme } from "../theme/useTheme";
import { PlotlyFigure, scaledHeight, type PlotlyPayload } from "./PlotlyFigure";

const RESIZE_DEBOUNCE_MS = 150;

/**
 * Registered once the echarts chunk has loaded. The module imports are all
 * dynamic so the whole renderer stays out of the main bundle; registration
 * is memoized on the shared promise.
 */
let echartsLoader: Promise<{
  init: (el: HTMLElement, theme?: unknown, opts?: { renderer?: string; height?: number }) => EChartsInstance;
}> | null = null;

interface EChartsInstance {
  setOption(option: unknown, opts?: { notMerge?: boolean }): void;
  resize(): void;
  dispose(): void;
}

function loadECharts() {
  echartsLoader ??= Promise.all([
    import("echarts/core"),
    import("echarts/charts"),
    import("echarts/components"),
    import("echarts/renderers"),
  ]).then(([echarts, charts, components, renderers]) => {
    echarts.use([
      charts.LineChart,
      charts.BarChart,
      charts.ScatterChart,
      charts.HeatmapChart,
      charts.CustomChart,
      components.GridComponent,
      components.TooltipComponent,
      components.LegendComponent,
      components.VisualMapComponent,
      components.TitleComponent,
      components.MarkLineComponent,
      renderers.SVGRenderer,
    ]);
    return { init: echarts.init as never };
  });
  return echartsLoader;
}

/**
 * ECharts pilot renderer: same contract as PlotlyFigure (viewport-gated JSON
 * fetch, themed chrome, labeled skeleton, iframe-grade failure handling) but
 * draws the committed figure with Apache ECharts on the SVG renderer.
 * Payloads outside the pilot subset (see supportsECharts) and any
 * import/conversion/render failure fall back to the plotly renderer, so the
 * pilot can never break a page.
 */
export function EChartsFigure({
  pid,
  name,
  caption,
  sectionId,
  onPayload,
}: {
  pid: string;
  name: string;
  caption?: string;
  /** Story section id; when given, the caption links back to `#sec-{sectionId}`. */
  sectionId?: string;
  /** Notified with the parsed figure JSON (null when unavailable) so hosts
   * can offer a non-visual fallback such as a data table. */
  onPayload?: (payload: PlotlyPayload | null) => void;
}) {
  const [payload, setPayload] = useState<PlotlyPayload | null>(null);
  const [fallback, setFallback] = useState(false);
  const [inView, setInView] = useState(false);
  const { theme } = useTheme();
  /** ECharts has painted into the host — the skeleton can retire. */
  const [rendered, setRendered] = useState(false);
  const elRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EChartsInstance | null>(null);
  // Latest-ref pattern: the fetch effect runs per (pid, name, inView), never
  // per callback identity, so an inline host callback cannot trigger refetches.
  const onPayloadRef = useRef(onPayload);
  onPayloadRef.current = onPayload;

  // Figure data and the echarts chunk share the same viewport gate.
  useEffect(() => {
    let cancelled = false;
    setPayload(null);
    setFallback(false);
    setRendered(false);
    if (!inView) return;
    fetch(`/projects/${pid}/figures/${name}.json`)
      .then((res) => {
        if (res.status === 404) return null;
        if (!res.ok) throw new Error(`figure JSON ${res.status}`);
        return res.json() as Promise<PlotlyPayload>;
      })
      .then((p: PlotlyPayload | null) => {
        if (cancelled) return;
        if (p && Array.isArray(p.data) && p.layout && supportsECharts(p)) {
          setPayload(p);
          onPayloadRef.current?.(p);
        } else if (p && Array.isArray(p.data) && p.layout) {
          // parseable but outside the pilot subset → plotly renderer
          setFallback(true);
        } else {
          setFallback(true);
          onPayloadRef.current?.(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFallback(true);
          onPayloadRef.current?.(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [pid, name, inView]);

  // Gate the (heavy) echarts chunk on viewport proximity; load immediately
  // when IntersectionObserver is unavailable.
  useEffect(() => {
    if (fallback) return;
    if (typeof IntersectionObserver === "undefined" || !elRef.current) {
      setInView(true);
      return;
    }
    const el = elRef.current;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setInView(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [fallback]);

  useEffect(() => {
    if (!payload || !inView || !elRef.current) return;
    // Capture the element now: refs are detached before passive effect cleanups run.
    const el = elRef.current;
    let disposed = false;
    let resizeTimer = 0;

    const render = async () => {
      try {
        const { init } = await loadECharts();
        if (disposed) return;
        const height = scaledHeight(payload.layout.height, el.clientWidth);
        el.style.height = `${height}px`;
        chartRef.current ??= init(el, undefined, { renderer: "svg", height });
        const option: EChartsOption = plotlyToECharts(payload, theme, el.clientWidth);
        chartRef.current.setOption(option as never, { notMerge: true });
        // The chart is painted — swap the skeleton out (only if still mounted:
        // a resize re-render may finish after unmount).
        if (!disposed) setRendered(true);
      } catch {
        // Import, conversion and renderer failures use the plotly fallback.
        if (!disposed) setFallback(true);
      }
    };
    void render();

    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(() => {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(() => void render(), RESIZE_DEBOUNCE_MS);
      });
      observer.observe(el);
    }
    return () => {
      disposed = true;
      window.clearTimeout(resizeTimer);
      observer?.disconnect();
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, [payload, inView, theme]);

  if (fallback) {
    return <PlotlyFigure pid={pid} name={name} caption={caption} sectionId={sectionId} onPayload={onPayload} />;
  }

  const captionEl = caption ? (
    sectionId ? (
      <a href={`#sec-${sectionId}`} className="figure-caption">
        {caption}
      </a>
    ) : (
      <figcaption className="figure-caption">{caption}</figcaption>
    )
  ) : null;

  return (
    <figure className="figure-frame">
      <div className="plotly-wrap">
        {!rendered && (
          <div className="frame-skeleton" aria-hidden="true" data-testid="figure-skeleton">
            <span className="frame-label">&gt; {name}</span>
            <span className="frame-skeleton-status">rendering figure…</span>
          </div>
        )}
        <div ref={elRef} className="plotly-host echarts-host" data-testid={`echarts-${name}`} />
      </div>
      {captionEl}
    </figure>
  );
}
