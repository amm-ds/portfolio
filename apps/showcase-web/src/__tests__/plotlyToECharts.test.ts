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
  title?: Array<Record<string, any>>;
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

  it("maps the heatmap to a visualMap + heatmap series", () => {
    const option = asOpt(plotlyToECharts(loadFigure("cost_surface"), "dark"));
    const heatmapIdx = option.series.findIndex((s) => s.type === "heatmap");
    expect(heatmapIdx).toBeGreaterThanOrEqual(0);
    expect(option.series[heatmapIdx].data).toHaveLength(41 * 19);
    expect(option.visualMap).toBeDefined();
    expect(option.visualMap.type).toBe("continuous");
    expect(option.visualMap.seriesIndex).toBe(heatmapIdx);
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
    // the zero-pinning annotation rides the silent layer, so the value axis
    // itself stays autoscaling (plotly parity: annotation coords expand the
    // range through data, not through explicit min/max)
    expect(option.xAxis[0].min).toBeUndefined();
    // numeric-x bars get a px width from the data-unit widths
    const bars = option.series.filter((s) => s.type === "bar");
    for (const b of bars) {
      expect(b.barWidth).toBeGreaterThan(0);
      expect(Number.isFinite(b.barWidth)).toBe(true);
    }
  });

  it("renders subplot headers as extra title entries", () => {
    const option = asOpt(plotlyToECharts(loadFigure("eda_churn_profile"), "dark"));
    const texts = (option.title ?? []).map((t) => t.text);
    expect(texts[0]).toContain("Churn profile");
    expect(texts).toContain("Churn rate by contract");
    expect(texts).toContain("Monthly charges distribution");
    expect(texts).toContain("Tenure distribution");
  });

  it("scales grids and bar widths to the container width", () => {
    const full = asOpt(plotlyToECharts(loadFigure("bootstrap_ci"), "dark", 1000));
    const half = asOpt(plotlyToECharts(loadFigure("bootstrap_ci"), "dark", 500));
    expect(half.grid[0].width).toBeCloseTo(full.grid[0].width / 2, 0);
    const fullBar = full.series.find((s) => s.type === "bar")!;
    const halfBar = half.series.find((s) => s.type === "bar")!;
    expect(halfBar.barWidth).toBeCloseTo(fullBar.barWidth / 2, 0);
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

  it("rejects non-linear axis types", () => {
    expect(
      supportsECharts({
        data: [{ type: "scatter", mode: "markers", x: [1, 10, 100], y: [1, 2, 3] }],
        layout: { xaxis: { type: "log" } },
      }),
    ).toBe(false);
  });

  it("rejects unsupported marker symbols, shapes and histnorms", () => {
    expect(
      supportsECharts({
        data: [{ type: "scatter", mode: "markers", x: [1], y: [1], marker: { symbol: "bowtie" } }],
        layout: {},
      }),
    ).toBe(false);
    expect(
      supportsECharts({
        data: [{ type: "scatter", mode: "lines", x: [0, 1], y: [0, 1] }],
        layout: { shapes: [{ type: "rect", x0: 0, x1: 1, y0: 0, y1: 1 }] },
      }),
    ).toBe(false);
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
