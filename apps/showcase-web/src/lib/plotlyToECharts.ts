import { asRecord } from "./records";
import type { Theme } from "../theme/useTheme";
import { LIGHT_TRACE_COLOR_MAP } from "../theme/plotlyTraceColors";
import {
  PLOTLY_THEME_PALETTES,
  scaledHeight,
  type PlotlyPayload,
} from "../components/PlotlyFigure";
import type { ComposeOption } from "echarts/core";
import type {
  BarSeriesOption,
  CustomSeriesOption,
  FunnelSeriesOption,
  HeatmapSeriesOption,
  LineSeriesOption,
  ScatterSeriesOption,
} from "echarts/charts";
import type {
  GridComponentOption,
  LegendComponentOption,
  MarkAreaComponentOption,
  TitleComponentOption,
  TooltipComponentOption,
  VisualMapComponentOption,
} from "echarts/components";

/**
 * Apache ECharts pilot: convert committed plotly figure payloads (the subset
 * the committed figures use — scatter/line, bar, histogram, heatmap, funnel
 * on linear/log or category axes, line/rect shapes, fill bands and text
 * annotations) into a ready-to-setOption ECharts option. Anything outside
 * that subset throws so the caller can render plotly instead
 * (see `supportsECharts`). The payload is never mutated.
 *
 * Theme chrome mirrors PlotlyFigure: figures are authored for the dark
 * surface, so dark keeps the authored colors and light remaps them through
 * the same LIGHT_TRACE_COLOR_MAP / palette tables.
 */
export type EChartsOption = ComposeOption<
  | BarSeriesOption
  | CustomSeriesOption
  | FunnelSeriesOption
  | HeatmapSeriesOption
  | LineSeriesOption
  | ScatterSeriesOption
  | GridComponentOption
  | LegendComponentOption
  | MarkAreaComponentOption
  | TitleComponentOption
  | TooltipComponentOption
  | VisualMapComponentOption
>;

const DESIGN_WIDTH = 1000;
const DEFAULT_MARGIN = { l: 80, r: 80, t: 100, b: 80 };
/** Tooltip card colors committed in every figure's hoverlabel block. */
const HOVER_BG = "#f8fafc";
const HOVER_BORDER = "#334155";
const HOVER_TEXT = "#0f172a";
/** Site mono stack — tick labels harmonize with the terminal chrome. */
const MONO_STACK = '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
/** Dark-surface subtitle color authored into every committed title. */
const SUBTEXT_COLOR_DARK = "#cbd5e1";
/** Light-mode equivalent, matching PlotlyFigure's inline-color rewrite. */
const SUBTEXT_COLOR_LIGHT = "#475569";
/** 5-point star for plotly `marker.symbol: "star"` optimum markers. */
const STAR_SYMBOL =
  "path://M0.5 0 L0.615 0.342 L0.976 0.346 L0.685 0.56 L0.794 0.905 L0.5 0.695 " +
  "L0.206 0.905 L0.315 0.56 L0.024 0.346 L0.385 0.342 Z";

const AXIS_KEY_RE = /^([xy])axis(\d*)$/;
const BR_RE = /<br\s*\/?\s*>/gi;
const TAG_RE = /<[^>]*>/g;
const INLINE_COLOR_RE = /color\s*:\s*#([0-9a-fA-F]{3,8})/;
const SCATTER_MODE_RE = /^(lines|markers|text)(\+(lines|markers|text))*$/;

const DASH_MAP: Record<string, string> = {
  dash: "dashed",
  dot: "dotted",
  // echarts lineStyle has no dash-dot; dashed is the closest match
  dashdot: "dashed",
};

const SYMBOL_MAP: Record<string, string> = {
  circle: "circle",
  square: "rect",
  diamond: "diamond",
  "triangle-up": "triangle",
  star: STAR_SYMBOL,
  x: "path://M0.22 0.22 L0.42 0.42 L0.5 0.34 L0.58 0.42 L0.78 0.22 L0.86 0.3 L0.66 0.5 " +
    "L0.86 0.7 L0.78 0.78 L0.58 0.58 L0.5 0.66 L0.42 0.58 L0.22 0.78 L0.14 0.7 L0.34 0.5 " +
    "L0.14 0.3 Z",
};

function fail(message: string): never {
  throw new Error(`plotlyToECharts: ${message}`);
}

/** Numbers or plotly's numeric strings (sizes/widths serialize loosely). */
function num(v: unknown): number | undefined {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) return Number(v);
  return undefined;
}

// ---------------------------------------------------------------------------
// Typed-array decoding: plotly serializes long numeric arrays as
// {dtype, bdata} (base64, little-endian). Widths plotly does not emit fail.
// ---------------------------------------------------------------------------

const BDATA_ARRAYS: Record<string, (buf: ArrayBuffer) => ArrayLike<number>> = {
  f8: (b) => new Float64Array(b),
  f4: (b) => new Float32Array(b),
  i4: (b) => new Int32Array(b),
  u4: (b) => new Uint32Array(b),
  i2: (b) => new Int16Array(b),
  u2: (b) => new Uint16Array(b),
  i1: (b) => new Int8Array(b),
  u1: (b) => new Uint8Array(b),
};

function decodeBdata(v: Record<string, unknown>): number[] {
  const make = BDATA_ARRAYS[String(v.dtype)];
  const bdata = v.bdata;
  if (!make || typeof bdata !== "string") fail(`unsupported bdata encoding ${String(v.dtype)}`);
  const bytes = Uint8Array.from(atob(bdata), (c) => c.charCodeAt(0));
  const buf = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buf).set(bytes);
  const arr = make(buf);
  return Array.from({ length: arr.length }, (_, i) => Number(arr[i]));
}

function toNumberArray(v: unknown, what: string): number[] {
  if (v === undefined || v === null) return [];
  if (Array.isArray(v)) {
    return v.map((e) => {
      // nulls mark missing bars/points: they become NaN and render as gaps
      if (e === null || e === undefined) return NaN;
      const n = num(e);
      if (n === undefined) fail(`${what} holds a non-numeric value`);
      return n;
    });
  }
  const rec = asRecord(v);
  if ("bdata" in rec) return decodeBdata(rec);
  fail(`${what} is not an array`);
}

const DATE_LIKE_RE = /^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$/;

/** plotly's `2014-02-26 13:45:00.000000` strings → epoch ms (undefined if not a date). */
function parsePlotlyDate(v: unknown): number | undefined {
  if (typeof v !== "string" || !DATE_LIKE_RE.test(v)) return undefined;
  const ms = Date.parse(v.replace(" ", "T"));
  return Number.isFinite(ms) ? ms : undefined;
}

function toValueArray(v: unknown, what: string): (number | string)[] {
  if (v === undefined || v === null) return [];
  if (Array.isArray(v)) return v as (number | string)[];
  const rec = asRecord(v);
  if ("bdata" in rec) return decodeBdata(rec);
  fail(`${what} is not an array`);
}

// ---------------------------------------------------------------------------
// Colors (same semantics as PlotlyFigure's reskinTraces / chromeColor)
// ---------------------------------------------------------------------------

function remapColor(color: string, theme: Theme): string {
  if (theme !== "light") return color;
  return LIGHT_TRACE_COLOR_MAP[color.toLowerCase()] ?? color;
}

/** Dark keeps the authored payload color, light forces the palette color. */
function chromeColor(payloadColor: unknown, paletteColor: string, theme: Theme): string {
  if (theme === "light") return paletteColor;
  return typeof payloadColor === "string" ? payloadColor : paletteColor;
}

function stripTags(text: string): string {
  return text.replace(TAG_RE, "").trim();
}

/** Greedy word-wrap at maxChars (long words pass through unsplit). */
function wrapText(text: string, maxChars: number): string {
  const lines: string[] = [];
  for (const rawLine of text.split("\n")) {
    let cur = "";
    for (const word of rawLine.split(/\s+/)) {
      if (!word) continue;
      if ((cur + " " + word).trim().length > maxChars) {
        if (cur) lines.push(cur.trim());
        cur = word;
      } else {
        cur = (cur + " " + word).trim();
      }
    }
    if (cur) lines.push(cur.trim());
  }
  return lines.join("\n");
}

/** Sample a plotly colorscale ([[pos, color], ...]) at fraction t ∈ [0,1]
 *  (nearest-up sampling — the committed scales have fine stops). */
function colorFromScale(scale: unknown[], t: number): string | undefined {
  if (scale.length === 0) return undefined;
  const clamped = Math.min(1, Math.max(0, t));
  for (let i = 1; i < scale.length; i++) {
    const cur = scale[i] as unknown[];
    if (clamped <= Number(cur[0]) || i === scale.length - 1) {
      return typeof cur[1] === "string" ? cur[1] : undefined;
    }
  }
  const first = scale[0] as unknown[];
  return typeof first[1] === "string" ? first[1] : undefined;
}

// ---------------------------------------------------------------------------
// Axis / grid bookkeeping
// ---------------------------------------------------------------------------

interface AxisInfo {
  key: string;
  index: number;
  isX: boolean;
  raw: Record<string, unknown>;
  /** Position of this axis inside the xAxis/yAxis option arrays. */
  arrayIndex: number;
  /** Position of the grid this axis belongs to inside the grid array. */
  gridIndex: number;
  type: "value" | "category" | "log" | "time";
  categories: string[];
  built: Record<string, unknown> | null;
}

interface GridInfo {
  xIndex: number;
  yIndex: number;
  xDomain: number[];
  yDomain: number[];
  left: number;
  top: number;
  width: number;
  height: number;
}

/** "x2" → 1, "x" → 0, absent → 0 ("x domain" strips its suffix first). */
function axisRefIndex(v: unknown, axis: "x" | "y"): number {
  if (v === undefined || v === null) return 0;
  if (typeof v !== "string") fail(`unsupported ${axis}axis ref`);
  const m = new RegExp(`^${axis}(\\d*)$`).exec(v.replace(/ domain$/, ""));
  if (!m) fail(`unsupported ${axis}axis ref "${v}"`);
  return m[1] === "" ? 0 : Number(m[1]) - 1;
}

function extentAdd(extent: { min: number; max: number } | null, v: number | undefined) {
  if (v === undefined || !Number.isFinite(v)) return extent;
  if (extent === null) return { min: v, max: v };
  extent.min = Math.min(extent.min, v);
  extent.max = Math.max(extent.max, v);
  return extent;
}

/**
 * Freedman–Diaconis bin width — the heuristic behind plotly's autobin.
 * Exact bin edges may differ slightly from plotly's implementation.
 */
function fdBinWidth(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  if (n < 2) return 1;
  const q = (p: number) => {
    const pos = (n - 1) * p;
    const lo = Math.floor(pos);
    const hi = Math.ceil(pos);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  };
  const iqr = q(0.75) - q(0.25);
  const h = (2 * iqr) / Math.cbrt(n);
  if (Number.isFinite(h) && h > 0) return h;
  const span = sorted[n - 1] - sorted[0];
  return span > 0 ? span / Math.ceil(Math.sqrt(n)) : 1;
}

function makeBinEdges(values: number[], xbins: Record<string, unknown> | null): number[] {
  const start = num(xbins?.start);
  const end = num(xbins?.end);
  if (xbins && start !== undefined && end !== undefined) {
    const size = num(xbins.size) ?? fdBinWidth(values);
    const step = size > 0 ? size : 1;
    const edges: number[] = [];
    for (let e = start; e < end + step / 2; e += step) edges.push(Math.min(e, end));
    return edges;
  }
  const width = fdBinWidth(values);
  const min = values.reduce((a, v) => Math.min(a, v), Infinity);
  const max = values.reduce((a, v) => Math.max(a, v), -Infinity);
  const count = Math.max(1, Math.ceil((max - min) / width));
  return Array.from({ length: count + 1 }, (_, i) => min + i * width);
}

// ---------------------------------------------------------------------------
// Internal plans (fully typed; the echarts option boundary is cast once)
// ---------------------------------------------------------------------------

interface SeriesDraft {
  type: string;
  name?: string;
  /** Internal: which grid the draft belongs to (not an echarts field). */
  gridIndex?: number;
  xIdx: number;
  yIdx: number;
  silent?: boolean;
  data: unknown[];
  [key: string]: unknown;
}

interface ErrorBarPlan {
  gridIndex: number;
  xIdx: number;
  yIdx: number;
  /** error_x whiskers run horizontally, error_y vertically */
  horizontal: boolean;
  category: (number | string)[];
  center: number[];
  errLo: number[];
  errHi: number[];
  color: string;
}

interface HistogramPlan {
  gridIndex: number;
  xIdx: number;
  yIdx: number;
  name: string | undefined;
  values: number[];
  xbins: Record<string, unknown> | null;
  histnorm: string;
  color: string;
  opacity: number | null;
}

interface AnnotationPoint {
  x: number;
  y: number;
  text: string;
  color: string;
  fontSize: number;
  position: string;
  /** y given as an axis fraction ("y domain"), resolved after extents */
  yFraction?: { index: number; frac: number; log?: boolean };
  /** x given as an axis fraction ("x domain"), resolved after extents */
  xFraction?: { index: number; frac: number; log?: boolean };
}

interface ShapeLine {
  gridIndex: number;
  vertical: boolean;
  value: number;
  color: string;
  width: number;
  dash: string;
}

interface RectArea {
  gridIndex: number;
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  color: string;
  opacity: number;
}

/**
 * One silent invisible series per grid carries the annotation labels (and
 * the grid's line shapes as markLine). Its points also feed the axis
 * extents, matching plotly's autorange behavior for annotations/shapes.
 */
function annotationLayer(
  xIdx: number,
  yIdx: number,
  points: AnnotationPoint[],
  shapes: ShapeLine[],
  rects: RectArea[],
): SeriesDraft {
  const data = points.map((p) => ({
    value: [p.x, p.y],
    label: {
      show: true,
      formatter: p.text,
      position: p.position,
      color: p.color,
      fontSize: p.fontSize,
      lineHeight: p.fontSize + 2,
    },
  }));
  const layer: SeriesDraft = {
    type: "scatter",
    xIdx,
    yIdx,
    data,
    silent: true,
    symbolSize: 0,
    tooltip: { show: false },
    // annotations/markers at the exact data edge (x=0, y=max) must paint
    // past the grid boundary like plotly's annotations, not clip away
    clip: false,
    z: 10,
  };
  if (shapes.length > 0) {
    layer.markLine = {
      silent: true,
      symbol: "none",
      animation: false,
      label: { show: false },
      data: shapes.map((s) => {
        const item: Record<string, unknown> = s.vertical ? { xAxis: s.value } : { yAxis: s.value };
        item.lineStyle = { color: s.color, width: s.width, type: s.dash };
        return item;
      }),
    };
  }
  if (rects.length > 0) {
    layer.markArea = {
      silent: true,
      animation: false,
      label: { show: false },
      data: rects.map((r) => {
        const pair = [
          { xAxis: r.x0, yAxis: r.y0, itemStyle: { color: r.color, opacity: r.opacity } },
          { xAxis: r.x1, yAxis: r.y1 },
        ];
        return pair;
      }),
    };
  }
  return layer;
}

/** Numbers or plotly date strings → axis units (log ranges are 10ᵏ). */
function axisRangeValue(v: unknown, type: AxisInfo["type"]): number | undefined {
  if (typeof v === "number" && Number.isFinite(v)) return type === "log" ? 10 ** v : v;
  if (typeof v === "string") {
    if (type === "time") return parsePlotlyDate(v);
    const n = num(v);
    if (n !== undefined) return type === "log" ? 10 ** n : n;
  }
  return undefined;
}

/** Value-axis tick text: integers get thousands separators, floats six
 *  significant digits (authored ranges can sit on raw IEEE floats). */
function formatTick(v: number): string {
  if (!Number.isFinite(v)) return "";
  if (Number.isInteger(v) && Math.abs(v) < 1e12) return v.toLocaleString("en-US");
  return String(Number(v.toPrecision(6)));
}

// --- tooltips: rounded, capped, grouped -------------------------------------

const TOOLTIP_MAX_ENTRIES = 8;

/** Axis-trigger tooltip: numbers shaped like the axis ticks (formatTick), at
 *  most TOOLTIP_MAX_ENTRIES series lines with a +N-more tail, and identical
 *  series+value runs collapsed into one line (the "many repeated entries"
 *  class of popup noise on dense charts). */
function formatAxisTooltip(params: unknown): string {
  const list = Array.isArray(params) ? params : [params];
  const rows: string[] = [];
  const seen = new Set<string>();
  let hidden = 0;
  for (const raw of list) {
    const p = raw as {
      seriesName?: string;
      value?: unknown;
      marker?: string;
      axisValueLabel?: string;
      axisValue?: string | number;
    };
    const value = Array.isArray(p.value) ? p.value[p.value.length - 1] : p.value;
    const numeric = typeof value === "number" ? value : Number(value);
    const text = Number.isFinite(numeric) ? formatTick(numeric) : String(value ?? "—");
    const key = `${p.seriesName ?? ""}${text}`;
    if (seen.has(key)) {
      hidden += 1;
      continue;
    }
    seen.add(key);
    if (rows.length >= TOOLTIP_MAX_ENTRIES) {
      hidden += 1;
      continue;
    }
    rows.push(`${p.marker ?? ""}${p.seriesName ?? ""}: ${text}`);
  }
  const head = list[0] as { axisValueLabel?: string; axisValue?: string | number } | undefined;
  const header =
    head?.axisValueLabel ?? (head?.axisValue !== undefined ? formatTick(Number(head.axisValue)) : "");
  const more = hidden > 0 ? `<br/>+${hidden} more` : "";
  const body = rows.join("<br/>");
  return header ? `${header}<br/>${body}${more}` : `${body}${more}`;
}

/** Dense-scatter item tooltip: the single nearest point, rounded like ticks. */
function formatScatterItem(param: unknown): string {
  const p = param as { seriesName?: string; value?: unknown; marker?: string };
  if (!Array.isArray(p.value)) return String(p.value ?? "");
  const [x, y] = p.value as [unknown, unknown];
  const xs = typeof x === "number" ? formatTick(x) : String(x);
  const ys = typeof y === "number" ? formatTick(y) : String(y);
  return `${p.marker ?? ""}${p.seriesName ?? ""}<br/>${xs}, ${ys}`;
}

/** Heatmap cell tooltip: `row · column: value` — no whole-column dumps. */
function formatHeatmapItem(param: unknown): string {
  const p = param as { value?: unknown; marker?: string };
  if (!Array.isArray(p.value) || p.value.length < 3) return String(p.value ?? "");
  const [x, y, z] = p.value as [unknown, unknown, unknown];
  const zs = typeof z === "number" ? formatTick(z) : String(z);
  return `${p.marker ?? ""}${String(y)} · ${String(x)}: ${zs}`;
}

/** The payload's authored [min, max] for this axis, or null when absent.
 *  A null side means "auto" and falls back to the data extent (unpadded). */
function authoredAxisRange(
  info: Pick<AxisInfo, "raw" | "type">,
  ext: { min: number; max: number } | null,
): [number, number] | null {
  const raw = info.raw.range;
  if (!Array.isArray(raw) || raw.length !== 2) return null;
  const autoLo = raw[0] === null || raw[0] === undefined;
  const autoHi = raw[1] === null || raw[1] === undefined;
  const lo = autoLo ? ext?.min : axisRangeValue(raw[0], info.type);
  const hi = autoHi ? ext?.max : axisRangeValue(raw[1], info.type);
  if (lo === undefined || hi === undefined || !(hi > lo)) return null;
  return [lo, hi];
}

/**
 * Convert a plotly figure payload to a ready-to-setOption ECharts option.
 * `containerWidth` drives margin/grid scaling (the same 1000px-design rule
 * as PlotlyFigure) and the data-unit→px conversion of bar widths; it
 * defaults to the design width for tests and headless use. Throws on any
 * feature outside the pilot subset — callers render plotly instead.
 */
export function plotlyToECharts(
  payload: PlotlyPayload,
  theme: Theme,
  containerWidth = DESIGN_WIDTH,
): EChartsOption {
  const palette = PLOTLY_THEME_PALETTES[theme];
  const layout = payload.layout ?? {};
  if (!asRecord(layout)) fail("payload.layout missing");
  const data = Array.isArray(payload.data) ? payload.data : fail("payload.data missing");

  const tpl = asRecord(asRecord(layout.template).layout);
  const colorway = (
    Array.isArray(tpl.colorway) ? tpl.colorway.filter((c) => typeof c === "string") : []
  ) as string[];
  const tplFont = asRecord(tpl.font);
  const fontFamily = typeof tplFont.family === "string" ? tplFont.family : undefined;
  const fontSize = num(tplFont.size) ?? 12;
  const baseColor = chromeColor(tplFont.color, palette.textColor, theme);

  const rawMargin = asRecord(layout.margin);
  const margin = {
    l: num(rawMargin.l) ?? DEFAULT_MARGIN.l,
    r: num(rawMargin.r) ?? DEFAULT_MARGIN.r,
    t: num(rawMargin.t) ?? DEFAULT_MARGIN.t,
    b: num(rawMargin.b) ?? DEFAULT_MARGIN.b,
  };
  const designW = num(layout.width) ?? DESIGN_WIDTH;
  const width = containerWidth > 0 ? containerWidth : DESIGN_WIDTH;
  const scale = width / designW;
  const height = scaledHeight(layout.height, width);

  // --- discover the axes declared in the layout ---------------------------
  const axisByKey = new Map<string, AxisInfo>();
  for (const key of Object.keys(layout)) {
    const m = AXIS_KEY_RE.exec(key);
    if (!m) continue;
    const isX = m[1] === "x";
    const index = m[2] === "" ? 0 : Number(m[2]) - 1;
    const raw = asRecord(layout[key]);
    const declared = raw.type;
    if (
      declared !== undefined &&
      declared !== null &&
      declared !== "linear" &&
      declared !== "-" &&
      declared !== "category" &&
      declared !== "log"
    ) {
      fail(`unsupported ${key}.type "${String(declared)}"`);
    }
    axisByKey.set(key, {
      key,
      index,
      isX,
      raw,
      arrayIndex: -1,
      gridIndex: -1,
      type: declared === "category" ? "category" : declared === "log" ? "log" : "value",
      categories: [],
      built: null,
    });
  }
  const axisAt = (isX: boolean, index: number): AxisInfo => {
    const key = isX ? (index === 0 ? "xaxis" : `xaxis${index + 1}`) : index === 0 ? "yaxis" : `yaxis${index + 1}`;
    const found = axisByKey.get(key);
    if (found) return found;
    const info: AxisInfo = {
      key,
      index,
      isX,
      raw: {},
      arrayIndex: -1,
      gridIndex: -1,
      type: "value",
      categories: [],
      built: null,
    };
    axisByKey.set(key, info);
    return info;
  };

  // --- grids: one per (xIdx, yIdx) pair; rects are computed in a finalize
  // step once the margin bands (titles/legend presence) are known ----------
  const grids: GridInfo[] = [];
  const gridKeys: string[] = [];
  const gridIndexFor = (xIdx: number, yIdx: number): number => {
    const key = `${xIdx}:${yIdx}`;
    const existing = gridKeys.indexOf(key);
    if (existing !== -1) return existing;
    const xd = asRecord(axisAt(true, xIdx).raw).domain;
    const yd = asRecord(axisAt(false, yIdx).raw).domain;
    const xDomain = Array.isArray(xd) && xd.length === 2 ? (xd.map(Number) as number[]) : [0, 1];
    const yDomain = Array.isArray(yd) && yd.length === 2 ? (yd.map(Number) as number[]) : [0, 1];
    const idx = grids.length;
    gridKeys.push(key);
    grids.push({ xIndex: xIdx, yIndex: yIdx, xDomain, yDomain, left: 0, top: 0, width: 0, height: 0 });
    return idx;
  };

  // --- traces ---------------------------------------------------------------
  const series: SeriesDraft[] = [];
  const histograms: HistogramPlan[] = [];
  const errorBars: ErrorBarPlan[] = [];
  const xExtents = new Map<number, { min: number; max: number } | null>();
  const yExtents = new Map<number, { min: number; max: number } | null>();
  const exactX = new Set<number>();
  const exactY = new Set<number>();
  const namedSeries: string[] = [];
  /** value axes that carry outside bar labels ("0.616 (−31%)"): headroom */
  const labelHeadroomAxes = new Set<string>();
  let heatmapVisual: { min: number; max: number; colors: string[]; title?: string } | null = null;

  const traceColor = (i: number, explicit: unknown): string => {
    const raw =
      typeof explicit === "string"
        ? explicit
        : colorway.length > 0
          ? colorway[i % colorway.length]
          : "#2dd4bf";
    return remapColor(raw, theme);
  };
  const xAdd = (idx: number, v: number | undefined) => {
    if (axisAt(true, idx).type === "log") {
      // log axes can't take linear extents or non-positive values, but they
      // DO take their own positive data extent: plotly fits the data range
      // on a log autorange, while echarts' own log autoscale snaps outward
      // to powers of ten and strands the curve in part of the canvas
      if (typeof v === "number" && Number.isFinite(v) && v > 0) {
        xExtents.set(idx, extentAdd(xExtents.get(idx) ?? null, v));
      }
      return;
    }
    xExtents.set(idx, extentAdd(xExtents.get(idx) ?? null, v));
  };
  const yAdd = (idx: number, v: number | undefined) => {
    if (axisAt(false, idx).type === "log") {
      if (typeof v === "number" && Number.isFinite(v) && v > 0) {
        yExtents.set(idx, extentAdd(yExtents.get(idx) ?? null, v));
      }
      return;
    }
    yExtents.set(idx, extentAdd(yExtents.get(idx) ?? null, v));
  };
  const registerCategory = (info: AxisInfo, label: string) => {
    if (!info.categories.includes(label)) info.categories.push(label);
  };

  for (let i = 0; i < data.length; i++) {
    const t = asRecord(data[i]);
    const type = typeof t.type === "string" ? t.type : "scatter";
    if (
      type !== "scatter" &&
      type !== "bar" &&
      type !== "histogram" &&
      type !== "heatmap" &&
      type !== "funnel"
    ) {
      fail(`unsupported trace type "${type}"`);
    }
    const xIdx = axisRefIndex(t.xaxis, "x");
    const yIdx = axisRefIndex(t.yaxis, "y");
    // funnels are not cartesian: no grid, no axis extents
    const gridIndex = type === "funnel" ? -1 : gridIndexFor(xIdx, yIdx);
    const name = typeof t.name === "string" && t.name !== "" ? t.name : undefined;
    if (name && !namedSeries.includes(name)) namedSeries.push(name);
    const marker = asRecord(t.marker);
    const line = asRecord(t.line);

    if (type === "funnel") {
      const stages = toValueArray(t.y, "funnel.stages");
      const vals = toNumberArray(t.x, "funnel.values");
      const n = Math.max(stages.length, vals.length);
      if (n === 0) fail("funnel without stage data");
      const first = vals[0] ?? 1;
      const textinfo = typeof t.textinfo === "string" ? t.textinfo : "value+percent initial";
      const showValue = textinfo.includes("value");
      const showPct = textinfo.includes("percent");
      const color = traceColor(i, Array.isArray(marker.color) ? undefined : marker.color);
      const items = stages.map((label, k) => ({
        name: String(label),
        value: vals.length > 0 ? vals[Math.min(k, vals.length - 1)] : 0,
        itemStyle: { color },
      }));
      series.push({
        type: "funnel",
        name,
        xIdx: 0,
        yIdx: 0,
        data: items,
        // plotly keeps authored stage order and proportional widths
        sort: "none",
        left: "28%",
        width: "58%",
        top: "12%",
        bottom: "7%",
        gap: 4,
        minSize: "8%",
        label: {
          show: true,
          position: "left",
          fontSize: 12,
          color: baseColor,
          formatter: (p: { name: string; value: number }) => {
            const bits: string[] = [];
            if (showValue) bits.push(String(p.value));
            if (showPct) bits.push(`${(((p.value ?? 0) / first) * 100).toFixed(1)}%`);
            return `${p.name}: ${bits.join(" · ")}`;
          },
        },
        itemStyle: { borderWidth: 0 },
        z: 2,
      });
      continue;
    }

    if (type === "scatter") {
      const xs = toValueArray(t.x, "scatter.x");
      const ys = toValueArray(t.y, "scatter.y");
      const n = Math.max(xs.length, ys.length);
      const mode = typeof t.mode === "string" ? t.mode : "lines";
      if (n === 0) {
        // degenerate empty trace: render nothing rather than fail the figure
        series.push({ type: mode.includes("lines") ? "line" : "scatter", name, gridIndex, xIdx, yIdx, data: [] });
        continue;
      }
      if (!SCATTER_MODE_RE.test(mode)) fail(`unsupported scatter mode "${mode}"`);
      const hasLines = mode.includes("lines");
      const hasMarkers = mode.includes("markers") || (!hasLines && !mode.includes("text"));
      const hasText = mode.includes("text");
      const lineColor = traceColor(i, line.color);
      const markerColor = traceColor(i, typeof marker.color === "string" ? marker.color : line.color);
      // numeric marker.color rides a colorscale (e.g. points colored by a
      // third variable): map each value through the scale to an item color
      const mcArr = Array.isArray(marker.color) ? marker.color : null;
      const mcScale = Array.isArray(marker.colorscale) ? marker.colorscale : null;
      const numericMc =
        mcArr !== null && mcScale !== null && mcArr.length > 0 && mcArr.every((c) => typeof c === "number" || c === null);
      let mcMin = Infinity;
      let mcMax = -Infinity;
      if (numericMc) {
        for (const c of mcArr as unknown[]) {
          if (typeof c === "number") {
            mcMin = Math.min(mcMin, c);
            mcMax = Math.max(mcMax, c);
          }
        }
      }
      const xInfo = axisAt(true, xIdx);
      const points: unknown[] = [];
      for (let k = 0; k < n; k++) {
        const xv = xs.length > 0 ? xs[Math.min(k, xs.length - 1)] : k;
        const yv = ys.length > 0 ? ys[Math.min(k, ys.length - 1)] : k;
        let xOut: number | string = k;
        if (typeof xv === "string") {
          const ms = parsePlotlyDate(xv);
          if (ms !== undefined && xInfo.type !== "category") {
            // date strings ride an echarts time axis (converted to epoch ms);
            // the parsed stamp feeds the axis extent like any numeric x
            xInfo.type = "time";
            xOut = ms;
            xAdd(xIdx, ms);
          } else if (ms !== undefined && xInfo.type === "time") {
            xOut = ms;
            xAdd(xIdx, ms);
          } else if (xInfo.type === "time") {
            fail("scatter.x mixes dates and categories");
          } else {
            xInfo.type = "category";
            registerCategory(xInfo, xv.replace(BR_RE, "\n"));
            xOut = xv.replace(BR_RE, "\n");
          }
        } else {
          xOut = xv;
          xAdd(xIdx, xv);
        }
        const yn = typeof yv === "string" ? fail("scatter.y holds categories") : yv;
        yAdd(yIdx, yn);
        const item: Record<string, unknown> = {
          value: [xOut, Number.isFinite(yn) ? yn : null],
        };
        if (numericMc) {
          const mv = (mcArr as unknown[])[Math.min(k, (mcArr as unknown[]).length - 1)];
          if (typeof mv === "number" && Number.isFinite(mv)) {
            const t = (mv - mcMin) / (mcMax - mcMin || 1);
            const sampled = colorFromScale(mcScale as unknown[], t);
            if (sampled) item.itemStyle = { color: remapColor(sampled, theme) };
          }
        }
        if (hasText && Array.isArray(t.text) && typeof t.text[k] === "string") {
          item.label = {
            show: true,
            formatter: t.text[k],
            position: "top",
            color: baseColor,
            fontSize: 11,
          };
        }
        points.push(item);
      }
      const draft: SeriesDraft = { type: hasLines ? "line" : "scatter", name, gridIndex, xIdx, yIdx, data: points };
      if (hasLines) {
        draft.lineStyle = {
          color: lineColor,
          width: num(line.width) ?? 2,
          type: DASH_MAP[String(line.dash)] ?? "solid",
        };
        draft.showSymbol = hasMarkers;
        draft.smooth = false;
        draft.z = 3;
      }
      if (hasMarkers) {
        const rawSymbol = typeof marker.symbol === "string" ? marker.symbol : undefined;
        const hollow = rawSymbol?.endsWith("-open") ?? false;
        const symbol = rawSymbol ? SYMBOL_MAP[hollow ? rawSymbol.slice(0, -5) : rawSymbol] : undefined;
        if (rawSymbol !== undefined && !symbol) {
          fail(`unsupported marker.symbol "${rawSymbol}"`);
        }
        draft.symbol = symbol ?? "circle";
        if (Array.isArray(marker.size)) {
          const sizes = marker.size.map((s) => num(s) ?? 6);
          draft.symbolSize = (_value: unknown, params: { dataIndex: number }) =>
            sizes[params.dataIndex] ?? 6;
        } else {
          draft.symbolSize = num(marker.size) ?? 6;
        }
        // "x-open"-style hollow markers draw as an outlined symbol
        draft.itemStyle = hollow
          ? { color: "rgba(0,0,0,0)", borderColor: markerColor, borderWidth: 2 }
          : { color: markerColor };
        // markers on the data edge stay fully painted (plotly parity)
        draft.clip = false;
      } else if (hasText) {
        draft.itemStyle = { color: lineColor };
      }
      // fill between this trace and the next (plotly `fill: "tonexty"`,
      // e.g. confidence bands): rendered as a silent polygon layer later
      if (t.fill === "tonexty") {
        draft.__bandToNext = true;
        if (typeof t.fillcolor === "string") draft.__bandFill = remapColor(t.fillcolor, theme);
      } else if (t.fill === "tozeroy") {
        draft.areaStyle = { opacity: 0.25 };
      }
      series.push(draft);
      // error bars ride the same custom series the bars use; plotly's
      // `arrayminus` makes the whisker asymmetric when present
      for (const key of ["error_x", "error_y"] as const) {
        const err = asRecord(t[key]);
        if (Object.keys(err).length === 0 || err.array === undefined) continue;
        const hi = toNumberArray(err.array, `${key}.array`);
        const lo =
          err.arrayminus !== undefined
            ? toNumberArray(err.arrayminus, `${key}.arrayminus`)
            : [...hi];
        errorBars.push({
          gridIndex,
          xIdx,
          yIdx,
          horizontal: key === "error_x",
          category: xs as (number | string)[],
          center: ys as number[],
          errLo: lo,
          errHi: hi,
          color: markerColor,
        });
      }
    } else if (type === "bar") {
      const horizontal = t.orientation === "h";
      const cat = toValueArray(horizontal ? t.y : t.x, "bar.category");
      const vals = toNumberArray(horizontal ? t.x : t.y, "bar.values");
      const n = Math.max(cat.length, vals.length);
      if (n === 0) {
        // degenerate empty trace: render nothing rather than fail the figure
        series.push({ type: "bar", name, gridIndex, xIdx, yIdx, data: [] });
        continue;
      }
      const catAxis = horizontal ? axisAt(false, yIdx) : axisAt(true, xIdx);
      const valAxis = horizontal ? axisAt(true, xIdx) : axisAt(false, yIdx);
      const isCategory = cat.some((c) => typeof c === "string");
      if (isCategory) catAxis.type = "category";
      const color = traceColor(i, Array.isArray(marker.color) ? undefined : marker.color);
      const opacity = num(marker.opacity);
      const perColors = Array.isArray(marker.color)
        ? marker.color.map((c) => (typeof c === "string" ? remapColor(c, theme) : color))
        : null;
      const widthArr = Array.isArray(t.width)
        ? t.width.map((w) => num(w))
        : [num(t.width)].filter((w): w is number => w !== undefined);

      const dataItems: unknown[] = [];
      const texts = Array.isArray(t.text) ? t.text : null;
      const textInside = t.textposition === "inside";
      for (let k = 0; k < n; k++) {
        const catV = cat.length > 0 ? cat[Math.min(k, cat.length - 1)] : k;
        const val = vals.length > 0 ? vals[Math.min(k, vals.length - 1)] : 0;
        if (catAxis.type === "category") {
          registerCategory(catAxis, String(catV).replace(BR_RE, "\n"));
        } else {
          (horizontal ? yAdd : xAdd)(horizontal ? yIdx : xIdx, Number(catV));
        }
        if (Number.isFinite(val)) {
          (horizontal ? xAdd : yAdd)(horizontal ? xIdx : yIdx, val);
          (horizontal ? xAdd : yAdd)(horizontal ? xIdx : yIdx, 0); // bar baseline pins zero
        }
        const catLabel =
          catAxis.type === "category" ? String(catV).replace(BR_RE, "\n") : Number(catV);
        const item: Record<string, unknown> = {
          value: horizontal ? [Number.isFinite(val) ? val : null, catLabel] : [catLabel, Number.isFinite(val) ? val : null],
        };
        if (perColors) {
          item.itemStyle = { color: perColors[k % perColors.length], opacity: opacity ?? 1 };
        }
        if (texts && typeof texts[k] === "string" && texts[k] !== "") {
          item.label = {
            show: true,
            formatter: texts[k],
            position: textInside ? (horizontal ? "inside" : "inside") : horizontal ? "right" : "top",
            color: textInside ? "#0f172a" : baseColor,
            fontSize: num(asRecord(t.textfont).size) ?? 12,
          };
          if (!textInside) labelHeadroomAxes.add(horizontal ? `x:${xIdx}` : `y:${yIdx}`);
        }
        dataItems.push(item);
      }
      (horizontal ? exactX : exactY).add(valAxis.index);
      const [firstWidth] = widthArr;
      if (catAxis.type !== "category" && firstWidth !== undefined && widthArr.every((w) => Number.isFinite(w))) {
        // keep the half-bar padding on the category axis (data-unit widths
        // run along it) so edge bars are not clipped
        const half = firstWidth / 2;
        for (let k = 0; k < n; k++) {
          const catV = cat.length > 0 ? cat[Math.min(k, cat.length - 1)] : k;
          (horizontal ? yAdd : xAdd)(horizontal ? yIdx : xIdx, Number(catV) + half);
          (horizontal ? yAdd : xAdd)(horizontal ? yIdx : xIdx, Number(catV) - half);
        }
      }
      const draft: SeriesDraft = {
        type: "bar",
        name,
        gridIndex,
        xIdx,
        yIdx,
        data: dataItems,
        itemStyle: { color, opacity: opacity ?? 1 },
      };
      if (widthArr.length > 0) draft.__barWidthData = widthArr[0];
      series.push(draft);
      for (const key of ["error_x", "error_y"] as const) {
        const err = asRecord(t[key]);
        if (Object.keys(err).length === 0) continue;
        if (err.array === undefined) continue; // scalar "value" form unsupported → skip
        const hi = toNumberArray(err.array, `${key}.array`);
        const lo =
          err.arrayminus !== undefined
            ? toNumberArray(err.arrayminus, `${key}.arrayminus`)
            : [...hi];
        errorBars.push({
          gridIndex,
          xIdx,
          yIdx,
          horizontal: key === "error_x",
          category: cat,
          center: vals,
          errLo: lo,
          errHi: hi,
          color,
        });
      }
    } else if (type === "histogram") {
      if (t.orientation === "h") fail("horizontal histogram unsupported");
      const values = toNumberArray(t.x, "histogram.x").filter((v) => Number.isFinite(v));
      if (values.length === 0) fail("histogram without x data");
      const histnorm = typeof t.histnorm === "string" ? t.histnorm : "";
      if (histnorm !== "" && histnorm !== "probability density") {
        fail(`unsupported histnorm "${histnorm}"`);
      }
      const xbins = asRecord(t.xbins);
      histograms.push({
        gridIndex,
        xIdx,
        yIdx,
        name,
        values,
        xbins: num(xbins.start) !== undefined && num(xbins.end) !== undefined ? xbins : null,
        histnorm,
        color: traceColor(i, Array.isArray(marker.color) ? undefined : marker.color),
        opacity: num(marker.opacity) ?? null,
      });
      exactX.add(xIdx);
      exactY.add(yIdx);
      yAdd(yIdx, 0);
    } else {
      // heatmap (correlation/confusion matrices carry category labels)
      const xsRaw = toValueArray(t.x, "heatmap.x");
      const ysRaw = toValueArray(t.y, "heatmap.y");
      let z: unknown[][];
      if (Array.isArray(t.z) && t.z.length > 0 && Array.isArray(t.z[0])) {
        z = t.z as unknown[][];
      } else {
        // typed-array serialization: flat bdata + explicit shape (plotly
        // writes shape as a "rows, cols" string)
        const rec = asRecord(t.z);
        const shapeRaw = rec.shape;
        const shape = Array.isArray(shapeRaw)
          ? shapeRaw.map(Number)
          : typeof shapeRaw === "string"
            ? shapeRaw.split(",").map((s) => Number(s.trim()))
            : [];
        if (!("bdata" in rec) || shape.length !== 2 || shape.some((n) => !Number.isFinite(n))) {
          fail("heatmap.z is not a 2D array");
        }
        const flat = decodeBdata(rec);
        const [rows, cols] = shape;
        if (flat.length !== rows * cols) fail("heatmap.z shape does not match bdata");
        z = Array.from({ length: rows }, (_, j) => flat.slice(j * cols, (j + 1) * cols));
      }
      if (z.length !== ysRaw.length || z.some((row) => !Array.isArray(row) || row.length !== xsRaw.length)) {
        fail("heatmap.z shape does not match x/y");
      }
      if (t.colorscale !== undefined && !Array.isArray(t.colorscale)) {
        fail("unsupported colorscale form");
      }
      const colors = Array.isArray(t.colorscale)
        ? (t.colorscale as unknown[]).map((stop) => {
            const s = stop as unknown[];
            return typeof s[1] === "string" ? s[1] : fail("unsupported colorscale stop");
          })
        : ["#2dd4bf", "#f472b6"];
      const xInfoH = axisAt(true, xIdx);
      const yInfoH = axisAt(false, yIdx);
      const xCat = xsRaw.some((v) => typeof v === "string");
      const yCat = ysRaw.some((v) => typeof v === "string");
      if (xCat) xInfoH.type = "category";
      if (yCat) yInfoH.type = "category";
      const items: unknown[] = [];
      let zMin = Infinity;
      let zMax = -Infinity;
      for (let j = 0; j < ysRaw.length; j++) {
        const yv = ysRaw[j];
        for (let k = 0; k < xsRaw.length; k++) {
          const xv = xsRaw[k];
          const zRaw = z[j][k];
          // holes (null / NaN cells) render as empty matrix slots
          if (zRaw === null || zRaw === undefined || (typeof zRaw === "number" && !Number.isFinite(zRaw))) {
            continue;
          }
          const zv = num(zRaw);
          if (zv === undefined) fail("heatmap.z holds a non-numeric value");
          if (typeof xv === "string") registerCategory(xInfoH, xv.replace(BR_RE, "\n"));
          else xAdd(xIdx, xv);
          if (typeof yv === "string") registerCategory(yInfoH, yv.replace(BR_RE, "\n"));
          else yAdd(yIdx, yv);
          zMin = Math.min(zMin, zv);
          zMax = Math.max(zMax, zv);
          items.push({
            value: [
              typeof xv === "string" ? xv.replace(BR_RE, "\n") : xv,
              typeof yv === "string" ? yv.replace(BR_RE, "\n") : yv,
              zv,
            ],
          });
        }
      }
      series.push({
        type: "heatmap",
        name,
        gridIndex,
        xIdx,
        yIdx,
        data: items,
        z: 1,
        // small matrices read better with the value printed in the cell;
        // large ones stay clean and rely on the cell tooltip
        ...(xsRaw.length * ysRaw.length <= 144
          ? {
              label: {
                show: true,
                fontSize: 10,
                color: palette.textColor,
                formatter: (p: { value?: unknown[] }) =>
                  Array.isArray(p.value) && typeof p.value[2] === "number"
                    ? formatTick(p.value[2])
                    : "",
              },
            }
          : {}),
      });
      const colorbarTitle = asRecord(
        asRecord(asRecord(t.marker).colorbar).title ?? asRecord(t.colorbar).title,
      ).text;
      heatmapVisual = {
        min: zMin,
        max: zMax,
        colors,
        ...(typeof colorbarTitle === "string" && colorbarTitle
          ? { title: colorbarTitle.replace(BR_RE, " ") }
          : {}),
      };
    }
  }

  // --- confidence bands (plotly `fill: "tonexty"`): silent polygon between
  // the flagged trace and the next one on the same grid ----------------------
  for (let s = 0; s < series.length; s++) {
    const draft = series[s];
    if (draft.__bandToNext !== true) continue;
    const fillRaw = draft.__bandFill;
    const lower = series[s + 1];
    delete draft.__bandToNext;
    delete draft.__bandFill;
    if (!lower || lower.gridIndex !== draft.gridIndex) continue;
    if (draft.type !== "line" && draft.type !== "scatter") continue;
    if (lower.type !== "line" && lower.type !== "scatter") continue;
    const upperPts = (draft.data as Array<{ value: unknown[] }>).map((d) => d.value);
    const lowerPts = (lower.data as Array<{ value: unknown[] }>).map((d) => d.value);
    const fill = typeof fillRaw === "string" ? fillRaw : String((draft.lineStyle as Record<string, unknown> | undefined)?.color ?? "#38bdf8");
    const bandOpacity = typeof fillRaw === "string" ? 1 : 0.22;
    series.push({
      type: "custom",
      gridIndex: draft.gridIndex,
      xIdx: draft.xIdx,
      yIdx: draft.yIdx,
      // the item value is one real upper point: inside the data extent, so
      // the series influences the axis range exactly as the line itself does
      data: [{ value: upperPts[0] ?? [0, 0] }],
      silent: true,
      z: 1,
      // the polygon reads the closure's point lists (per-band), not params:
      // echarts v6 does not expose the raw item on the renderItem params
      renderItem: (_params: unknown, api: { coord: (v: unknown[]) => number[] }) => {
        const pts = [
          ...upperPts.map((p) => api.coord(p)),
          ...[...lowerPts].reverse().map((p) => api.coord(p)),
        ];
        return {
          type: "polygon",
          shape: { points: pts },
          style: { fill, opacity: bandOpacity },
        };
      },
    } as SeriesDraft);
  }

  // --- histogram binning: shared edges per x-axis, like plotly's autobin ---
  const histByAxis = new Map<number, HistogramPlan[]>();
  for (const h of histograms) {
    const list = histByAxis.get(h.xIdx) ?? [];
    list.push(h);
    histByAxis.set(h.xIdx, list);
  }
  for (const [xIdx, plans] of histByAxis) {
    const pooled = plans.flatMap((p) => p.values);
    const sharedXbins =
      plans.length > 0 && plans.every((p) => p.xbins !== null) ? plans[0].xbins : null;
    const edges = makeBinEdges(pooled, sharedXbins);
    for (const e of edges) xAdd(xIdx, e);
    const centers = edges.slice(0, -1).map((e, b) => (e + edges[b + 1]) / 2);
    const binWidth = edges.length > 1 ? edges[1] - edges[0] : 1;
    for (const plan of plans) {
      const counts = new Array<number>(centers.length).fill(0);
      for (const v of plan.values) {
        const b = Math.min(centers.length - 1, Math.max(0, Math.floor((v - edges[0]) / binWidth)));
        counts[b] += 1;
      }
      // probability density: count / (n · binWidth), so areas integrate to 1
      const norm = plan.histnorm === "probability density" ? plan.values.length * binWidth : 1;
      series.push({
        type: "bar",
        name: plan.name,
        gridIndex: plan.gridIndex,
        xIdx,
        yIdx: plan.yIdx,
        data: centers.map((c, b) => ({ value: [c, counts[b] / norm] })),
        itemStyle: { color: plan.color, opacity: plan.opacity ?? 1 },
        __binWidth: binWidth,
        z: 2,
      });
      if (plan.name && !namedSeries.includes(plan.name)) namedSeries.push(plan.name);
    }
  }

  // --- error bars (custom series; echarts has no built-in) -------------------
  for (const plan of errorBars) {
    const items: unknown[] = [];
    for (let k = 0; k < plan.center.length; k++) {
      const kHi = Math.min(k, plan.errHi.length - 1);
      const kLo = Math.min(k, plan.errLo.length - 1);
      if (!Number.isFinite(plan.center[k])) continue;
      if (!Number.isFinite(plan.errHi[kHi]) && !Number.isFinite(plan.errLo[kLo])) continue;
      items.push({
        value: plan.horizontal
          ? [plan.center[k], plan.category[Math.min(k, plan.category.length - 1)], plan.errLo[kLo], plan.errHi[kHi]]
          : [plan.category[Math.min(k, plan.category.length - 1)], plan.center[k], plan.errLo[kLo], plan.errHi[kHi]],
      });
    }
    if (items.length === 0) continue;
    series.push({
      type: "custom",
      gridIndex: plan.gridIndex,
      xIdx: plan.xIdx,
      yIdx: plan.yIdx,
      data: items,
      silent: true,
      z: 4,
      renderItem: (_params: unknown, api: { value: (i: number) => number; coord: (v: number[]) => number[] }) => {
        const cap = 4;
        const stroke = { stroke: plan.color, lineWidth: 1.5 };
        if (plan.horizontal) {
          const mid = api.coord([api.value(0), api.value(1)]);
          const lo = api.coord([api.value(0) - api.value(2), api.value(1)]);
          const hi = api.coord([api.value(0) + api.value(3), api.value(1)]);
          return {
            type: "group",
            children: [
              { type: "line", shape: { x1: lo[0], y1: lo[1], x2: hi[0], y2: hi[1] }, style: stroke },
              { type: "line", shape: { x1: lo[0], y1: mid[1] - cap, x2: lo[0], y2: mid[1] + cap }, style: stroke },
              { type: "line", shape: { x1: hi[0], y1: mid[1] - cap, x2: hi[0], y2: mid[1] + cap }, style: stroke },
            ],
          };
        }
        const mid = api.coord([api.value(0), api.value(1)]);
        const lo = api.coord([api.value(0), api.value(1) - api.value(2)]);
        const hi = api.coord([api.value(0), api.value(1) + api.value(3)]);
        return {
          type: "group",
          children: [
            { type: "line", shape: { x1: lo[0], y1: lo[1], x2: hi[0], y2: hi[1] }, style: stroke },
            { type: "line", shape: { x1: mid[0] - cap, y1: lo[1], x2: mid[0] + cap, y2: lo[1] }, style: stroke },
            { type: "line", shape: { x1: mid[0] - cap, y1: hi[1], x2: mid[0] + cap, y2: hi[1] }, style: stroke },
          ],
        };
      },
    } as SeriesDraft);
  }

  // --- annotations ------------------------------------------------------------
  const annotations = Array.isArray(layout.annotations) ? layout.annotations : [];
  // subplot headers, keyed by grid; positioned after the margin bands exist
  const subTitleByGrid = new Map<number, { text: string; color: string; fontSize: number }>();
  const annPointsByGrid = new Map<number, AnnotationPoint[]>();
  for (const raw of annotations) {
    const a = asRecord(raw);
    const text = typeof a.text === "string" ? stripTags(a.text.replace(BR_RE, "\n")) : "";
    if (text === "") continue;
    const font = asRecord(a.font);
    const fontSize = num(font.size) ?? 13;
    // plotly defaults absent refs to the plain axes ("x"/"y"); only explicit
    // "paper" refs (the subplot headers) take the title branch below
    const xref = typeof a.xref === "string" ? a.xref : "x";
    const yref = typeof a.yref === "string" ? a.yref : "y";
    const xanchor = typeof a.xanchor === "string" ? a.xanchor : "center";
    if (xref === "paper" && yref === "paper" && a.showarrow === false) {
      // subplot header: map the paper point onto the grid whose domain
      // rect contains it (stacked subplots share x domains, so the y
      // coordinate is the discriminator)
      const ax = num(a.x) ?? 0.5;
      const ay = num(a.y) ?? 1;
      let bestGrid = 0;
      let bestDist = Infinity;
      for (let g = 0; g < grids.length; g++) {
        const gd = grids[g];
        const cx = (gd.xDomain[0] + gd.xDomain[1]) / 2;
        const cy = (gd.yDomain[0] + gd.yDomain[1]) / 2;
        const inside =
          ax >= gd.xDomain[0] - 0.02 &&
          ax <= gd.xDomain[1] + 0.02 &&
          1 - ay >= gd.yDomain[0] - 0.05 &&
          1 - ay <= gd.yDomain[1] + 0.05;
        const d = Math.abs(cx - ax) + Math.abs(cy - (1 - ay));
        if (inside) {
          bestGrid = g;
          bestDist = -1;
          break;
        }
        if (d < bestDist) {
          bestDist = d;
          bestGrid = g;
        }
      }
      void bestDist;
      subTitleByGrid.set(bestGrid, {
        text,
        color: chromeColor(font.color, palette.textColor, theme),
        fontSize,
      });
      continue;
    }
    const xIdx = xref.startsWith("x") && xref !== "paper" ? axisRefIndex(xref, "x") : null;
    const yIdx = yref.startsWith("y") && yref !== "paper" ? axisRefIndex(yref, "y") : null;
    // "… domain" refs are axis fractions; plain "paper" heights resolve too
    const yIsFraction = yref.endsWith(" domain") || yref === "paper";
    const xIsFraction = xref.endsWith(" domain");
    let xVal = num(a.x);
    if (typeof a.x === "string" && xIdx !== null && axisAt(true, xIdx).type === "time") {
      xVal = parsePlotlyDate(a.x);
    }
    if (xIdx === null) continue;
    const xAxisIsTime = axisAt(true, xIdx).type === "time";
    if (xIsFraction) {
      // a fraction of the x domain — resolved once the extents are final;
      // fractions are safe on any axis (they map onto the data extent)
      const fracPoint: AnnotationPoint = {
        x: 0,
        y: 0,
        text,
        color: remapColor(typeof font.color === "string" ? font.color : palette.textColor, theme),
        fontSize,
        position: xanchor === "right" ? "right" : "top",
        xFraction: {
          index: xIdx,
          frac: num(a.x) ?? 1,
          log: axisAt(true, xIdx).type === "log",
        },
      };
      if (yIsFraction) {
        fracPoint.yFraction = {
          index: yIdx ?? 0,
          frac: num(a.y) ?? 1,
          log: yIdx !== null && axisAt(false, yIdx).type === "log",
        };
      } else {
        const yVal = num(a.y);
        if (yVal !== undefined && yIdx !== null) yAdd(yIdx, yVal);
        fracPoint.y = yVal ?? 0;
      }
      const list = annPointsByGrid.get(gridIndexFor(xIdx, yIdx ?? xIdx)) ?? [];
      list.push(fracPoint);
      annPointsByGrid.set(gridIndexFor(xIdx, yIdx ?? xIdx), list);
      continue;
    }
    if (xVal === undefined) continue;
    // numeric x on a time axis whose dates come from strings: a bare number
    // is not a date and must never become a time value (epoch garbage)
    if (xAxisIsTime && typeof a.x === "number") continue;
    const gridIndex = gridIndexFor(xIdx, yIdx ?? xIdx);
    xAdd(xIdx, xVal);
    const point: AnnotationPoint = {
      x: xVal,
      y: 0,
      text,
      color: remapColor(typeof font.color === "string" ? font.color : palette.textColor, theme),
      fontSize,
      position: xanchor === "right" ? "right" : "top",
    };
    if (yIsFraction) {
      point.yFraction = {
        index: yIdx ?? 0,
        frac: num(a.y) ?? 1,
        log: yIdx !== null && axisAt(false, yIdx).type === "log",
      };
    } else {
      const yVal = num(a.y);
      if (yVal !== undefined && yIdx !== null) yAdd(yIdx, yVal);
      point.y = yVal ?? 0;
    }
    const list = annPointsByGrid.get(gridIndex) ?? [];
    list.push(point);
    annPointsByGrid.set(gridIndex, list);
  }

  // --- shapes -------------------------------------------------------------------
  const shapes = Array.isArray(layout.shapes) ? layout.shapes : [];
  const shapeLines: ShapeLine[] = [];
  const shapeRects: RectArea[] = [];
  // shapes tolerate paper refs: a vertical line's y ref and a horizontal
  // line's x ref don't matter (markLine spans the whole grid anyway)
  const shapeAxisRef = (v: unknown, axis: "x" | "y"): number =>
    typeof v === "string" && v === "paper" ? 0 : axisRefIndex(v, axis);
  // date-string bounds on a time axis → epoch ms
  const shapeValue = (v: unknown, idx: number, isX: boolean): number | undefined => {
    if (typeof v === "string") {
      const info = axisAt(isX, idx);
      if (info.type === "time") return parsePlotlyDate(v);
      return undefined;
    }
    return num(v);
  };
  for (const raw of shapes) {
    const s = asRecord(raw);
    const xIdx = shapeAxisRef(s.xref, "x");
    const yIdx = shapeAxisRef(s.yref, "y");
    // a bare NUMBER on a time axis with a DATA ref is never a date (plotly
    // writes domain fractions as numbers, but those carry a "… domain" ref
    // and resolve against the extent) — drop such shapes rather than let
    // epoch garbage reach the axis
    const xDataRefNum =
      !(typeof s.xref === "string" && s.xref.endsWith(" domain")) &&
      (typeof s.x0 === "number" || typeof s.x1 === "number");
    const yDataRefNum =
      !(typeof s.yref === "string" && s.yref.endsWith(" domain")) &&
      (typeof s.y0 === "number" || typeof s.y1 === "number");
    if (
      (axisAt(true, xIdx).type === "time" && xDataRefNum) ||
      (axisAt(false, yIdx).type === "time" && yDataRefNum)
    ) {
      continue;
    }
    const gridIndex = gridIndexFor(xIdx, yIdx);
    const xDomainRef = typeof s.xref === "string" && s.xref.endsWith(" domain");
    const yDomainRef = typeof s.yref === "string" && s.yref.endsWith(" domain");
    if (s.type === "rect") {
      // highlight region (e.g. anomaly windows, CI bands): becomes markArea
      const fillRaw = typeof s.fillcolor === "string" ? s.fillcolor : "rgba(148,163,184,0.2)";
      const opacity = num(s.opacity) ?? 1;
      const xExt = xExtents.get(xIdx);
      const yExt = yExtents.get(yIdx);
      const resolve = (
        v: number | undefined,
        ext: { min: number; max: number } | null | undefined,
        frac: boolean,
      ) => {
        if (v === undefined) return undefined;
        if (!frac) return v;
        // a domain fraction needs the axis' real data extent — never a
        // synthetic [0,1] window
        if (!ext) return undefined;
        return ext.min + v * (ext.max - ext.min);
      };
      const rx0 = resolve(shapeValue(s.x0, xIdx, true), xExt, xDomainRef);
      const rx1 = resolve(shapeValue(s.x1, xIdx, true), xExt, xDomainRef);
      const ry0 = resolve(shapeValue(s.y0, yIdx, false), yExt, yDomainRef);
      const ry1 = resolve(shapeValue(s.y1, yIdx, false), yExt, yDomainRef);
      if (rx0 === undefined || rx1 === undefined || ry0 === undefined || ry1 === undefined) {
        fail("unsupported rect shape bounds");
      }
      shapeRects.push({
        gridIndex,
        x0: Math.min(rx0, rx1),
        x1: Math.max(rx0, rx1),
        y0: Math.min(ry0, ry1),
        y1: Math.max(ry0, ry1),
        color: remapColor(fillRaw, theme),
        opacity,
      });
      xAdd(xIdx, rx0);
      xAdd(xIdx, rx1);
      yAdd(yIdx, ry0);
      yAdd(yIdx, ry1);
      continue;
    }
    if (s.type !== "line") fail(`unsupported shape type "${String(s.type)}"`);
    const lineStyle = asRecord(s.line);
    const color = remapColor(
      typeof lineStyle.color === "string" ? lineStyle.color : palette.textColor,
      theme,
    );
    const width = num(lineStyle.width) ?? 2;
    const dash = DASH_MAP[String(lineStyle.dash)] ?? "solid";
    const x0 = shapeValue(s.x0, xIdx, true);
    const x1 = shapeValue(s.x1, xIdx, true);
    const y0 = shapeValue(s.y0, yIdx, false);
    const y1 = shapeValue(s.y1, yIdx, false);
    if (x0 !== undefined && x0 === x1) {
      shapeLines.push({ gridIndex, vertical: true, value: x0, color, width, dash });
      xAdd(xIdx, x0);
    } else if (y0 !== undefined && y0 === y1) {
      shapeLines.push({ gridIndex, vertical: false, value: y0, color, width, dash });
      yAdd(yIdx, y0);
    } else {
      fail("diagonal line shape unsupported");
    }
  }

  // --- finalize axis arrays -------------------------------------------------------
  const xInfos = [...axisByKey.values()].filter((i) => i.isX).sort((a, b) => a.index - b.index);
  const yInfos = [...axisByKey.values()].filter((i) => !i.isX).sort((a, b) => a.index - b.index);
  xInfos.forEach((info, i) => {
    info.arrayIndex = i;
  });
  yInfos.forEach((info, i) => {
    info.arrayIndex = i;
  });
  // explicit ticktext/tickvals define the category labels (lollipop ranks):
  // integer positions 0..n-1 index into the label list
  for (const info of [...xInfos, ...yInfos]) {
    const tickText = info.raw.ticktext;
    const tickVals = info.raw.tickvals;
    const indexed =
      Array.isArray(tickText) &&
      tickText.length > 0 &&
      tickText.every((v) => typeof v === "string") &&
      Array.isArray(tickVals) &&
      tickVals.length === tickText.length &&
      tickVals.every((v, i) => num(v) === i);
    if (indexed) {
      info.type = "category";
      info.categories = tickText.map((v) => String(v).replace(BR_RE, "\n"));
    }
  }
  // heatmap cells need category axes in echarts: register every distinct
  // coordinate as a category (stringified) so value pairs resolve by label
  for (const draft of series) {
    if (draft.type !== "heatmap") continue;
    const xh = axisAt(true, draft.xIdx);
    const yh = axisAt(false, draft.yIdx);
    xh.type = "category";
    yh.type = "category";
    for (const item of draft.data as Array<{ value: unknown[] }>) {
      const [xv, yv] = item.value as [unknown, unknown];
      const xs = String(xv);
      const ys = String(yv);
      if (!xh.categories.includes(xs)) xh.categories.push(xs);
      if (!yh.categories.includes(ys)) yh.categories.push(ys);
      item.value = [xs, ys, item.value[2]];
    }
  }
  const axisTitleText = (info: AxisInfo): string | null => {
    const t = info.raw.title;
    if (typeof t === "string") return t;
    const inner = asRecord(t).text;
    return typeof inner === "string" ? inner : null;
  };

  // --- axis ↔ grid wiring ---------------------------------------------------------
  // ECharts requires a series' xAxis and yAxis to belong to the SAME grid, so
  // each axis joins the first in-use grid carrying its index (the diagonal
  // pairings plotly's anchor model implies are dropped when unused).
  const usedGrids = new Set<number>();
  for (const d of series) if (d.gridIndex !== undefined) usedGrids.add(d.gridIndex);
  for (const g of annPointsByGrid.keys()) usedGrids.add(g);
  for (const s of shapeLines) usedGrids.add(s.gridIndex);
  for (const r of shapeRects) usedGrids.add(r.gridIndex);
  for (const g of subTitleByGrid.keys()) usedGrids.add(g);
  for (const info of xInfos) {
    info.gridIndex = grids.findIndex((g, gi) => usedGrids.has(gi) && g.xIndex === info.index);
  }
  for (const info of yInfos) {
    info.gridIndex = grids.findIndex((g, gi) => usedGrids.has(gi) && g.yIndex === info.index);
  }
  // drop unused grids, remap indices, and build one axis instance PER GRID:
  // echarts pairs axes with grids 1:1, so a plotly axis shared by (or paired
  // across) several grids becomes one instance per grid
  const remap = new Map<number, number>();
  const keptGrids: GridInfo[] = [];
  grids.forEach((g, gi) => {
    if (usedGrids.has(gi)) {
      remap.set(gi, keptGrids.length);
      keptGrids.push(g);
    }
  });
  grids.length = 0;
  grids.push(...keptGrids);
  const remapGrid = (gi: number) => (gi === -1 ? -1 : (remap.get(gi) ?? 0));
  for (const d of series) if (d.gridIndex !== undefined) d.gridIndex = remapGrid(d.gridIndex);
  {
    const rebuilt = new Map<number, AnnotationPoint[]>();
    for (const [g, pts] of annPointsByGrid) rebuilt.set(remapGrid(g), pts);
    annPointsByGrid.clear();
    for (const [g, pts] of rebuilt) annPointsByGrid.set(g, pts);
    const subRebuilt = new Map<number, { text: string; color: string; fontSize: number }>();
    for (const [g, t] of subTitleByGrid) subRebuilt.set(remapGrid(g), t);
    subTitleByGrid.clear();
    for (const [g, t] of subRebuilt) subTitleByGrid.set(g, t);
    for (const s of shapeLines) s.gridIndex = remapGrid(s.gridIndex);
    for (const r of shapeRects) r.gridIndex = remapGrid(r.gridIndex);
  }
  const xInstances = grids.map((g) => ({ info: axisAt(true, g.xIndex), gridIndex: grids.indexOf(g) }));
  const yInstances = grids.map((g) => ({ info: axisAt(false, g.yIndex), gridIndex: grids.indexOf(g) }));

  // --- margin bands ---------------------------------------------------------------
  // Font sizes don't scale with the container, so the paper margins (which the
  // authored figures size for a 1000px design) are clamped to px minimums:
  // titles/legends/rotated labels must never be squeezed out or overlap the
  // plot. top: global title block + subplot-header band; bottom: rotated
  // category labels + axis names; left/right: tick widths, legend, colorbar.
  const titleParts = (() => {
    const t = asRecord(layout.title);
    const text = typeof t.text === "string" ? t.text : null;
    if (text === null) return null;
    const parts = text.split(BR_RE).map(stripTags);
    const titleFont = asRecord(t.font);
    const subMatch = INLINE_COLOR_RE.exec(text);
    const subColorRaw = subMatch ? `#${subMatch[1]}` : SUBTEXT_COLOR_DARK;
    const size = num(titleFont.size) ?? 16;
    const subSize = Math.min(13, size - 3.5);
    // word-wrap the subtitle so it never clips at the card edge
    const maxChars = Math.max(14, Math.floor((width * 0.92) / (subSize * 0.6)));
    const rawSub = parts.slice(1).join(" ");
    const lines: string[] = [];
    let cur = "";
    for (const word of rawSub.split(/\s+/)) {
      if ((cur + " " + word).trim().length > maxChars) {
        if (cur) lines.push(cur.trim());
        cur = word;
      } else {
        cur = (cur + " " + word).trim();
      }
    }
    if (cur) lines.push(cur.trim());
    const subtext = lines.join("\n");
    return {
      text: parts[0],
      subtext,
      subLines: lines.length,
      color: chromeColor(titleFont.color, palette.textColor, theme),
      size,
      subSize,
      subColor:
        theme === "light"
          ? (LIGHT_TRACE_COLOR_MAP[subColorRaw.toLowerCase()] ?? SUBTEXT_COLOR_LIGHT)
          : subColorRaw,
    };
  })();
  const rawLegend = asRecord(layout.legend);
  const showLegend = (layout.showlegend ?? tpl.showlegend ?? true) !== false && namedSeries.length > 0;
  const legendOrient = rawLegend.orientation === "h" ? "horizontal" : "vertical";
  const hasMainTitle = titleParts !== null;
  const mainTitleBlock = hasMainTitle
    ? titleParts.size + (titleParts.subtext ? (titleParts.subLines * (titleParts.subSize + 3)) : 0) + 8
    : 0;
  const anyCategoryY = yInfos.some((i) => i.type === "category");
  const longestYCat = yInfos.reduce(
    (m, i) => (i.type === "category" ? i.categories.reduce((a, c) => Math.max(a, c.length), m) : m),
    0,
  );
  const anyYName = yInfos.some((i) => axisTitleText(i) !== null);
  // horizontal y category labels (candidate names) need real width
  const yCatBand = anyCategoryY
    ? Math.min(Math.round(longestYCat * 6.0) + 14 + (anyYName ? 18 : 0), Math.round(width * 0.44))
    : 0;
  const leftBand = Math.max(margin.l * scale, 40 + (anyYName ? 16 : 0), yCatBand);
  // the right band must actually fit the longest legend entry, capped so
  // mobile keeps plot room
  const longestName = namedSeries.reduce((m, n) => Math.max(m, n.length), 0);
  const legendBand =
    showLegend && legendOrient === "vertical"
      ? Math.min(Math.max(122, longestName * 7.8 + 46), Math.round(width * 0.46))
      : 0;
  const rightBand = Math.max(margin.r * scale, legendBand, heatmapVisual ? 60 : 0);
  const innerWpx = Math.max(40, width - leftBand - rightBand);
  // subplot headers shrink + wrap to their grid width so neighboring titles
  // can never collide, however narrow the canvas
  const subMetrics = new Map<number, { text: string; fontSize: number; lines: number }>();
  for (const [g, sub] of subTitleByGrid) {
    const grid = grids[g];
    const gridW = grid ? (grid.xDomain[1] - grid.xDomain[0]) * innerWpx : innerWpx;
    const oneLineW = sub.text.length * sub.fontSize * 0.58;
    const fontSize =
      oneLineW > gridW ? Math.max(10, Math.floor(sub.fontSize * Math.min(1, gridW / oneLineW))) : sub.fontSize;
    const maxChars = Math.max(6, Math.floor((gridW * 0.94) / (fontSize * 0.58)));
    const text = sub.text.length > maxChars ? wrapText(sub.text, maxChars) : sub.text;
    subMetrics.set(g, { text, fontSize, lines: text.split("\n").length });
  }
  const subTitleBand =
    subMetrics.size > 0
      ? Math.max(...[...subMetrics.values()].map((m) => m.lines * (m.fontSize + 3) + 6))
      : 0;
  const topBand = Math.max(
    margin.t * scale,
    hasMainTitle || subTitleBand > 0 ? mainTitleBlock + subTitleBand + 8 : 0,
  );
  // bottom band: rotated label depth + axis-name clearance, per category axis
  const bottomBand = (() => {
    let band = Math.max(margin.b * scale, 26);
    for (const info of xInfos) {
      if (info.type !== "category") continue;
      const grid = grids.find((g) => g.xIndex === info.index);
      const span = grid ? grid.xDomain[1] - grid.xDomain[0] : 1;
      const n = Math.max(1, info.categories.length);
      const longest = info.categories.reduce((m, c) => Math.max(m, c.length), 0);
      const slot = (innerWpx * span) / n;
      const rotated = slot < longest * 6.2 + 8;
      const depth = rotated ? longest * 6.2 * 0.55 + 20 : 16;
      band = Math.max(band, Math.round(depth + (axisTitleText(info) !== null ? 30 : 8)));
    }
    return band;
  })();
  const innerHpx = Math.max(40, height - topBand - bottomBand);
  for (const g of grids) {
    g.left = leftBand + g.xDomain[0] * innerWpx;
    g.top = topBand + (1 - g.yDomain[1]) * innerHpx;
    g.width = (g.xDomain[1] - g.xDomain[0]) * innerWpx;
    g.height = (g.yDomain[1] - g.yDomain[0]) * innerHpx;
  }

  const buildAxis = (info: AxisInfo, gridIndex: number, overlay: "none" | "right" | "top"): Record<string, unknown> => {
    const extents = info.isX ? xExtents : yExtents;
    const exactSet = info.isX ? exactX : exactY;
    const ext = extents.get(info.index) ?? null;
    const rawTick = asRecord(info.raw.tickfont);
    const titleFont = asRecord(asRecord(info.raw.title).font);
    const titleText = axisTitleText(info);
    const axisLabel: Record<string, unknown> = {
      color: chromeColor(rawTick.color, palette.textColor, theme),
      fontSize: num(rawTick.size) ?? fontSize - 2,
      fontFamily: MONO_STACK,
      hideOverlap: true,
    };
    if (info.raw.showticklabels === false) axisLabel.show = false;
    // axis name: wrap long titles so they never clip, and keep clearance from
    // (possibly rotated) tick labels below/left
    const gridW = grids[gridIndex]?.width ?? innerWpx;
    const gridH = grids[gridIndex]?.height ?? innerHpx;
    const nameFont = (axisLabel.fontSize as number) + 1;
    let wrappedName: string | null = null;
    if (titleText) {
      const maxChars = Math.max(8, Math.floor(((info.isX ? gridW : gridH) * 0.8) / (nameFont * 0.62)));
      wrappedName = wrapText(titleText.replace(BR_RE, "\n"), maxChars);
    }
    if (info.type === "category") {
      axisLabel.fontSize = 10;
      if (info.isX) {
        // rotate only when the longest label can't fit its slot horizontally
        const longest = info.categories.reduce((m, c) => Math.max(m, c.length), 0);
        const slot = gridW / Math.max(1, info.categories.length);
        const estW = longest * 6.2 + 8;
        if (slot < estW) {
          axisLabel.rotate = 30;
          axisLabel.margin = 6;
        }
      }
    }
    const opt: Record<string, unknown> = {
      type: info.type,
      gridIndex,
      axisLine: { lineStyle: { color: chromeColor(info.raw.linecolor, palette.axisLineColor, theme) } },
      axisTick: { show: false },
      position: overlay === "right" ? "right" : overlay === "top" ? "top" : undefined,
      splitLine: {
        show: overlay === "none",
        lineStyle: { color: chromeColor(info.raw.gridcolor, palette.gridColor, theme) },
      },
      axisLabel,
    };
    if (info.type === "value") {
      // trim raw-float ticks (authored ranges and extents can land on
      // 0.9560236…; integers still get thousands separators)
      axisLabel.formatter = (v: number) => formatTick(v);
    }
    // range precedence: an authored layout.*axis.range wins verbatim; then the
    // bar-family zero baseline (positive-only extents); otherwise the window
    // is the axis' own data extent ± 5% padding, materialized explicitly —
    // echarts v6 no longer honors `scale: true` for zero-exclusion, and an
    // explicit window is the only way to keep epoch 0 / a pinned zero out.
    const authored = authoredAxisRange(info, ext);
    if (authored) {
      opt.min = authored[0];
      opt.max = authored[1];
    } else if (
      info.type === "value" &&
      info.raw.type !== "log" &&
      ext &&
      exactSet.has(info.index)
    ) {
      // bar/histogram baselines sit at zero: pin the side the bars grow away
      // from for single-signed extents (min for positive-only, max for
      // negative-only); mixed-signed extents use the plain data window
      if (ext.min >= 0) {
        opt.min = 0;
        opt.max = ext.max + (ext.max - ext.min > 0 ? (ext.max - ext.min) * 0.05 : 1);
      } else if (ext.max <= 0) {
        opt.max = 0;
        opt.min = ext.min - (ext.max - ext.min > 0 ? (ext.max - ext.min) * 0.05 : 1);
      } else {
        const span = ext.max - ext.min;
        const pad = span > 0 ? span * 0.05 : 1;
        opt.min = ext.min - pad;
        opt.max = ext.max + pad;
      }
    } else if (info.type !== "category") {
      if (ext) {
        if (info.raw.type === "log") {
          // plotly's log autorange fits the data extent exactly; echarts'
          // own autoscale snaps to powers of ten and strands the curve in
          // part of the canvas. Materialize the exact positive extent: a
          // pad would only dirty the boundary tick (0.00430458… vs 0.005).
          opt.min = ext.min;
          opt.max = ext.max;
        } else {
          const span = ext.max - ext.min;
          const pad = span > 0 ? span * 0.05 : Math.max(1, Math.abs(ext.max) * 0.05);
          opt.min = ext.min - pad;
          opt.max = ext.max + pad;
        }
      }
      // an axis with no data emits no min/max at all — no synthetic [0,1]
    }
    if (info.type === "category") {
      opt.data = info.categories;
    }
    if (wrappedName) {
      // sub-120px grids can't host a y-axis name without it colliding with
      // the neighbor subplot's chrome — the subplot title already names it
      const narrowY = !info.isX && (grids[gridIndex]?.width ?? innerWpx) < 120;
      if (!narrowY) {
        opt.name = wrappedName;
        opt.nameLocation = "middle";
        // gap must clear the rotated-label stack below (x) or the label column
        // plus padding (y)
        const rotated = typeof axisLabel.rotate === "number";
        const longestCat = info.type === "category"
          ? info.categories.reduce((m, c) => Math.max(m, c.length), 0)
          : 0;
        const labelDepth = info.isX
          ? info.type === "category" && rotated
            ? longestCat * 6.2 * 0.55 + 18
            : 16
          : info.type === "category"
            ? 14
            : 16;
        opt.nameGap = info.isX ? Math.round(26 + labelDepth) : Math.round(36 + labelDepth);
        opt.nameTextStyle = { color: chromeColor(titleFont.color, palette.textColor, theme) };
      }
    }
    return opt;
  };
  // stacked subplots share one axis each; OVERLAID subplots (identical
  // domain rect) are plotly's secondary-axis idiom — those instances move to
  // the far side and drop their gridlines
  const sameRect = (a: GridInfo, b: GridInfo) =>
    Math.abs(a.xDomain[0] - b.xDomain[0]) < 0.01 &&
    Math.abs(a.xDomain[1] - b.xDomain[1]) < 0.01 &&
    Math.abs(a.yDomain[0] - b.yDomain[0]) < 0.01 &&
    Math.abs(a.yDomain[1] - b.yDomain[1]) < 0.01;
  const overlayOf = (g: number): "none" | "right" | "top" => {
    const gi = grids[g];
    const prior = grids.findIndex((o, oi) => oi < g && sameRect(gi, o));
    if (prior === -1) return "none";
    return gi.xIndex === grids[prior].xIndex ? "right" : "top";
  };
  const xAxisOptions = xInstances.map((inst, i) => buildAxis(inst.info, inst.gridIndex, overlayOf(i)));
  const yAxisOptions = yInstances.map((inst, i) => buildAxis(inst.info, inst.gridIndex, overlayOf(i)));

  // resolve axis-fraction annotation coordinates against the final extents;
  // a fraction without a real extent can't be placed — drop the point. Log
  // extents interpolate in log space (a linear fraction of a log window
  // would land the annotation on the wrong side of the axis).
  for (const [g, points] of annPointsByGrid) {
    annPointsByGrid.set(
      g,
      points.filter((p) => {
        if (p.yFraction) {
          const ext = yExtents.get(p.yFraction.index);
          if (!ext) return false;
          p.y =
            p.yFraction.log && ext.min > 0
              ? ext.min * Math.pow(ext.max / ext.min, p.yFraction.frac)
              : ext.min + p.yFraction.frac * (ext.max - ext.min);
        }
        if (p.xFraction) {
          const ext = xExtents.get(p.xFraction.index);
          if (!ext) return false;
          p.x =
            p.xFraction.log && ext.min > 0
              ? ext.min * Math.pow(ext.max / ext.min, p.xFraction.frac)
              : ext.min + p.xFraction.frac * (ext.max - ext.min);
        }
        return true;
      }),
    );
  }

  // --- outside bar value labels must fit their slot (mobile) --------------------
  for (const draft of series) {
    if (draft.type !== "bar" || !Array.isArray(draft.data) || draft.data.length === 0) continue;
    const g = grids[draft.gridIndex ?? 0];
    if (!g) continue;
    const n = draft.data.length;
    for (const item of draft.data as Array<{ label?: { position?: string; show?: boolean; formatter?: string; fontSize?: number } }>) {
      if (!item.label || item.label.show === false || !item.label.formatter) continue;
      const estW = item.label.formatter.length * (item.label.fontSize ?? 12) * 0.62;
      if (item.label.position === "right") {
        if (g.height / n < estW * 0.92) item.label.show = false;
      } else if (item.label.position === "top") {
        if (g.width / n < estW * 0.92) item.label.show = false;
      }
    }
  }

  // --- data-unit bar widths → px via the data span of the x-axis -------------
  const plotWidthOf = (gridIndex: number): number => grids[gridIndex]?.width ?? innerWpx;
  for (const draft of series) {
    const binWidth = draft.__binWidth;
    const barWidthData = draft.__barWidthData;
    if (typeof binWidth !== "number" && typeof barWidthData !== "number") continue;
    const ext = xExtents.get(draft.xIdx);
    const span = ext ? ext.max - ext.min : 0;
    const dataWidth = typeof binWidth === "number" ? binWidth : (barWidthData as number);
    draft.barWidth = span > 0 ? (dataWidth / span) * plotWidthOf(draft.gridIndex ?? 0) : undefined;
    delete draft.__binWidth;
    delete draft.__barWidthData;
  }

  // --- plotly barmode overlay → stacked z (negative gap) ------------------------
  if (layout.barmode === "overlay") {
    for (const draft of series) {
      if (draft.type === "bar") draft.barGap = "-100%";
    }
  }

  // --- annotation + shape layers ---------------------------------------------------
  // ECharts clips markers/labels/markLines sitting exactly on the autoscale
  // boundary (the annotation at x=0 IS the axis max), so each edge annotation
  // contributes a label-less invisible nudge point that pushes the axis ~7%
  // past it — the breathing room plotly's autorange margin provides. Outside
  // bar value labels get the same headroom above the tallest bar.
  const nudgePast = (ext: { min: number; max: number } | null | undefined, v: number): number | null => {
    if (!ext) return null;
    const span = ext.max - ext.min;
    if (!(span > 0)) return null;
    const center = (ext.min + ext.max) / 2;
    const dir = v >= center ? 1 : -1;
    const nearEdge = dir > 0 ? v >= ext.max - span * 0.02 : v <= ext.min + span * 0.02;
    return nearEdge ? v + dir * span * 0.07 : null;
  };
  // grids that need bar-label headroom: axis index → the grid that owns it
  const headroomByGrid = new Map<number, { isX: boolean; value: number }>();
  for (const key of labelHeadroomAxes) {
    const [axis, idxStr] = key.split(":");
    const idx = Number(idxStr);
    const ext = (axis === "x" ? xExtents : yExtents).get(idx);
    if (!ext) continue;
    const span = ext.max - ext.min || Math.abs(ext.max) || 1;
    const value = ext.max + span * 0.16;
    const gridIndex = grids.findIndex((g) => (axis === "x" ? g.xIndex : g.yIndex) === idx);
    if (gridIndex >= 0) headroomByGrid.set(gridIndex, { isX: axis === "x", value });
  }
  for (let g = 0; g < grids.length; g++) {
    const points = annPointsByGrid.get(g) ?? [];
    const lines = shapeLines.filter((s) => s.gridIndex === g);
    const rects = shapeRects.filter((s) => s.gridIndex === g);
    const headroom = headroomByGrid.get(g);
    if (points.length === 0 && lines.length === 0 && rects.length === 0 && !headroom) continue;
    const layer = annotationLayer(grids[g].xIndex, grids[g].yIndex, points, lines, rects);
    const xExt = xExtents.get(grids[g].xIndex);
    const yExt = yExtents.get(grids[g].yIndex);
    const extras: unknown[] = [];
    const pushNudge = (x: number | null, y: number | null) => {
      const nx = x === null ? null : nudgePast(xExt, x);
      const ny = y === null ? null : nudgePast(yExt, y);
      if (nx === null && ny === null) return;
      const cx = x === null ? ((xExt?.min ?? 0) + (xExt?.max ?? 1)) / 2 : xExt ? Math.min(Math.max(x, xExt.min), xExt.max) : x;
      const cy = y === null ? ((yExt?.min ?? 0) + (yExt?.max ?? 1)) / 2 : yExt ? Math.min(Math.max(y, yExt.min), yExt.max) : y;
      extras.push({ value: [nx ?? cx, ny ?? cy] });
    };
    for (const p of points) pushNudge(p.x, p.y);
    for (const s of lines) {
      // a vertical line only needs horizontal breathing room (and vice versa);
      // nudging the spanning axis would distort the bar scale
      pushNudge(s.vertical ? s.value : null, s.vertical ? null : s.value);
    }
    if (headroom) pushNudge(headroom.isX ? headroom.value : null, headroom.isX ? null : headroom.value);
    layer.data = [...layer.data, ...extras];
    series.push(layer);
  }

  // --- titles -------------------------------------------------------------------------
  // Main title centered on the canvas, occupying its own band; each subplot
  // header centered over its grid rect, sitting in the reserved band above
  // it so a series at its max can never touch it.
  const titles: Record<string, unknown>[] = [];
  if (titleParts) {
    // shrink an over-long title block so it never clips at the card edge
    const estW = Math.max(
      titleParts.text.length * titleParts.size * 0.6,
      titleParts.subtext.length * titleParts.subSize * 0.6,
    );
    const fit = estW > width * 0.94 ? (width * 0.94) / estW : 1;
    titles.push({
      text: titleParts.text,
      subtext: titleParts.subtext,
      left: Math.round(width / 2),
      top: Math.max(4, Math.round((topBand - mainTitleBlock - subTitleBand) / 2)),
      textAlign: "center",
      subtextAlign: "center",
      textStyle: {
        color: titleParts.color,
        fontSize: Math.max(11, Math.round(titleParts.size * fit * 10) / 10),
        fontWeight: "normal",
      },
      subtextStyle: {
        color: titleParts.subColor,
        fontSize: Math.max(9, Math.round(titleParts.subSize * fit * 10) / 10),
      },
    });
  }
  for (const [g, sub] of subTitleByGrid) {
    const grid = grids[g];
    const metrics = subMetrics.get(g);
    if (!grid || !metrics) continue;
    titles.push({
      text: metrics.text,
      left: Math.round(grid.left + grid.width / 2),
      top: Math.round(grid.top - metrics.lines * (metrics.fontSize + 3) - 4),
      textAlign: "center",
      textStyle: { color: sub.color, fontSize: metrics.fontSize, fontWeight: "normal" },
    });
  }

  // --- legend ---------------------------------------------------------------------------
  const legendFont = asRecord(rawLegend.font);
  let legend: Record<string, unknown> | undefined;
  if (showLegend) {
    const ly = num(rawLegend.y) ?? 1;
    const yanchor = typeof rawLegend.yanchor === "string" ? rawLegend.yanchor : "top";
    const legendH = namedSeries.length * 21 + 8;
    const top =
      topBand + (1 - ly) * innerHpx - (yanchor === "middle" ? legendH / 2 : yanchor === "bottom" ? legendH : 0);
    legend = {
      show: true,
      orient: legendOrient,
      data: namedSeries,
      left: Math.round(width - rightBand + 6),
      top: Math.round(Math.max(topBand, top)),
      textStyle: {
        color: chromeColor(legendFont.color, palette.textColor, theme),
        fontSize: num(legendFont.size) ?? 12,
      },
      borderWidth: 0,
      backgroundColor: "transparent",
      inactiveColor: palette.gridColor,
    };
  }

  // --- series axis indices + assemble ------------------------------------------------------
  for (const draft of series) {
    if (draft.type === "funnel") continue; // not cartesian
    draft.xAxisIndex = Math.max(
      0,
      xInstances.findIndex((inst) => inst.gridIndex === draft.gridIndex),
    );
    draft.yAxisIndex = Math.max(
      0,
      yInstances.findIndex((inst) => inst.gridIndex === draft.gridIndex),
    );
  }
  const dataSeries = series.filter((s) => !s.silent);
  const cartesianSeries = dataSeries.filter((s) => s.type !== "funnel");
  const totalPoints = cartesianSeries.reduce(
    (n, s) => n + (Array.isArray(s.data) ? (s.data as unknown[]).length : 0),
    0,
  );
  const allScatter =
    cartesianSeries.length > 0 && cartesianSeries.every((s) => s.type === "scatter");
  const allHeatmap =
    cartesianSeries.length > 0 && cartesianSeries.every((s) => s.type === "heatmap");
  // dense scatter clouds (temp_vs_rentals: seasons x thousands of rows) bury
  // the reader in whole-x-bin dumps under an axis trigger — report the
  // single nearest point instead; pure heatmaps use a cell tooltip; line/bar
  // charts keep the axis trigger with the capped grouped formatter
  const itemTrigger = (allScatter && totalPoints > 500) || allHeatmap;
  const itemFormatter = allHeatmap ? formatHeatmapItem : formatScatterItem;
  const option: Record<string, unknown> = {
    backgroundColor: "rgba(0,0,0,0)",
    textStyle: { fontFamily, color: baseColor, fontSize },
    title: titles,
    grid: grids.map((g) => ({
      left: Math.round(g.left),
      top: Math.round(g.top),
      width: Math.round(g.width),
      height: Math.round(g.height),
      containLabel: false,
    })),
    xAxis: xAxisOptions,
    yAxis: yAxisOptions,
    series,
    tooltip: {
      confine: true,
      trigger: cartesianSeries.length === 0 || itemTrigger ? "item" : "axis",
      backgroundColor: HOVER_BG,
      borderColor: HOVER_BORDER,
      textStyle: { color: HOVER_TEXT, fontSize: 12, fontFamily },
      axisPointer: { type: "line", lineStyle: { color: palette.axisLineColor } },
      formatter: itemTrigger ? itemFormatter : formatAxisTooltip,
    },
  };
  if (legend) option.legend = legend;
  if (heatmapVisual) {
    option.visualMap = {
      type: "continuous",
      min: heatmapVisual.min,
      max: heatmapVisual.max,
      // every cartesian heatmap series draws its colors from the visualMap
      seriesIndex: series.map((s, i) => (s.type === "heatmap" ? i : -1)).filter((i) => i !== -1),
      orient: "vertical",
      right: 6,
      top: "middle",
      calculable: false,
      inRange: { color: heatmapVisual.colors },
      textStyle: { color: palette.textColor, fontSize: 11 },
      // the plotly colorbar title becomes the legend's top-end label
      ...(heatmapVisual.title
        ? { text: [heatmapVisual.title, formatTick(heatmapVisual.min)] }
        : {}),
    };
  }
  return option as unknown as EChartsOption;
}

/**
 * True only when every trace/axis/shape in the payload is inside the pilot
 * subset the converter implements; the caller renders plotly otherwise.
 * Conversion is cheap (small committed figures), so this simply attempts it.
 */
export function supportsECharts(payload: PlotlyPayload): boolean {
  try {
    plotlyToECharts(payload, "dark");
    return true;
  } catch {
    return false;
  }
}
