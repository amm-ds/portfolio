import { useEffect, useRef, useState } from "react";
import type PlotlyStatic from "plotly.js-dist-min";
import { FigureFrame } from "./FigureFrame";

interface PlotlyPayload {
  data: unknown[];
  layout: Record<string, unknown>;
}

const MIN_HEIGHT = 320;
const MAX_HEIGHT = 900;
const DEFAULT_HEIGHT = 560;

function clampHeight(height: unknown): number {
  const h = typeof height === "number" && Number.isFinite(height) ? height : DEFAULT_HEIGHT;
  return Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, h));
}

/**
 * Native plotly rendering of a figure JSON payload: full-size (no internal
 * scrolling), re-skinned to the site theme (transparent backgrounds), with
 * automatic fallback to the HTML iframe (FigureFrame) when the JSON payload
 * is unavailable (404).
 */
export function PlotlyFigure({
  pid,
  name,
  caption,
}: {
  pid: string;
  name: string;
  caption?: string;
}) {
  const [payload, setPayload] = useState<PlotlyPayload | null>(null);
  const [failed, setFailed] = useState(false);
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

  useEffect(() => {
    if (!payload || !elRef.current) return;
    // Capture the element now: refs are detached before passive effect cleanups run.
    const el = elRef.current;
    let disposed = false;
    (async () => {
      const Plotly = (await import("plotly.js-dist-min")).default;
      if (disposed) return;
      plotlyRef.current = Plotly;
      const layout: Record<string, unknown> = {
        ...payload.layout,
        autosize: true,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
      };
      layout.height = clampHeight(payload.layout.height);
      delete layout.width; // full-width responsive
      await Plotly.react(el, payload.data, layout, {
        responsive: true,
        displayModeBar: false,
      });
    })();
    return () => {
      disposed = true;
      // Plotly may still be loading; purge only when it rendered into `el`.
      plotlyRef.current?.purge(el);
    };
  }, [payload]);

  if (failed) {
    return <FigureFrame projectId={pid} name={name} caption={caption} />;
  }

  return (
    <figure className="figure-frame">
      <div className="plotly-wrap">
        {!payload && (
          <div className="frame-skeleton" aria-hidden="true">
            <span>loading…</span>
          </div>
        )}
        <div ref={elRef} className="plotly-host" data-testid={`plotly-${name}`} />
      </div>
      {caption && <figcaption className="figure-caption">{caption}</figcaption>}
    </figure>
  );
}
