import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  plotlyToECharts,
  supportsECharts,
  type EChartsOption,
} from "../lib/plotlyToECharts";
import type { PlotlyPayload } from "../components/PlotlyFigure";

/**
 * Converter gate: run plotlyToECharts over the REAL committed churn payloads
 * (read straight from projects/05-ml-pipeline-churn/reports/figures) so the
 * pilot contract is proven against production data, not hand-written mocks.
 */

// vitest runs with the package as cwd: ../../ lands on the repo root.
const FIGURES_DIR = resolve(process.cwd(), "../../projects/05-ml-pipeline-churn/reports/figures");

const FIGURE_NAMES = [
  "calibration_curve",
  "business_cost_curve",
  "cost_surface",
  "decision_curve",
  "eda_churn_profile",
  "fairness_slices",
  "permutation_importance",
  "precision_recall_curve",
  "bootstrap_ci",
] as const;

function loadFigure(name: string): PlotlyPayload {
  return JSON.parse(readFileSync(resolve(FIGURES_DIR, `${name}.json`), "utf8")) as PlotlyPayload;
}

/** Loose view into the assembled option for assertions. */
interface Opt {
  series: Array<Record<string, any>>;
  xAxis: Array<Record<string, any>>;
  yAxis: Array<Record<string, any>>;
  grid: Array<Record<string, any>>;
  legend: Record<string, any>;
  visualMap: Record<string, any>;
  title: Array<Record<string, any>>;
  tooltip: Record<string, any>;
}

function asOpt(option: EChartsOption): Opt {
  return option as unknown as Opt;
}

/** ECharts type for each plotly trace in the payload (data series only). */
function expectedSeriesTypes(payload: PlotlyPayload): string[] {
  return payload.data.map((raw) => {
    const t = raw as Record<string, any>;
    if (t.type === "bar") return "bar";
    if (t.type === "histogram") return "bar";
    if (t.type === "heatmap") return "heatmap";
    const mode = typeof t.mode === "string" ? t.mode : "lines";
    return mode.includes("lines") ? "line" : "scatter";
  });
}

describe("plotlyToECharts over the committed churn figures", () => {
  for (const name of FIGURE_NAMES) {
    it(`converts ${name} (supported, series match the plotly traces)`, () => {
      const payload = loadFigure(name);
      expect(supportsECharts(payload)).toBe(true);
      const option = asOpt(plotlyToECharts(payload, "dark"));
      const dataSeries = option.series.filter((s) => !s.silent);
      expect(dataSeries.map((s) => s.type)).toEqual(expectedSeriesTypes(payload));
      expect(option.xAxis.length).toBeGreaterThan(0);
      expect(option.yAxis.length).toBeGreaterThan(0);
    });
  }

  it("never mutates the fetched payload", () => {
    for (const name of FIGURE_NAMES) {
      const payload = loadFigure(name);
      const snapshot = JSON.stringify(payload);
      plotlyToECharts(payload, "dark");
      plotlyToECharts(payload, "light");
      expect(JSON.stringify(payload)).toBe(snapshot);
    }
  });

  it("decodes plotly's base64 typed arrays into point coordinates", () => {
    const option = asOpt(plotlyToECharts(loadFigure("calibration_curve"), "dark"));
    const raw = option.series[1]; // selected model (raw): bdata x/y
    const first = raw.data[0].value;
    const last = raw.data[raw.data.length - 1].value;
    expect(first[0]).toBeGreaterThan(0);
    expect(first[0]).toBeLessThan(0.2);
    expect(last[0]).toBeGreaterThan(0.8);
    expect(last[0]).toBeLessThanOrEqual(1);
    for (const point of raw.data) {
      expect(Number.isFinite(point.value[0])).toBe(true);
      expect(Number.isFinite(point.value[1])).toBe(true);
    }
  });

  it("resolves colorway colors for traces without an explicit color (dark keeps, light remaps)", () => {
    const dark = asOpt(plotlyToECharts(loadFigure("calibration_curve"), "dark"));
    // trace 1 has no explicit color → colorway[1]; dark preserves the authored palette
    expect(dark.series[1].lineStyle.color).toBe("#38bdf8");
    const light = asOpt(plotlyToECharts(loadFigure("calibration_curve"), "light"));
    expect(light.series[1].lineStyle.color).toBe("#0284c7");
    // explicit authored colors remap too (same table as reskinTraces)
    expect(dark.series[0].lineStyle.color).toBe("#64748b");
    expect(light.series[0].lineStyle.color).toBe("#475569");
  });

  it("themes the legend and tooltip chrome per site palette in light mode", () => {
    const dark = asOpt(plotlyToECharts(loadFigure("business_cost_curve"), "dark"));
    expect(dark.legend.textStyle.color).toBe("#e2e8f0");
    const light = asOpt(plotlyToECharts(loadFigure("business_cost_curve"), "light"));
    expect(light.legend.textStyle.color).toBe("#172433");
    expect(light.tooltip.textStyle.color).toBe("#0f172a");
    // grid/splitLine chrome follows the theme palette
    expect(light.xAxis[0].splitLine.lineStyle.color).toBe("rgba(78,98,118,0.22)");
  });

  it("renders histogram densities that integrate to 1 (probability density histnorm)", () => {
    const payload = loadFigure("eda_churn_profile");
    const option = asOpt(plotlyToECharts(payload, "dark"));
    const hists = option.series.filter((s) => s.type === "bar" && s.barWidth !== undefined);
    expect(hists).toHaveLength(4);
    for (const h of hists) {
      const xs = h.data.map((d: { value: number[] }) => d.value[0]);
      const ys = h.data.map((d: { value: number[] }) => d.value[1]);
      for (const y of ys) expect(Number.isFinite(y)).toBe(true);
      const binWidth = xs[1] - xs[0];
      expect(binWidth).toBeGreaterThan(0);
      const mass = ys.reduce((a: number, y: number) => a + y * binWidth, 0);
      expect(mass).toBeCloseTo(1, 2);
    }
    // shared edges: both densities on the same subplot bin identically
    const left = hists.filter((h) => h.xAxisIndex === 1);
    expect(left).toHaveLength(2);
    expect(left[0].data.map((d: { value: number[] }) => d.value[0])).toEqual(
      left[1].data.map((d: { value: number[] }) => d.value[0]),
    );
  });

  it("renders a count histogram whose bins sum to the trace count when histnorm is unset", () => {
    const payload: PlotlyPayload = {
      data: [{ type: "histogram", x: [1, 2, 2, 3, 3, 3, 7] }],
      layout: { height: 560 },
    };
    expect(supportsECharts(payload)).toBe(true);
    const option = asOpt(plotlyToECharts(payload, "dark"));
    const hist = option.series.find((s) => s.type === "bar")!;
    const total = hist.data.reduce((a: number, d: { value: number[] }) => a + d.value[1], 0);
    expect(total).toBe(7);
    for (const d of hist.data.map((x: { value: number[] }) => x.value[1])) {
      expect(Number.isFinite(d)).toBe(true);
    }
  });

  it("sets the count-histogram y-extent from the bin counts (regression: axis pinned to [0,1])", () => {
    // 01's real latency histogram: 65 latencies, peak bin count well above 1.
    // Wave-18 viewer report: "bars are 100% in all cases, chart irrelevant" —
    // the trace-parse branch only pinned the zero baseline, so the exact-axis
    // extent resolved {0,0} → max 1 and every count clipped to full height.
    const payload = JSON.parse(
      readFileSync(
        resolve(process.cwd(), "../../projects/01-rag-agent/reports/figures/latency_histogram.json"),
        "utf8",
      ),
    ) as PlotlyPayload;
    const option = asOpt(plotlyToECharts(payload, "dark"));
    const hist = option.series.find((s) => s.type === "bar")!;
    const maxCount = Math.max(...hist.data.map((d: { value: number[] }) => d.value[1]));
    expect(maxCount).toBeGreaterThan(1);
    expect(option.yAxis[0].max).toBeGreaterThan(maxCount);
    expect(option.yAxis[0].max).toBeLessThanOrEqual(maxCount * 1.2);
  });

  it("anchors funnels below the two-line title band (regression: subtitle overlapped stage 1)", () => {
    // 01's real retrieval funnel. Wave-18 viewer report: "funnel is good but
    // subtitle overlaps" — the funnel top was "12%" of the CONTAINER, landing
    // inside the headline+subtitle block.
    const payload = JSON.parse(
      readFileSync(
        resolve(process.cwd(), "../../projects/01-rag-agent/reports/figures/retrieval_funnel.json"),
        "utf8",
      ),
    ) as PlotlyPayload;
    const option = asOpt(plotlyToECharts(payload, "dark"));
    const funnel = option.series.find((s) => s.type === "funnel")!;
    expect(typeof funnel.top).toBe("number");
    const blockBottom =
      Math.max(...option.title.map((t) => (t.top as number) + (t.textStyle?.fontSize ?? 12) * 2.5));
    expect(funnel.top as number).toBeGreaterThanOrEqual(blockBottom - 8);
  });

  it("maps the heatmap to a visualMap + heatmap series", () => {
    const option = asOpt(plotlyToECharts(loadFigure("cost_surface"), "dark"));
    const heatmapIdx = option.series.findIndex((s) => s.type === "heatmap");
    expect(heatmapIdx).toBeGreaterThanOrEqual(0);
    expect(option.series[heatmapIdx].data).toHaveLength(41 * 19);
    expect(option.visualMap).toBeDefined();
    expect(option.visualMap.type).toBe("continuous");
    expect(option.visualMap.seriesIndex).toContain(heatmapIdx);
    expect(option.visualMap.min).toBeLessThan(option.visualMap.max);
    expect(option.visualMap.inRange.color[0]).toContain("rgb(");
  });

  it("keeps per-bar colors from a marker.color array (dark) and remaps them (light)", () => {
    const payload: PlotlyPayload = {
      data: [
        {
          type: "bar",
          x: ["a", "b"],
          y: [1, 2],
          marker: { color: ["#2dd4bf", "#64748b"] },
        },
      ],
      layout: { height: 560 },
    };
    const dark = asOpt(plotlyToECharts(payload, "dark"));
    expect(dark.series[0].data.map((d: { itemStyle: { color: string } }) => d.itemStyle.color)).toEqual([
      "#2dd4bf",
      "#64748b",
    ]);
    const light = asOpt(plotlyToECharts(payload, "light"));
    expect(light.series[0].data.map((d: { itemStyle: { color: string } }) => d.itemStyle.color)).toEqual([
      "#0f766e",
      "#475569",
    ]);
  });

  it("builds multi-subplot grids from plotly axis domains", () => {
    const option = asOpt(plotlyToECharts(loadFigure("fairness_slices"), "dark"));
    expect(option.grid).toHaveLength(2);
    expect(option.xAxis).toHaveLength(2);
    expect(option.yAxis).toHaveLength(2);
    expect(option.xAxis[0].type).toBe("category");
    expect(option.xAxis[0].data).toHaveLength(7);
    expect(option.xAxis[1].type).toBe("category");
    expect(option.grid[0].width).toBeLessThan(option.grid[1].left - option.grid[0].left);
    const legend = option.legend.data as string[];
    expect(legend).toEqual(["recall", "precision", "f1", "business_cost", "overall F1"]);
  });

  it("renders the horizontal permutation bar with a custom error-bar series", () => {
    const option = asOpt(plotlyToECharts(loadFigure("permutation_importance"), "dark"));
    const bar = option.series.find((s) => s.type === "bar")!;
    expect(bar.data).toHaveLength(6);
    expect(option.yAxis[0].type).toBe("category");
    expect(option.yAxis[0].data).toEqual([
      "gender",
      "senior_citizen",
      "monthly_charges",
      "internet_service",
      "contract",
      "tenure_months",
    ]);
    const err = option.series.find((s) => s.type === "custom")!;
    expect(err).toBeDefined();
    expect(err.data).toHaveLength(6);
    expect(typeof err.renderItem).toBe("function");
  });

  it("carries the bootstrap zero line as a markLine and sizes bars from the data span", () => {
    const option = asOpt(plotlyToECharts(loadFigure("bootstrap_ci"), "dark"));
    const layer = option.series.find((s) => s.markLine)!;
    expect(layer).toBeDefined();
    expect(layer.markLine.data[0].xAxis).toBe(0);
    // numeric bar centers on x get the data window (extent ± padding) —
    // never a pinned [0,1]; the zero baseline lives on the value (y) axis
    expect(option.xAxis[0].min).toBeLessThan(-500);
    expect(option.xAxis[0].min).toBeGreaterThan(-640);
    expect(option.xAxis[0].max).toBeGreaterThan(0);
    expect(option.xAxis[0].max).toBeLessThan(80);
    expect(option.yAxis[0].min).toBe(0); // positive-only bar counts
    // numeric-x bars get a px width from the data-unit widths
    const bars = option.series.filter((s) => s.type === "bar");
    for (const b of bars) {
      expect(b.barWidth).toBeGreaterThan(0);
      expect(Number.isFinite(b.barWidth)).toBe(true);
    }
  });

  it("numeric domain fractions never ride a time axis (adaptive_stream regression)", () => {
    // The payload's threshold shape and label use xref "x domain" with
    // INTEGER fractions (plotly writes fractions as numbers) — they must
    // resolve against the data extent, never be read as epoch ms (~1970).
    const payload = JSON.parse(
      readFileSync(
        resolve(process.cwd(), "../../projects/03-anomaly-detection/reports/figures/adaptive_stream.json"),
        "utf8",
      ),
    ) as PlotlyPayload;
    const option = asOpt(plotlyToECharts(payload, "dark", 1000));
    const stamps = payload.data
      .flatMap((t) => (Array.isArray((t as Record<string, unknown>).x) ? ((t as Record<string, unknown>).x as string[]) : []))
      .map((s) => Date.parse(s.replace(" ", "T")))
      .filter((v) => Number.isFinite(v));
    const ax = option.xAxis[0];
    const span = Math.max(...stamps) - Math.min(...stamps);
    expect(ax.type).toBe("time");
    // window = data extent ± ~5% padding — never epoch-adjacent
    expect(ax.min).toBeLessThan(Math.min(...stamps));
    expect(ax.min).toBeGreaterThan(Math.min(...stamps) - span * 0.2);
    expect(ax.max).toBeGreaterThan(Math.max(...stamps));
    expect(ax.max).toBeLessThan(Math.max(...stamps) + span * 0.2);
    // the "fixed threshold" label rides the silent layer at the resolved
    // fraction (the right edge of the data), not at x=1
    const layer = option.series.find((s) => s.silent && s.data.some((d: { label?: unknown }) => d.label))!;
    expect(layer).toBeDefined();
    const labeled = layer.data.find((d: { label?: unknown }) => d.label) as { value: number[] };
    expect(labeled.value[0]).toBeGreaterThan(1e12);
    // and the threshold line still spans the plot as a markLine
    const markLine = option.series.find((s) => s.markLine);
    expect(markLine).toBeDefined();
  });

  it("time axes span the parsed data dates — never epoch 0 (zone_fan regression)", () => {
    const payload = JSON.parse(
      readFileSync(
        resolve(process.cwd(), "../../projects/07-open-data-mobility/reports/figures/zone_fan.json"),
        "utf8",
      ),
    ) as PlotlyPayload;
    const option = asOpt(plotlyToECharts(payload, "dark", 990));
    // parse the payload's own date strings as the ground truth
    const stamps = payload.data
      .flatMap((t) => (Array.isArray((t as Record<string, unknown>).x) ? ((t as Record<string, unknown>).x as string[]) : []))
      .map((s) => Date.parse(s.replace(" ", "T")))
      .filter((v) => Number.isFinite(v));
    const dataMin = Math.min(...stamps);
    const dataMax = Math.max(...stamps);
    for (const axis of option.xAxis) {
      expect(axis.type).toBe("time");
      // window is the data extent ± padding: strictly inside it, and far
      // away from 1970 either way
      expect(axis.min).toBeGreaterThan(dataMin - (dataMax - dataMin) * 0.2);
      expect(axis.min).toBeLessThan(dataMin);
      expect(axis.max).toBeGreaterThan(dataMax);
      expect(axis.max).toBeLessThan(dataMax + (dataMax - dataMin) * 0.2);
      expect(axis.min).toBeGreaterThan(1e12); // no epoch-0 leak
    }
  });

  it("honors a payload-authored axis range verbatim (scale_ladder regression)", () => {
    const payload = JSON.parse(
      readFileSync(
        resolve(process.cwd(), "../../projects/04-nlp-classification/reports/figures/scale_ladder.json"),
        "utf8",
      ),
    ) as PlotlyPayload;
    const option = asOpt(plotlyToECharts(payload, "dark", 990));
    const authored = (payload.layout as Record<string, Record<string, unknown>>).yaxis.range as number[];
    expect(option.yAxis[0].min).toBe(authored[0]);
    expect(option.yAxis[0].max).toBe(authored[1]);
  });

  it("keeps authored [0, 1] windows for rate metrics (win_rate)", () => {
    const payload = JSON.parse(
      readFileSync(
        resolve(process.cwd(), "../../projects/02-demand-forecasting/reports_m5/figures/win_rate.json"),
        "utf8",
      ),
    ) as PlotlyPayload;
    expect(supportsECharts(payload)).toBe(true);
    const option = asOpt(plotlyToECharts(payload, "dark", 990));
    const y = option.yAxis[0];
    expect(y.min).toBe(0);
    expect(y.max).toBe(1);
  });

  it("value-axis windows track the data extent — no pinned 0/1 (temp_vs_rentals)", () => {
    const payload = JSON.parse(
      readFileSync(
        resolve(process.cwd(), "../../projects/12-tabular-ml-lifecycle/reports/figures/temp_vs_rentals.json"),
        "utf8",
      ),
    ) as PlotlyPayload;
    const option = asOpt(plotlyToECharts(payload, "dark", 990));
    const xs = option.series
      .flatMap((s) => (s.data as Array<{ value: unknown[] }>) ?? [])
      .map((d) => d.value[0])
      .filter((v): v is number => typeof v === "number" && Number.isFinite(v));
    const dataMin = Math.min(...xs);
    const dataMax = Math.max(...xs);
    const span = dataMax - dataMin;
    const ax = option.xAxis[0];
    // extent ± ~5% padding; neither a forced zero nor a pinned [0,1]
    expect(ax.min).toBeGreaterThanOrEqual(dataMin - span * 0.08);
    expect(ax.min).toBeLessThanOrEqual(dataMin);
    expect(ax.max).toBeGreaterThanOrEqual(dataMax);
    expect(ax.max).toBeLessThanOrEqual(dataMax + span * 0.08);
    expect(ax.min === 0 && ax.max === 1).toBe(false);
    // and the y window fits the rentals, not [0,1]
    const ys = option.series
      .flatMap((s) => (s.data as Array<{ value: unknown[] }>) ?? [])
      .map((d) => d.value[1])
      .filter((v): v is number => typeof v === "number" && Number.isFinite(v));
    const ySpan = Math.max(...ys) - Math.min(...ys);
    expect(option.yAxis[0].max).toBeGreaterThan(Math.max(...ys) + ySpan * 0.04);
    expect(option.yAxis[0].max).toBeLessThan(Math.max(...ys) + ySpan * 0.08);
  });

  it("renders subplot headers as extra title entries", () => {
    const option = asOpt(plotlyToECharts(loadFigure("eda_churn_profile"), "dark"));
    const texts = (option.title ?? []).map((t) => String(t.text).replace(/\n+/g, " "));
    expect(texts[0]).toContain("Churn profile");
    expect(texts).toContain("Churn rate by contract");
    expect(texts).toContain("Monthly charges distribution");
    expect(texts).toContain("Tenure distribution");
  });

  it("scales grids and bar widths down with the container (px bands clamp the shrink)", () => {
    const full = asOpt(plotlyToECharts(loadFigure("bootstrap_ci"), "dark", 1440));
    const small = asOpt(plotlyToECharts(loadFigure("bootstrap_ci"), "dark", 500));
    expect(small.grid[0].width).toBeLessThan(full.grid[0].width);
    expect(small.grid[0].width).toBeGreaterThan(40);
    const fullBar = full.series.find((s) => s.type === "bar")!;
    const smallBar = small.series.find((s) => s.type === "bar")!;
    expect(smallBar.barWidth).toBeLessThan(fullBar.barWidth);
    expect(smallBar.barWidth).toBeGreaterThan(0);
  });

  it("reserves a top band so titles never touch the plot, and centers subplot titles over their grid", () => {
    // eda has a global title + three subplot headers
    const opt = asOpt(plotlyToECharts(loadFigure("eda_churn_profile"), "dark", 1000));
    const main = opt.title[0];
    expect(main.top).toBeGreaterThanOrEqual(4);
    // every subplot header sits above its grid and is centered on it
    for (const sub of opt.title.slice(1)) {
      const g = opt.grid[opt.title.indexOf(sub) - 1];
      expect(sub.top + (sub.textStyle?.fontSize ?? 16)).toBeLessThanOrEqual(g.top);
      expect(Math.abs(sub.left - (g.left + g.width / 2))).toBeLessThanOrEqual(2);
    }
    // the global title is horizontally centered on the canvas
    expect(Math.abs(main.left - 500)).toBeLessThanOrEqual(2);
  });

  it("keeps the legend inside the reserved right band at mobile widths", () => {
    const opt = asOpt(plotlyToECharts(loadFigure("calibration_curve"), "dark", 390));
    // legend starts inside the clamped right band and has room for its text
    expect(opt.legend.left).toBeGreaterThan(390 - 190);
    expect(opt.legend.left).toBeLessThan(390);
  });

  it("encodes the axis-label polish invariants on every figure", () => {
    for (const name of FIGURE_NAMES) {
      const option = asOpt(plotlyToECharts(loadFigure(name), "dark", 390));
      for (const axis of [...option.xAxis, ...option.yAxis]) {
        // dense ticks thin instead of colliding; ticks use the site mono stack
        expect(axis.axisLabel.hideOverlap).toBe(true);
        expect(String(axis.axisLabel.fontFamily)).toContain("JetBrains Mono");
        // named axes carry clearance derived from the label stack
        if (axis.name) {
          expect(axis.nameGap).toBeGreaterThan(20);
          expect(String(axis.name).length).toBeGreaterThan(0);
        }
      }
    }
  });

  it("rotates category x labels only when the slot cannot fit them", () => {
    // fairness: 7 short-ish slice labels on a half-width grid at 390px → rotated
    const fairness = asOpt(plotlyToECharts(loadFigure("fairness_slices"), "dark", 390));
    const catX = fairness.xAxis.filter((a) => a.type === "category");
    expect(catX.length).toBeGreaterThan(0);
    for (const a of catX) expect(a.axisLabel.rotate).toBe(30);
    // permutation importance has NO category x axis → nothing rotated there
    const perm = asOpt(plotlyToECharts(loadFigure("permutation_importance"), "dark", 390));
    expect(perm.xAxis.every((a) => a.axisLabel.rotate === undefined)).toBe(true);
  });
});

describe("funnel support (projects/01 retrieval_funnel)", () => {
  const FUNNEL_DIR = resolve(process.cwd(), "../../projects/01-rag-agent/reports/figures");

  it("converts the committed funnel payload", () => {
    const payload = JSON.parse(
      readFileSync(resolve(FUNNEL_DIR, "retrieval_funnel.json"), "utf8"),
    ) as PlotlyPayload;
    expect(supportsECharts(payload)).toBe(true);
    const option = asOpt(plotlyToECharts(payload, "dark", 1000));
    const funnel = option.series.find((s) => s.type === "funnel")!;
    expect(funnel).toBeDefined();
    expect(funnel.sort).toBe("none");
    // stages map to named, colorway-colored items with the authored values
    expect(funnel.data.map((d: { name: string }) => d.name)).toEqual([
      "embedding candidates (top-15)",
      "after rerank (top-3)",
      "relevant article in top-k",
    ]);
    expect(funnel.data.map((d: { value: number }) => d.value)).toEqual([975, 195, 54]);
    // not cartesian: no grids/axes are emitted
    expect(option.grid).toHaveLength(0);
    expect(option.xAxis).toHaveLength(0);
    expect(option.yAxis).toHaveLength(0);
    // percent-initial formatting is anchored on the first stage
    const label = funnel.label.formatter as (p: { name: string; value: number }) => string;
    expect(label({ name: "s", value: 195 })).toBe("s: 195 · 20.0%");
    expect(label({ name: "s", value: 975 })).toBe("s: 975 · 100.0%");
  });
});

describe("choropleth fallback (projects/07)", () => {
  const MAPS_DIR = resolve(process.cwd(), "../../projects/07-open-data-mobility/reports/figures");

  it("rejects the committed choropleth payloads (plotly fallback)", () => {
    for (const name of ["zone_demand_map", "zone_residual_map"]) {
      const payload = JSON.parse(readFileSync(resolve(MAPS_DIR, `${name}.json`), "utf8")) as PlotlyPayload;
      expect(supportsECharts(payload)).toBe(false);
    }
  });
});

describe("supportsECharts", () => {
  it("rejects trace types outside the pilot subset", () => {
    expect(
      supportsECharts({
        data: [{ type: "pie", labels: ["a", "b"], values: [1, 2] }],
        layout: {},
      }),
    ).toBe(false);
  });

  it("rejects axis types outside value/log/category", () => {
    expect(
      supportsECharts({
        data: [{ type: "scatter", mode: "markers", x: [1, 10, 100], y: [1, 2, 3] }],
        layout: { xaxis: { type: "date" } },
      }),
    ).toBe(false);
  });

  it("accepts log axes and renders them as echarts log axes", () => {
    const payload: PlotlyPayload = {
      data: [{ type: "scatter", mode: "markers", x: [1, 10, 100], y: [1, 2, 3] }],
      layout: { xaxis: { type: "log" } },
    };
    expect(supportsECharts(payload)).toBe(true);
    const option = asOpt(plotlyToECharts(payload, "dark"));
    expect(option.xAxis[0].type).toBe("log");
    // plotly's log autorange fits the data extent exactly (echarts' own
    // decade snapping would strand the curve in part of the canvas)
    expect(option.xAxis[0].min).toBe(1);
    expect(option.xAxis[0].max).toBe(100);
  });

  it("log window tracks the data extent instead of snapping to decades", () => {
    const payload: PlotlyPayload = {
      data: [
        {
          type: "scatter",
          mode: "lines",
          x: [0.005, 0.01, 0.02, 0.05, 0.1],
          y: [0.1, 0.2, 0.3, 0.4, 0.5],
        },
      ],
      layout: { xaxis: { type: "log" } },
    };
    const option = asOpt(plotlyToECharts(payload, "dark"));
    // threshold_sweep regression: the window is exactly the data extent
    expect(option.xAxis[0].min).toBe(0.005);
    expect(option.xAxis[0].max).toBe(0.1);
  });

  it("tooltips round like the axis ticks, cap at 8 entries, and group repeats", () => {
    const payload: PlotlyPayload = {
      data: [
        { type: "scatter", mode: "lines", name: "a", x: [1, 2], y: [0.123456789, 0.2] },
        { type: "scatter", mode: "lines", name: "b", x: [1, 2], y: [0.123456789, 0.4] },
      ],
      layout: {},
    };
    const option = asOpt(plotlyToECharts(payload, "dark"));
    const tooltip = option.tooltip as { formatter: (p: unknown) => string };
    const params = [
      ...Array.from({ length: 12 }, (_, i) => ({
        seriesName: `s${i}`,
        value: [1, 0.5],
        marker: "",
        axisValueLabel: "x = 1",
      })),
      // a duplicate of s0's rendered value — must collapse, not double-list
      { seriesName: "s0-dup", value: [1, 0.5], marker: "", axisValueLabel: "x = 1" },
    ];
    const html = tooltip.formatter(params);
    const lines = html.split("<br/>").filter((l) => l.includes(":"));
    expect(lines.length).toBe(8);
    expect(html).toContain("+5 more"); // 12 unique + 1 duplicate - 8 shown
    const rounded = asOpt(
      plotlyToECharts(
        {
          data: [{ type: "scatter", mode: "lines", name: "a", x: [1], y: [0.123456789] }],
          layout: {},
        },
        "dark",
      ),
    ).tooltip as { formatter: (p: unknown) => string };
    expect(rounded.formatter([{ seriesName: "a", value: [1, 0.123456789], marker: "", axisValueLabel: "1" }])).toContain(
      "0.123457",
    );
  });

  it("dense all-scatter charts switch to the single-point item tooltip", () => {
    const many = (offset: number) => ({
      type: "scatter" as const,
      mode: "markers" as const,
      name: `s${offset}`,
      x: Array.from({ length: 400 }, (_, i) => i),
      y: Array.from({ length: 400 }, (_, i) => i + offset),
    });
    const option = asOpt(
      plotlyToECharts({ data: [many(0), many(1000)], layout: {} }, "dark"),
    );
    const tooltip = option.tooltip as { trigger: string; formatter: (p: unknown) => string };
    expect(tooltip.trigger).toBe("item"); // 800 points > 500 threshold
    const html = tooltip.formatter({ seriesName: "s0", value: [3, 3], marker: "" });
    expect(html).toContain("s0");
    expect(html).toContain("3"); // rounded single point, no x-bin dump
  });

  it("heatmaps get cell labels, an item tooltip with the value, and the colorbar title", () => {
    const payload = {
      data: [
        {
          type: "heatmap",
          x: ["a", "b", "c"],
          y: ["p", "q", "r"],
          z: [
            [1, 0.2, -0.35],
            [0.2, 1, 0.87654321],
            [-0.35, 0.87654321, 1],
          ],
          // authored per-cell text wins over reformatting z
          text: [
            ["1.00", "0.20", "-0.35"],
            ["0.20", "1.00", "0.88"],
            ["-0.35", "0.88", "1.00"],
          ],
          texttemplate: "%{text}",
          colorscale: [
            [0, "#f472b6"],
            [1, "#2dd4bf"],
          ],
          colorbar: { title: { text: "Pearson r" } },
        },
      ],
      layout: {},
    } as unknown as PlotlyPayload;
    const option = asOpt(plotlyToECharts(payload, "dark"));
    const series = (option.series as Array<Record<string, unknown>>)[0];
    expect((series.label as { show: boolean }).show).toBe(true); // 9 cells <= 144
    const labelFormatter = (series.label as { formatter: (p: unknown) => string }).formatter;
    expect(labelFormatter({ value: ["b", "q", 0.87654321], data: { authoredText: "0.88" } })).toBe(
      "0.88",
    );
    expect(labelFormatter({ value: ["a", "p", 1], data: {} })).toBe("1");
    const tooltip = option.tooltip as { trigger: string; formatter: (p: unknown) => string };
    expect(tooltip.trigger).toBe("item");
    expect(
      tooltip.formatter({ value: ["a", "q", 0.87654321], data: { authoredText: "0.88" }, marker: "" }),
    ).toBe("q · a: 0.88");
    expect(tooltip.formatter({ value: ["a", "q", 0.87654321], data: {}, marker: "" })).toBe(
      "q · a: 0.876543",
    );
    const visualMap = option.visualMap as { text?: string[] };
    expect(visualMap.text?.[0]).toBe("Pearson r");
  });

  it("accepts fill bands (tonexty) as a silent polygon between the pair", () => {
    const payload: PlotlyPayload = {
      data: [
        { type: "scatter", mode: "lines", x: [0, 1, 2], y: [2, 3, 2], fill: "tonexty", fillcolor: "rgba(45,212,191,0.2)" },
        { type: "scatter", mode: "lines", x: [0, 1, 2], y: [1, 1.5, 1] },
      ],
      layout: { height: 560 },
    };
    expect(supportsECharts(payload)).toBe(true);
    const option = asOpt(plotlyToECharts(payload, "dark"));
    const band = option.series.find((s) => s.type === "custom" && s.renderItem && s.z === 1)!;
    expect(band).toBeDefined();
    expect(band.silent).toBe(true);
    expect(typeof band.renderItem).toBe("function");
  });

  it("rejects unsupported marker symbols and histnorms (rect shapes are supported)", () => {
    expect(
      supportsECharts({
        data: [{ type: "scatter", mode: "markers", x: [1], y: [1], marker: { symbol: "bowtie" } }],
        layout: {},
      }),
    ).toBe(false);
    const withRect: PlotlyPayload = {
      data: [{ type: "scatter", mode: "lines", x: [0, 1], y: [0, 1] }],
      layout: {
        height: 560,
        shapes: [{ type: "rect", xref: "x", yref: "y", x0: 0.2, x1: 0.8, y0: 0.2, y1: 0.8, fillcolor: "rgba(148,163,184,0.2)" }],
      },
    };
    expect(supportsECharts(withRect)).toBe(true);
    const option = asOpt(plotlyToECharts(withRect, "dark"));
    const layer = option.series.find((s) => s.markArea)!;
    expect(layer.markArea.data[0][0].xAxis).toBe(0.2);
    expect(layer.markArea.data[0][1].yAxis).toBe(0.8);
    expect(
      supportsECharts({
        data: [{ type: "histogram", x: [1, 2, 3], histnorm: "percent" }],
        layout: {},
      }),
    ).toBe(false);
  });

  it("accepts an empty data array", () => {
    expect(supportsECharts({ data: [], layout: { height: 560 } })).toBe(true);
  });
});
