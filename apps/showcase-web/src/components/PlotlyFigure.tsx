import { useEffect, useRef, useState } from "react";
import type PlotlyStatic from "plotly.js-dist-min";
import { asRecord } from "../lib/records";
import { useTheme, type Theme } from "../theme/useTheme";
import { LIGHT_TRACE_COLOR_MAP } from "../theme/plotlyTraceColors";
import { FigureFrame } from "./FigureFrame";

export interface PlotlyPayload {
  data: unknown[];
  layout: Record<string, unknown>;
}

const DEFAULT_HEIGHT = 560;
const MIN_SCALED_HEIGHT = 360;
const MAX_SCALED_HEIGHT = 1100;
const TRANSPARENT = "rgba(0,0,0,0)";
const RESIZE_DEBOUNCE_MS = 150;

export interface PlotlyThemePalette {
  textColor: string;
  axisLineColor: string;
  gridColor: string;
  /** Authored dark-palette trace hex → light-surface equivalent. Empty in
   * dark (figures are authored for the dark surface, so nothing to remap).
   * Keys are lowercase; lookup lowercases the payload color, so authored
   * case variants match too. Exact-string matches only — anything the table
   * doesn't know (plotly defaults, rgba() washes) stays as authored. */
  traceColorMap: Record<string, string>;
}

export const PLOTLY_THEME_PALETTES: Record<Theme, PlotlyThemePalette> = {
  dark: {
    textColor: "#e2e8f0",
    axisLineColor: "rgba(148,163,184,0.3)",
    gridColor: "rgba(148,163,184,0.15)",
    traceColorMap: {},
  },
  light: {
    textColor: "#172433",
    axisLineColor: "rgba(78,98,118,0.48)",
    gridColor: "rgba(78,98,118,0.22)",
    traceColorMap: LIGHT_TRACE_COLOR_MAP,
  },
};

/** Scale the authored layout height to the measured container width (1000px design width). */
export function scaledHeight(layoutHeight: unknown, containerWidth: number): number {
  const h =
    typeof layoutHeight === "number" && Number.isFinite(layoutHeight)
      ? layoutHeight
      : DEFAULT_HEIGHT;
  const scaled = (h * containerWidth) / 1000;
  return Math.min(MAX_SCALED_HEIGHT, Math.max(MIN_SCALED_HEIGHT, scaled));
}

/** Chrome color precedence across themes. Committed figures bake dark-surface
 * chrome (near-white tick labels, dark grid) at both layout and template
 * level. Dark mode preserves that authored look — payload wins. Light mode
 * forces the readable palette color, keeping the payload's non-color props
 * (size, family). */
function chromeColor(payloadColor: unknown, paletteColor: string, theme: Theme): unknown {
  if (theme === "light") return paletteColor;
  return payloadColor ?? paletteColor;
}

/** Axis defaults for the requested theme; dark keeps the authored payload,
 * light forces the readable palette (see chromeColor). */
function axisLayout(
  rawAxis: unknown,
  palette: PlotlyThemePalette,
  theme: Theme,
): Record<string, unknown> {
  const ax = asRecord(rawAxis);
  const { tickfont, title, linecolor, zerolinecolor, gridcolor, ...rest } = ax;
  const t = asRecord(title);
  const { font: titleFont, ...titleRest } = t;
  const rawTick = asRecord(tickfont);
  const rawTitleFont = asRecord(titleFont);
  return {
    ...rest,
    tickfont: { ...rawTick, color: chromeColor(rawTick.color, palette.textColor, theme) },
    title: {
      ...titleRest,
      font: { ...rawTitleFont, color: chromeColor(rawTitleFont.color, palette.textColor, theme) },
    },
    linecolor: chromeColor(linecolor, palette.axisLineColor, theme),
    zerolinecolor: chromeColor(zerolinecolor, palette.axisLineColor, theme),
    gridcolor: chromeColor(gridcolor, palette.gridColor, theme),
  };
}

/** Remap a template's colorway for the light surface. Most committed figures
 * leave trace colors implicit and carry the palette as template.layout.colorway
 * (some exporters nest it directly on the template); without this those traces
 * keep the dark palette in light mode. Dark (empty map) and colorway-less
 * templates return unchanged. */
function reskinTemplate(
  template: unknown,
  traceColorMap: Record<string, string>,
): unknown {
  if (Object.keys(traceColorMap).length === 0) return template;
  const tpl = asRecord(template);
  const nested = asRecord(tpl.layout);
  if (Array.isArray(nested.colorway)) {
    return {
      ...tpl,
      layout: { ...nested, colorway: remapColorList(nested.colorway, traceColorMap) },
    };
  }
  if (Array.isArray(tpl.colorway)) {
    return { ...tpl, colorway: remapColorList(tpl.colorway, traceColorMap) };
  }
  return template;
}

function remapColorList(colors: unknown[], map: Record<string, string>): unknown[] {
  return colors.map((color) =>
    typeof color === "string" ? (map[color.toLowerCase()] ?? color) : color,
  );
}

/** Title chrome: light forces the readable text color — including inline
 * `color:#…` spans authored into the title text for the dark surface — and
 * dark passes the authored title through (payload font color wins today). */
const INLINE_TEXT_COLOR_RE = /color\s*:\s*'?#[0-9a-fA-F]{3,8}'?/gi;

function titleLayout(
  rawTitle: unknown,
  palette: PlotlyThemePalette,
  theme: Theme,
): Record<string, unknown> {
  const t = asRecord(rawTitle);
  const { font: titleFont, text, ...rest } = t;
  const rawTitleFont = asRecord(titleFont);
  const forcedText =
    theme === "light" && typeof text === "string"
      ? text.replace(INLINE_TEXT_COLOR_RE, "color:#475569")
      : text;
  return {
    ...rest,
    ...(text !== undefined ? { text: forcedText } : {}),
    font: { ...rawTitleFont, color: chromeColor(rawTitleFont.color, palette.textColor, theme) },
  };
}

const AXIS_KEY_RE = /^[xy]axis\d*$/;

/**
 * Re-skin a plotly layout for the site theme: transparent backgrounds, readable
 * text/axis defaults, height scaled to the container. The raw layout is never
 * mutated. Dark mode preserves the authored chrome (payload wins); light mode
 * forces the readable palette over the dark-authored chrome (see chromeColor).
 */
export function buildLayout(
  raw: Record<string, unknown>,
  containerWidth: number,
  theme: Theme = "dark",
): Record<string, unknown> {
  const palette = PLOTLY_THEME_PALETTES[theme];
  const { font, legend, xaxis, yaxis, template, width: _width, height, ...rest } = raw;
  // Light mode also themes the subplot axes (xaxis2…, yaxis2…) and the title,
  // which carry the same baked dark chrome; dark passes everything else
  // through untouched to preserve the authored look.
  if (theme === "light") {
    for (const key of Object.keys(rest)) {
      if (AXIS_KEY_RE.test(key)) {
        rest[key] = axisLayout(rest[key], palette, theme);
      } else if (key === "title") {
        rest[key] = titleLayout(rest[key], palette, theme);
      }
    }
  }
  const rawFont = asRecord(font);
  const rawLegend = asRecord(legend);
  const { font: legendFont, ...legendRest } = rawLegend;
  const rawLegendFont = asRecord(legendFont);
  const legendBg = chromeColor(rawLegend.bgcolor, TRANSPARENT, theme);
  return {
    ...rest,
    autosize: true,
    paper_bgcolor: TRANSPARENT,
    plot_bgcolor: TRANSPARENT,
    height: scaledHeight(height, containerWidth),
    font: { ...rawFont, color: chromeColor(rawFont.color, palette.textColor, theme) },
    legend: {
      ...legendRest,
      bgcolor: legendBg,
      font: { ...rawLegendFont, color: chromeColor(rawLegendFont.color, palette.textColor, theme) },
    },
    xaxis: axisLayout(xaxis, palette, theme),
    yaxis: axisLayout(yaxis, palette, theme),
    template: reskinTemplate(template, palette.traceColorMap),
  };
}

/** Remap one authored trace color for the light surface: string colors match
 * the table exactly (case-insensitively), color arrays remap entry by entry,
 * and anything the table doesn't know passes through untouched. */
function reskinTraceColor(color: unknown, map: Record<string, string>): unknown {
  if (typeof color === "string") return map[color.toLowerCase()] ?? color;
  if (Array.isArray(color)) return color.map((entry) => reskinTraceColor(entry, map));
  return color;
}

/** Copy one trace with its authored colors remapped. The input trace is never
 * mutated; untouched fields (data arrays, other styling) keep their original
 * references — only the color-bearing containers are copied. */
function reskinTrace(trace: unknown, map: Record<string, string>): unknown {
  if (typeof trace !== "object" || trace === null) return trace;
  const t = trace as Record<string, unknown>;
  const out: Record<string, unknown> = { ...t };
  if (typeof t.line === "object" && t.line !== null && "color" in t.line) {
    out.line = { ...t.line, color: reskinTraceColor(t.line.color, map) };
  }
  if (typeof t.marker === "object" && t.marker !== null) {
    const marker = t.marker as Record<string, unknown>;
    const m: Record<string, unknown> = { ...marker };
    if ("color" in marker) m.color = reskinTraceColor(marker.color, map);
    if ("colors" in marker) m.colors = reskinTraceColor(marker.colors, map);
    out.marker = m;
  }
  if ("fillcolor" in t) out.fillcolor = reskinTraceColor(t.fillcolor, map);
  return out;
}

/**
 * Re-skin figure trace colors for the site theme: figures are authored with
 * the dark palette, whose accents wash out on the light surface. Only colors
 * in the theme's table are remapped and the payload is never mutated — dark
 * returns the input unchanged (identity).
 */
export function reskinTraces(data: unknown[], theme: Theme): unknown[] {
  const map = PLOTLY_THEME_PALETTES[theme].traceColorMap;
  if (Object.keys(map).length === 0) return data;
  return data.map((trace) => reskinTrace(trace, map));
}

/**
 * Native plotly rendering of a figure JSON payload: full container width,
 * height scaled from the authored layout, re-skinned to the active theme
 * (chrome always, trace colors on the light surface), with automatic
 * fallback to the HTML iframe (FigureFrame) when the JSON payload is
 * unavailable (404).
 */
export function PlotlyFigure({
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
  const [failed, setFailed] = useState(false);
  const [inView, setInView] = useState(false);
  const { theme } = useTheme();
  /** Plotly has painted into the host — the skeleton can retire. */
  const [rendered, setRendered] = useState(false);
  const elRef = useRef<HTMLDivElement>(null);
  const plotlyRef = useRef<typeof PlotlyStatic | null>(null);
  // Latest-ref pattern: the fetch effect runs per (pid, name, inView), never
  // per callback identity, so an inline host callback cannot trigger refetches.
  const onPayloadRef = useRef(onPayload);
  onPayloadRef.current = onPayload;

  // Figure data and the Plotly chunk share the same viewport gate.
  useEffect(() => {
    let cancelled = false;
    setPayload(null);
    setFailed(false);
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
        if (p && Array.isArray(p.data) && p.layout) {
          setPayload(p);
          onPayloadRef.current?.(p);
        } else {
          setFailed(true);
          onPayloadRef.current?.(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true);
          onPayloadRef.current?.(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [pid, name, inView]);

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
        if (disposed) return;
        await plotlyRef.current.react(
          el,
          reskinTraces(payload.data, theme),
          buildLayout(payload.layout, el.clientWidth, theme),
          { responsive: true, displayModeBar: false },
        );
        // The plot is painted — swap the skeleton out (only if still mounted:
        // a resize re-render may finish after unmount).
        if (!disposed) setRendered(true);
      } catch {
        // Import and renderer failures use the same HTML fallback as missing JSON.
        if (!disposed) {
          setFailed(true);
          onPayloadRef.current?.(null);
        }
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
      // Plotly may still be loading; purge only once it rendered into `el`.
      plotlyRef.current?.purge(el);
    };
  }, [payload, inView, theme]);

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
        {!rendered && (
          <div className="frame-skeleton" aria-hidden="true" data-testid="figure-skeleton">
            <span className="frame-label">&gt; {name}</span>
            <span className="frame-skeleton-status">rendering figure…</span>
          </div>
        )}
        <div ref={elRef} className="plotly-host" data-testid={`plotly-${name}`} />
      </div>
      {captionEl}
    </figure>
  );
}
