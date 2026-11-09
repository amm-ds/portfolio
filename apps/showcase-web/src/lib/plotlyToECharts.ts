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
  HeatmapSeriesOption,
  LineSeriesOption,
  ScatterSeriesOption,
} from "echarts/charts";
import type {
  GridComponentOption,
  LegendComponentOption,
  TitleComponentOption,
  TooltipComponentOption,
  VisualMapComponentOption,
} from "echarts/components";

/**
 * Apache ECharts pilot: convert committed plotly figure payloads (the subset
 * the 05-ml-pipeline-churn figures actually use — scatter/line, bar,
 * histogram, heatmap on linear or category axes, line shapes and text
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
  | HeatmapSeriesOption
  | LineSeriesOption
  | ScatterSeriesOption
  | GridComponentOption
  | LegendComponentOption
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
      const n = num(e);
      if (n === undefined) fail(`${what} holds a non-numeric value`);
      return n;
    });
  }
  const rec = asRecord(v);
  if ("bdata" in rec) return decodeBdata(rec);
  fail(`${what} is not an array`);
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
  type: "value" | "category";
  categories: string[];
  built: Record<string, unknown> | null;
}

interface GridInfo {
  xIndex: number;
  yIndex: number;
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
  err: number[];
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
  yFraction?: { index: number; frac: number };
}

interface ShapeLine {
  gridIndex: number;
  vertical: boolean;
  value: number;
  color: string;
  width: number;
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
      data: shapes.map((s) => {
        const item: Record<string, unknown> = s.vertical ? { xAxis: s.value } : { yAxis: s.value };
        item.lineStyle = { color: s.color, width: s.width, type: "solid" };
        return item;
      }),
    };
  }
  return layer;
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
  const innerW = designW - margin.l - margin.r;
  const innerH = height / scale - margin.t - margin.b;

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
      declared !== "category"
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
      type: declared === "category" ? "category" : "value",
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

  // --- grids: one per (xIdx, yIdx) pair, positioned from axis domains -----
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
    grids.push({
      xIndex: xIdx,
      yIndex: yIdx,
      left: (margin.l + xDomain[0] * innerW) * scale,
      top: (margin.t + (1 - yDomain[1]) * innerH) * scale,
      width: (xDomain[1] - xDomain[0]) * innerW * scale,
      height: (yDomain[1] - yDomain[0]) * innerH * scale,
    });
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
  let heatmapVisual: { min: number; max: number; colors: string[] } | null = null;
  let heatmapCount = 0;

  const traceColor = (i: number, explicit: unknown): string => {
    const raw =
      typeof explicit === "string"
        ? explicit
        : colorway.length > 0
          ? colorway[i % colorway.length]
          : "#2dd4bf";
    return remapColor(raw, theme);
  };
  const xAdd = (idx: number, v: number | undefined) =>
    xExtents.set(idx, extentAdd(xExtents.get(idx) ?? null, v));
  const yAdd = (idx: number, v: number | undefined) =>
    yExtents.set(idx, extentAdd(yExtents.get(idx) ?? null, v));
  const registerCategory = (info: AxisInfo, label: string) => {
    if (!info.categories.includes(label)) info.categories.push(label);
  };

  for (let i = 0; i < data.length; i++) {
    const t = asRecord(data[i]);
    const type = typeof t.type === "string" ? t.type : "scatter";
    if (type !== "scatter" && type !== "bar" && type !== "histogram" && type !== "heatmap") {
      fail(`unsupported trace type "${type}"`);
    }
    const xIdx = axisRefIndex(t.xaxis, "x");
    const yIdx = axisRefIndex(t.yaxis, "y");
    const gridIndex = gridIndexFor(xIdx, yIdx);
    const name = typeof t.name === "string" && t.name !== "" ? t.name : undefined;
    if (name && !namedSeries.includes(name)) namedSeries.push(name);
    const marker = asRecord(t.marker);
    const line = asRecord(t.line);

    if (type === "scatter") {
      const xs = toValueArray(t.x, "scatter.x");
      const ys = toValueArray(t.y, "scatter.y");
      const n = Math.max(xs.length, ys.length);
      if (n === 0) fail("scatter trace without x/y data");
      const mode = typeof t.mode === "string" ? t.mode : "lines";
      if (!SCATTER_MODE_RE.test(mode)) fail(`unsupported scatter mode "${mode}"`);
      const hasLines = mode.includes("lines");
      const hasMarkers = mode.includes("markers") || (!hasLines && !mode.includes("text"));
      const hasText = mode.includes("text");
      const lineColor = traceColor(i, line.color);
      const markerColor = traceColor(i, typeof marker.color === "string" ? marker.color : line.color);
      const xInfo = axisAt(true, xIdx);
      const points: unknown[] = [];
      for (let k = 0; k < n; k++) {
        const xv = xs.length > 0 ? xs[Math.min(k, xs.length - 1)] : k;
        const yv = ys.length > 0 ? ys[Math.min(k, ys.length - 1)] : k;
        if (typeof xv === "string") {
          xInfo.type = "category";
          registerCategory(xInfo, xv);
        } else {
          xAdd(xIdx, xv);
        }
        const yn = typeof yv === "string" ? fail("scatter.y holds categories") : yv;
        yAdd(yIdx, yn);
        const item: Record<string, unknown> = {
          value: [xv, Number.isFinite(yn) ? yn : null],
        };
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
        const symbol = typeof marker.symbol === "string" ? SYMBOL_MAP[marker.symbol] : undefined;
        if (marker.symbol !== undefined && !symbol) {
          fail(`unsupported marker.symbol "${String(marker.symbol)}"`);
        }
        draft.symbol = symbol ?? "circle";
        if (Array.isArray(marker.size)) {
          const sizes = marker.size.map((s) => num(s) ?? 6);
          draft.symbolSize = (_value: unknown, params: { dataIndex: number }) =>
            sizes[params.dataIndex] ?? 6;
        } else {
          draft.symbolSize = num(marker.size) ?? 6;
        }
        draft.itemStyle = { color: markerColor };
        // markers on the data edge stay fully painted (plotly parity)
        draft.clip = false;
      } else if (hasText) {
        draft.itemStyle = { color: lineColor };
      }
      series.push(draft);
    } else if (type === "bar") {
      const horizontal = t.orientation === "h";
      const cat = toValueArray(horizontal ? t.y : t.x, "bar.category");
      const vals = toNumberArray(horizontal ? t.x : t.y, "bar.values");
      const n = Math.max(cat.length, vals.length);
      if (n === 0) fail("bar trace without x/y data");
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
      for (let k = 0; k < n; k++) {
        const catV = cat.length > 0 ? cat[Math.min(k, cat.length - 1)] : k;
        const val = vals.length > 0 ? vals[Math.min(k, vals.length - 1)] : 0;
        if (catAxis.type === "category") {
          registerCategory(catAxis, String(catV));
        } else {
          (horizontal ? yAdd : xAdd)(horizontal ? yIdx : xIdx, Number(catV));
        }
        (horizontal ? xAdd : yAdd)(horizontal ? xIdx : yIdx, val);
        (horizontal ? xAdd : yAdd)(horizontal ? xIdx : yIdx, 0); // bar baseline pins zero
        const catLabel = catAxis.type === "category" ? String(catV) : Number(catV);
        const item: Record<string, unknown> = {
          value: horizontal ? [val, catLabel] : [catLabel, val],
        };
        if (perColors) {
          item.itemStyle = { color: perColors[k % perColors.length], opacity: opacity ?? 1 };
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
        const errs = toNumberArray(err.array, `${key}.array`);
        errorBars.push({
          gridIndex,
          xIdx,
          yIdx,
          horizontal: key === "error_x",
          category: cat,
          center: vals,
          err: errs,
          color,
        });
      }
    } else if (type === "histogram") {
      if (t.orientation === "h") fail("horizontal histogram unsupported");
      const values = toNumberArray(t.x, "histogram.x");
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
      // heatmap
      const xs = toNumberArray(t.x, "heatmap.x");
      const ys = toNumberArray(t.y, "heatmap.y");
      const zRaw = t.z;
      if (!Array.isArray(zRaw) || zRaw.length === 0 || !Array.isArray(zRaw[0])) {
        fail("heatmap.z is not a 2D array");
      }
      const z = zRaw as unknown[][];
      if (z.length !== ys.length || z.some((row) => !Array.isArray(row) || row.length !== xs.length)) {
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
      const items: unknown[] = [];
      let zMin = Infinity;
      let zMax = -Infinity;
      for (let j = 0; j < ys.length; j++) {
        for (let k = 0; k < xs.length; k++) {
          const zv = num(z[j][k]);
          if (zv === undefined) fail("heatmap.z holds a non-numeric value");
          xAdd(xIdx, xs[k]);
          yAdd(yIdx, ys[j]);
          zMin = Math.min(zMin, zv);
          zMax = Math.max(zMax, zv);
          items.push({ value: [xs[k], ys[j], zv] });
        }
      }
      series.push({ type: "heatmap", name, gridIndex, xIdx, yIdx, data: items, z: 1 });
      heatmapVisual = { min: zMin, max: zMax, colors };
      heatmapCount += 1;
    }
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
      const err = plan.err[Math.min(k, plan.err.length - 1)];
      if (!Number.isFinite(plan.center[k]) || !Number.isFinite(err)) continue;
      items.push({
        value: plan.horizontal
          ? [plan.center[k], plan.category[Math.min(k, plan.category.length - 1)], err]
          : [plan.category[Math.min(k, plan.category.length - 1)], plan.center[k], err],
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
          const hi = api.coord([api.value(0) + api.value(2), api.value(1)]);
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
        const hi = api.coord([api.value(0), api.value(1) + api.value(2)]);
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
  const subplotTitles: Record<string, unknown>[] = [];
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
      // subplot header positioned in paper (domain) coordinates, just inside
      // the top of its grid — the way plotly anchors y=1, yanchor=bottom
      subplotTitles.push({
        text,
        left: Math.round((margin.l + (num(a.x) ?? 0.5) * innerW) * scale),
        top: Math.round((margin.t + (1 - (num(a.y) ?? 1)) * innerH) * scale + 4),
        textStyle: {
          color: chromeColor(font.color, palette.textColor, theme),
          fontSize,
          fontWeight: "normal",
        },
      });
      continue;
    }
    const xIdx = xref.startsWith("x") ? axisRefIndex(xref, "x") : null;
    const yIdx = yref.startsWith("y") && yref !== "paper" ? axisRefIndex(yref, "y") : null;
    const yIsDomain = yref.endsWith(" domain");
    const xVal = num(a.x);
    if (xIdx === null || xVal === undefined) continue;
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
    if (yIsDomain) {
      point.yFraction = { index: yIdx ?? 0, frac: num(a.y) ?? 1 };
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
  for (const raw of shapes) {
    const s = asRecord(raw);
    if (s.type !== "line") fail(`unsupported shape type "${String(s.type)}"`);
    const lineStyle = asRecord(s.line);
    const color = remapColor(
      typeof lineStyle.color === "string" ? lineStyle.color : palette.textColor,
      theme,
    );
    const width = num(lineStyle.width) ?? 2;
    const xIdx = axisRefIndex(s.xref, "x");
    const yIdx = axisRefIndex(s.yref, "y");
    const gridIndex = gridIndexFor(xIdx, yIdx);
    const x0 = num(s.x0);
    const x1 = num(s.x1);
    const y0 = num(s.y0);
    const y1 = num(s.y1);
    if (x0 !== undefined && x0 === x1) {
      shapeLines.push({ gridIndex, vertical: true, value: x0, color, width });
      xAdd(xIdx, x0);
    } else if (y0 !== undefined && y0 === y1) {
      shapeLines.push({ gridIndex, vertical: false, value: y0, color, width });
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
    info.gridIndex = gridIndexFor(info.index, info.index);
  });
  yInfos.forEach((info, i) => {
    info.arrayIndex = i;
    info.gridIndex = gridIndexFor(info.index, info.index);
  });

  const buildAxis = (info: AxisInfo): Record<string, unknown> => {
    const extents = info.isX ? xExtents : yExtents;
    const exactSet = info.isX ? exactX : exactY;
    const ext = extents.get(info.index) ?? null;
    const rawTick = asRecord(info.raw.tickfont);
    const titleFont = asRecord(asRecord(info.raw.title).font);
    const titleText = (() => {
      const t = info.raw.title;
      if (typeof t === "string") return t;
      const inner = asRecord(t).text;
      return typeof inner === "string" ? inner : null;
    })();
    const axisLabel: Record<string, unknown> = {
      color: chromeColor(rawTick.color, palette.textColor, theme),
      fontSize: num(rawTick.size) ?? fontSize - 2,
    };
    if (info.type === "category") {
      // long slice labels (e.g. "contract=month-to-month") get angled +
      // downsized so they fit their subplot slot instead of colliding with
      // the neighbor
      axisLabel.rotate = 30;
      axisLabel.fontSize = 10;
      axisLabel.margin = 6;
    }
    const opt: Record<string, unknown> = {
      type: info.type,
      gridIndex: info.gridIndex,
      axisLine: { lineStyle: { color: chromeColor(info.raw.linecolor, palette.axisLineColor, theme) } },
      axisTick: { show: false },
      splitLine: {
        show: true,
        lineStyle: { color: chromeColor(info.raw.gridcolor, palette.gridColor, theme) },
      },
      axisLabel,
    };
    if (info.type === "value" && ext && exactSet.has(info.index) && ext.min === 0) {
      // bar/histogram baselines must sit at zero; the open end is left to
      // echarts' autoscale so its ticks land on nice numbers (plotly parity:
      // setting an explicit data-derived max makes the raw extent a tick)
      opt.min = 0;
    }
    if (info.type === "category") {
      opt.data = info.categories;
    }
    if (titleText) {
      opt.name = titleText;
      opt.nameLocation = "middle";
      opt.nameGap = info.isX ? 30 : 42;
      opt.nameTextStyle = { color: chromeColor(titleFont.color, palette.textColor, theme) };
    }
    return opt;
  };
  for (const info of xInfos) info.built = buildAxis(info);
  for (const info of yInfos) info.built = buildAxis(info);

  // resolve axis-fraction annotation y values against the final y extents
  for (const points of annPointsByGrid.values()) {
    for (const p of points) {
      if (p.yFraction) {
        const ext = yExtents.get(p.yFraction.index) ?? { min: 0, max: 1 };
        p.y = ext.min + p.yFraction.frac * (ext.max - ext.min);
      }
    }
  }

  // --- data-unit bar widths → px via the data span of the x-axis -------------
  const plotWidthOf = (gridIndex: number): number => grids[gridIndex]?.width ?? innerW * scale;
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
  // past it — the breathing room plotly's autorange margin provides.
  const nudgePast = (ext: { min: number; max: number } | null | undefined, v: number): number | null => {
    if (!ext) return null;
    const span = ext.max - ext.min;
    if (!(span > 0)) return null;
    const center = (ext.min + ext.max) / 2;
    const dir = v >= center ? 1 : -1;
    const nearEdge = dir > 0 ? v >= ext.max - span * 0.02 : v <= ext.min + span * 0.02;
    return nearEdge ? v + dir * span * 0.07 : null;
  };
  for (let g = 0; g < grids.length; g++) {
    const points = annPointsByGrid.get(g) ?? [];
    const lines = shapeLines.filter((s) => s.gridIndex === g);
    if (points.length === 0 && lines.length === 0) continue;
    const layer = annotationLayer(grids[g].xIndex, grids[g].yIndex, points, lines);
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
    layer.data = [...layer.data, ...extras];
    series.push(layer);
  }

  // --- titles -------------------------------------------------------------------------
  const titleParts = (() => {
    const t = asRecord(layout.title);
    const text = typeof t.text === "string" ? t.text : null;
    if (text === null) return null;
    const parts = text.split(BR_RE).map(stripTags);
    const titleFont = asRecord(t.font);
    const subMatch = INLINE_COLOR_RE.exec(text);
    const subColorRaw = subMatch ? `#${subMatch[1]}` : SUBTEXT_COLOR_DARK;
    return {
      text: parts[0],
      subtext: parts.slice(1).join("\n"),
      color: chromeColor(titleFont.color, palette.textColor, theme),
      size: num(titleFont.size) ?? 16,
      subColor:
        theme === "light"
          ? (LIGHT_TRACE_COLOR_MAP[subColorRaw.toLowerCase()] ?? SUBTEXT_COLOR_LIGHT)
          : subColorRaw,
    };
  })();
  const titles: Record<string, unknown>[] = [];
  if (titleParts) {
    titles.push({
      text: titleParts.text,
      subtext: titleParts.subtext,
      left: "center",
      top: 6,
      textStyle: { color: titleParts.color, fontSize: titleParts.size, fontWeight: "normal" },
      subtextStyle: { color: titleParts.subColor, fontSize: Math.min(13, titleParts.size - 3.5) },
    });
  }
  titles.push(...subplotTitles);

  // --- legend ---------------------------------------------------------------------------
  const rawLegend = asRecord(layout.legend);
  const showLegend = (layout.showlegend ?? tpl.showlegend ?? true) !== false;
  const legendFont = asRecord(rawLegend.font);
  let legend: Record<string, unknown> | undefined;
  if (showLegend && namedSeries.length > 0) {
    const lx = num(rawLegend.x) ?? 1.02;
    const ly = num(rawLegend.y) ?? 1;
    legend = {
      show: true,
      orient: rawLegend.orientation === "h" ? "horizontal" : "vertical",
      data: namedSeries,
      left: Math.round((margin.l + lx * innerW) * scale),
      top: Math.round((margin.t + (1 - ly) * innerH) * scale),
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
  const xArrayIndex = (idx: number) => xInfos.find((i) => i.index === idx)?.arrayIndex ?? 0;
  const yArrayIndex = (idx: number) => yInfos.find((i) => i.index === idx)?.arrayIndex ?? 0;
  for (const draft of series) {
    draft.xAxisIndex = xArrayIndex(draft.xIdx);
    draft.yAxisIndex = yArrayIndex(draft.yIdx);
  }
  const dataSeries = series.filter((s) => !s.silent);
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
    xAxis: xInfos.map((i) => i.built),
    yAxis: yInfos.map((i) => i.built),
    series,
    tooltip: {
      confine: true,
      trigger: heatmapCount > 0 && dataSeries.length - heatmapCount === 0 ? "item" : "axis",
      backgroundColor: HOVER_BG,
      borderColor: HOVER_BORDER,
      textStyle: { color: HOVER_TEXT, fontSize: 12, fontFamily },
      axisPointer: { type: "line", lineStyle: { color: palette.axisLineColor } },
    },
  };
  if (legend) option.legend = legend;
  if (heatmapVisual) {
    option.visualMap = {
      type: "continuous",
      min: heatmapVisual.min,
      max: heatmapVisual.max,
      seriesIndex: series.findIndex((s) => s.type === "heatmap"),
      orient: "vertical",
      right: Math.round(margin.r * scale * 0.35),
      top: "middle",
      calculable: false,
      inRange: { color: heatmapVisual.colors },
      textStyle: { color: palette.textColor, fontSize: 11 },
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
