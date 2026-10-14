import { useEffect, useRef, useState } from "react";
import type PlotlyStatic from "plotly.js-dist-min";
import { FigureFrame } from "./FigureFrame";

interface PlotlyPayload {
  data: unknown[];
  layout: Record<string, unknown>;
}

const DEFAULT_HEIGHT = 560;
const MIN_SCALED_HEIGHT = 360;
const MAX_SCALED_HEIGHT = 1100;
const TEXT_COLOR = "#e2e8f0";
const AXIS_LINE_COLOR = "rgba(148,163,184,0.3)";
const GRID_COLOR = "rgba(148,163,184,0.15)";
const TRANSPARENT = "rgba(0,0,0,0)";
const RESIZE_DEBOUNCE_MS = 150;

/** Scale the authored layout height to the measured container width (1000px design width). */
export function scaledHeight(layoutHeight: unknown, containerWidth: number): number {
  const h =
    typeof layoutHeight === "number" && Number.isFinite(layoutHeight)
      ? layoutHeight
      : DEFAULT_HEIGHT;
  const scaled = (h * containerWidth) / 1000;
  return Math.min(MAX_SCALED_HEIGHT, Math.max(MIN_SCALED_HEIGHT, scaled));
}

type AnyRecord = Record<string, unknown>;

function asRecord(v: unknown): AnyRecord {
  return typeof v === "object" && v !== null ? (v as AnyRecord) : {};
}

/** Axis defaults for the dark theme; every payload value wins over its default. */
function axisLayout(rawAxis: unknown): AnyRecord {
  const ax = asRecord(rawAxis);
  const { tickfont, title, linecolor, zerolinecolor, gridcolor, ...rest } = ax;
  const t = asRecord(title);
  const { font: titleFont, ...titleRest } = t;
  return {
    ...rest,
    tickfont: { color: TEXT_COLOR, ...asRecord(tickfont) },
    title: { ...titleRest, font: { color: TEXT_COLOR, ...asRecord(titleFont) } },
    linecolor: linecolor ?? AXIS_LINE_COLOR,
    zerolinecolor: zerolinecolor ?? AXIS_LINE_COLOR,
    gridcolor: gridcolor ?? GRID_COLOR,
  };
}

/**
 * Re-skin a plotly layout for the site theme: transparent backgrounds, light
 * text/axis defaults, height scaled to the container. The raw layout is never
 * mutated and any payload value overrides its default.
 */
export function buildLayout(raw: AnyRecord, containerWidth: number): AnyRecord {
  const { font, legend, xaxis, yaxis, width: _width, height, ...rest } = raw;
  const rawFont = asRecord(font);
  const rawLegend = asRecord(legend);
  const { font: legendFont, bgcolor, ...legendRest } = rawLegend;
  return {
    ...rest,
    autosize: true,
    paper_bgcolor: TRANSPARENT,
    plot_bgcolor: TRANSPARENT,
    height: scaledHeight(height, containerWidth),
    font: { color: TEXT_COLOR, ...rawFont },
    legend: {
      ...legendRest,
      bgcolor: bgcolor ?? TRANSPARENT,
      font: { color: TEXT_COLOR, ...asRecord(legendFont) },
    },
    xaxis: axisLayout(xaxis),
    yaxis: axisLayout(yaxis),
  };
}

/**
 * Native plotly rendering of a figure JSON payload: full container width,
 * height scaled from the authored layout, re-skinned to the dark theme, with
 * automatic fallback to the HTML iframe (FigureFrame) when the JSON payload
 * is unavailable (404).
 */
export function PlotlyFigure({
  pid,
  name,
  caption,
  sectionId,
}: {
  pid: string;
  name: string;
  caption?: string;
  /** Story section id; when given, the caption links back to `#sec-{sectionId}`. */
  sectionId?: string;
}) {
  const [payload, setPayload] = useState<PlotlyPayload | null>(null);
  const [failed, setFailed] = useState(false);
  const [inView, setInView] = useState(false);
  const elRef = useRef<HTMLDivElement>(null);
  const plotlyRef = useRef<typeof PlotlyStatic | null>(null);

  useEffect(() => {
    let cancelled = false;
    setPayload(null);
    setFailed(false);
    fetch(`/projects/${pid}/figures/${name}.json`)
      .then((res) => {
        if (res.status === 404) return null;
        if (!res.ok) throw new Error(`figure JSON ${res.status}`);
        return res.json() as Promise<PlotlyPayload>;
      })
      .then((p: PlotlyPayload | null) => {
        if (cancelled) return;
        if (p && Array.isArray(p.data) && p.layout) setPayload(p);
        else setFailed(true);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [pid, name]);

  // Gate the (heavy) plotly chunk on viewport proximity; load immediately
  // when IntersectionObserver is unavailable.
  useEffect(() => {
    if (failed) return;
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
  }, [failed]);

  useEffect(() => {
    if (!payload || !inView || !elRef.current) return;
    // Capture the element now: refs are detached before passive effect cleanups run.
    const el = elRef.current;
    let disposed = false;
    let resizeTimer = 0;

    const render = async () => {
      try {
        plotlyRef.current =
          plotlyRef.current ?? (await import("plotly.js-dist-min")).default;
      } catch {
        return;
      }
      if (disposed) return;
      await plotlyRef.current.react(
        el,
        payload.data,
        buildLayout(payload.layout, el.clientWidth),
        { responsive: true, displayModeBar: false },
      );
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
      // Plotly may still be loading; purge only once it rendered into `el`.
      plotlyRef.current?.purge(el);
    };
  }, [payload, inView]);

  if (failed) {
    return <FigureFrame projectId={pid} name={name} caption={caption} />;
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
        {(!payload || !inView) && (
          <div className="frame-skeleton" aria-hidden="true">
            <span>loading…</span>
          </div>
        )}
        <div ref={elRef} className="plotly-host" data-testid={`plotly-${name}`} />
      </div>
      {captionEl}
    </figure>
  );
}
