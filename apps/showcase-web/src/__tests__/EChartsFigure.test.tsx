import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EChartsFigure } from "../components/EChartsFigure";
import { resetThemeStoreForTests } from "../theme/useTheme";

const mocks = vi.hoisted(() => ({
  init: vi.fn(),
  use: vi.fn(),
  setOption: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn(),
  react: vi.fn(),
  purge: vi.fn(),
}));

vi.mock("echarts/core", () => ({
  default: {},
  init: mocks.init,
  use: mocks.use,
}));

vi.mock("echarts/charts", () => ({
  LineChart: {},
  BarChart: {},
  ScatterChart: {},
  HeatmapChart: {},
  CustomChart: {},
  FunnelChart: {},
}));

vi.mock("echarts/components", () => ({
  GridComponent: {},
  TooltipComponent: {},
  LegendComponent: {},
  VisualMapComponent: {},
  TitleComponent: {},
  MarkLineComponent: {},
  MarkAreaComponent: {},
}));

vi.mock("echarts/renderers", () => ({
  SVGRenderer: {},
}));

vi.mock("plotly.js-dist-min", () => ({
  default: { react: mocks.react, purge: mocks.purge },
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const SUPPORTED = {
  data: [{ type: "bar", x: ["a", "b"], y: [1, 2] }],
  layout: { height: 560, width: 1000 },
};

beforeEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  resetThemeStoreForTests();
  mocks.init.mockReturnValue({
    setOption: mocks.setOption,
    resize: mocks.resize,
    dispose: mocks.dispose,
  });
});

afterEach(() => {
  resetThemeStoreForTests();
  cleanup();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  Object.values(mocks).forEach((m) => m.mockReset());
});

describe("EChartsFigure", () => {
  it("fetches the payload, inits echarts on the host div and retires the skeleton", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(SUPPORTED));
    vi.stubGlobal("fetch", fetchMock);
    const onPayload = vi.fn();
    render(<EChartsFigure pid="05-ml-pipeline-churn" name="pilot_fig" onPayload={onPayload} />);

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/projects/05-ml-pipeline-churn/figures/pilot_fig.json"),
    );
    await waitFor(() => expect(mocks.init).toHaveBeenCalledTimes(1));
    // registers the pilot modules exactly once, then reuses the instance
    expect(mocks.use).toHaveBeenCalledTimes(1);
    const host = mocks.init.mock.calls[0][0] as HTMLElement;
    expect(host.dataset.testid).toBe("echarts-pilot_fig");
    expect(mocks.init.mock.calls[0][2]).toMatchObject({ renderer: "svg" });
    await waitFor(() => expect(screen.queryByTestId("figure-skeleton")).toBeNull());
    expect(mocks.setOption).toHaveBeenCalled();
    const option = mocks.setOption.mock.calls[0][0];
    expect(option.series[0].type).toBe("bar");
    expect(option.backgroundColor).toBe("rgba(0,0,0,0)");
    expect(onPayload).toHaveBeenCalledWith(SUPPORTED);
  });

  it("falls back to the plotly renderer for unsupported payloads", async () => {
    // fresh Response per call: the fallback path fetches the same URL twice
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() =>
        Promise.resolve(
          jsonResponse({ data: [{ type: "pie", values: [1, 2] }], layout: { height: 560 } }),
        ),
      ),
    );
    const onPayload = vi.fn();
    render(<EChartsFigure pid="05-ml-pipeline-churn" name="pie_fig" onPayload={onPayload} />);
    // plotly takes over: its own fetch + react, no echarts init
    await waitFor(() => expect(mocks.react).toHaveBeenCalledTimes(1));
    expect(mocks.init).not.toHaveBeenCalled();
    expect(onPayload).toHaveBeenCalled();
  });

  it("falls back to the plotly renderer when the echarts init fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(SUPPORTED))),
    );
    mocks.init.mockImplementation(() => {
      throw new Error("renderer failed");
    });
    const onPayload = vi.fn();
    render(<EChartsFigure pid="05-ml-pipeline-churn" name="boom_fig" onPayload={onPayload} />);
    await waitFor(() => expect(mocks.react).toHaveBeenCalledTimes(1));
    expect(mocks.setOption).not.toHaveBeenCalled();
    expect(onPayload).toHaveBeenLastCalledWith(SUPPORTED);
  });

  it("falls back to the iframe when the JSON 404s", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no" }, 404)));
    render(<EChartsFigure pid="05-ml-pipeline-churn" name="missing_fig" />);
    await waitFor(() => expect(screen.getByTitle("Figure: missing_fig")).toBeInTheDocument());
    expect(mocks.init).not.toHaveBeenCalled();
    expect(mocks.react).not.toHaveBeenCalled();
  });

  it("disposes the chart on unmount", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(SUPPORTED)));
    const { unmount } = render(<EChartsFigure pid="05-ml-pipeline-churn" name="cleanup_fig" />);
    await waitFor(() => expect(mocks.init).toHaveBeenCalledTimes(1));
    unmount();
    await waitFor(() => expect(mocks.dispose).toHaveBeenCalledTimes(1));
  });

  it("renders the caption as a section link like PlotlyFigure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(SUPPORTED)));
    render(
      <EChartsFigure
        pid="05-ml-pipeline-churn"
        name="linked_fig"
        caption="fig :: results · 1/1 — Results"
        sectionId="results"
      />,
    );
    await waitFor(() => expect(mocks.init).toHaveBeenCalled());
    const link = screen.getByRole("link", { name: "fig :: results · 1/1 — Results" });
    expect(link.getAttribute("href")).toBe("#sec-results");
  });
});
