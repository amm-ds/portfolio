import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FigureCard, figureCsv } from "../components/FigureCard";

const mocks = vi.hoisted(() => ({
  react: vi.fn(),
  purge: vi.fn(),
  init: vi.fn(),
  use: vi.fn(),
  setOption: vi.fn(),
  dispose: vi.fn(),
}));

vi.mock("plotly.js-dist-min", () => ({
  default: { react: mocks.react, purge: mocks.purge },
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

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  mocks.react.mockReset();
  mocks.purge.mockReset();
  mocks.init.mockReset();
  mocks.use.mockReset();
  mocks.setOption.mockReset();
  mocks.dispose.mockReset();
});

const SUPPORTED_PAYLOAD = {
  data: [{ type: "bar", x: ["a", "b"], y: [1, 2] }],
  layout: { height: 560, width: 1000 },
};

describe("FigureCard", () => {
  it("renders one container with the chart and a commentary band inside it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() =>
        Promise.resolve(jsonResponse({ data: [{ type: "bar" }], layout: { height: 560 } })),
      ),
    );
    render(
      <FigureCard
        pid="01-rag-agent"
        name="retrieval_funnel"
        caption="Retrieval recall@5 reaches 0.83 once claims are verified."
      />,
    );
    await waitFor(() => expect(mocks.init).toHaveBeenCalledTimes(1));
    // a single .figure-card holds both the chart and the band — one tile
    const cards = document.querySelectorAll(".figure-card");
    expect(cards).toHaveLength(1);
    const card = cards[0];
    expect(card.querySelector(".plotly-host")).not.toBeNull();
    const band = card.querySelector("footer.figure-card-band")!;
    expect(band).not.toBeNull();
    expect(band.querySelector(".figure-id")!.textContent).toBe(
      "fig :: retrieval_funnel",
    );
    expect(band.querySelector(".figure-comment")!.textContent).toBe(
      "Retrieval recall@5 reaches 0.83 once claims are verified.",
    );
  });

  it("shows the labeled skeleton inside the card until the plot renders", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() =>
        Promise.resolve(jsonResponse({ data: [{ type: "bar" }], layout: { height: 560 } })),
      ),
    );
    render(
      <FigureCard
        pid="02-demand-forecasting"
        name="wape_horizon"
        caption="WAPE by candidate and horizon."
      />,
    );
    const card = document.querySelector<HTMLElement>(".figure-card")!;
    // intentional loading state: "> name" label + status line, not a blank box
    const skeleton = within(card).getByTestId("figure-skeleton");
    expect(skeleton).toHaveTextContent("> wape_horizon");
    expect(skeleton).toHaveTextContent("rendering figure…");
    await waitFor(() => expect(mocks.init).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(within(card).queryByTestId("figure-skeleton")).toBeNull());
    expect(card.querySelector(".plotly-host")).not.toBeNull();
  });

  it("falls back to an id-only band when no caption exists", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no" }, 404)));
    render(<FigureCard pid="01-rag-agent" name="latency_histogram" />);
    await waitFor(() => expect(screen.getByTitle("Figure: latency_histogram")).toBeInTheDocument());
    const band = document.querySelector(".figure-card footer.figure-card-band")!;
    expect(band.querySelector(".figure-id")!.textContent).toBe(
      "fig :: latency_histogram",
    );
    // no commentary paragraph, but the band itself is still there
    expect(band.querySelector(".figure-comment")).toBeNull();
  });

  it("keeps the band inside the container on the iframe fallback chart", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no" }, 404)));
    render(
      <FigureCard pid="05-ml-pipeline-churn" name="pr_curve" caption="Precision dominates above a 0.31 threshold." />,
    );
    await waitFor(() => expect(screen.getByTitle("Figure: pr_curve")).toBeInTheDocument());
    // chart (iframe) and band are siblings within the single card container
    const card = document.querySelector(".figure-card")!;
    expect(card.querySelector("iframe")).not.toBeNull();
    const band = card.querySelector("footer.figure-card-band")!;
    expect(band).not.toBeNull();
    expect(band.querySelector(".figure-comment")!.textContent).toContain(
      "Precision dominates above a 0.31 threshold.",
    );
    expect(band.querySelector(".figure-id")!.textContent).toBe("fig :: pr_curve");
  });

  it("routes every project through EChartsFigure (the per-figure plotly fallback stays inside)", async () => {
    mocks.init.mockReturnValue({ setOption: mocks.setOption, resize: vi.fn(), dispose: mocks.dispose });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(SUPPORTED_PAYLOAD))),
    );
    const { unmount } = render(<FigureCard pid="05-ml-pipeline-churn" name="pilot_bar" />);
    await waitFor(() => expect(mocks.init).toHaveBeenCalledTimes(1));
    expect(mocks.react).not.toHaveBeenCalled();
    // the data table band still receives the payload via onPayload
    await waitFor(() =>
      expect(document.querySelector(".figure-data table.data-table")).not.toBeNull(),
    );
    unmount();

    render(<FigureCard pid="01-rag-agent" name="plain_bar" />);
    await waitFor(() => expect(mocks.init).toHaveBeenCalledTimes(2));
    expect(mocks.react).not.toHaveBeenCalled();
  });

  it("shows real per-point values, bounds the table, and downloads every value", async () => {
    const y = Array.from({ length: 205 }, (_, index) => index + 0.125);
    const payload = { data: [{ type: "bar", name: "observed", x: y.map((_, i) => `p${i}`), y }], layout: {} };
    mocks.init.mockReturnValue({ setOption: mocks.setOption, resize: vi.fn(), dispose: mocks.dispose });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(payload)));
    const NativeURL = URL;
    const createObjectURL = vi.fn().mockReturnValue("blob:figure");
    const revokeObjectURL = vi.fn();
    class MockURL extends NativeURL {
      static createObjectURL = createObjectURL;
      static revokeObjectURL = revokeObjectURL;
    }
    vi.stubGlobal("URL", MockURL);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(<FigureCard pid="p" name="bounded" caption="Observed values by point." />);
    await waitFor(() => expect(document.querySelectorAll(".figure-data tbody tr")).toHaveLength(200));
    expect(document.querySelector(".figure-data tbody tr")).toHaveTextContent("p0");
    expect(document.querySelector(".figure-data tbody tr")).toHaveTextContent("0.125");
    expect(screen.getByText(/Showing the first 200 of 205 plotted values/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Observed values by point." })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "download CSV (205 values)" }));
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:figure");
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    await expect(blob.text()).resolves.toBe(figureCsv(payload));
    expect(figureCsv(payload).split("\r\n")).toHaveLength(206);
    click.mockRestore();
  });

  it("uses the plotly table header for the accessible data table", async () => {
    const payload = {
      data: [
        {
          type: "table",
          header: { values: ["quantization arm", "schema", "keywords", "requests", "failures"] },
          cells: {
            values: [
              ["gemma4:31b-it-qat (llamacpp)"],
              ["PASS"],
              ["PASS"],
              [40],
              [0],
            ],
          },
        },
      ],
      layout: {},
    };
    mocks.init.mockReturnValue({ setOption: mocks.setOption, resize: vi.fn(), dispose: mocks.dispose });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(payload)));
    render(<FigureCard pid="08-inference-serving" name="quality_quant" caption="Quality guardrail." />);

    await waitFor(() => expect(document.querySelector(".figure-data tbody tr")).not.toBeNull());
    const headers = [...document.querySelectorAll(".figure-data thead th")].map((el) => el.textContent);
    expect(headers).toEqual(["series", "schema", "keywords", "requests", "failures"]);
    expect(document.querySelector(".figure-data tbody tr")).toHaveTextContent("gemma4:31b-it-qat (llamacpp)");
    expect(document.querySelector(".figure-data tbody tr")).toHaveTextContent("PASS");
    expect(figureCsv(payload)).toBe(
      "series,schema,keywords,requests,failures\r\ngemma4:31b-it-qat (llamacpp),PASS,PASS,40,0",
    );
  });
});

describe("figureCsv", () => {
  it.each([
    {
      label: "lines and bars",
      trace: { type: "scatter", name: "actual", x: ["a", null], y: [1.25, 2] },
      expected: "series,x,y\r\nactual,a,1.25\r\nactual,,2",
    },
    {
      label: "heatmaps",
      trace: { type: "heatmap", name: "H", x: ["a", "b"], y: ["A"], z: [[0.25, 0.5]] },
      expected: "series,x,y,value\r\nH,a,A,0.25\r\nH,b,A,0.5",
    },
    {
      label: "funnels",
      trace: { type: "funnel", name: "F", y: ["visited", "converted"], x: [100, 12] },
      expected: "series,stage,value\r\nF,visited,100\r\nF,converted,12",
    },
    {
      label: "histograms",
      trace: { type: "histogram", name: "sample", x: [1.2, 1.3] },
      expected: "series,sample\r\nsample,1.2\r\nsample,1.3",
    },
    {
      label: "point maps",
      trace: {
        type: "scattergeo",
        name: "M",
        lon: [-73.9, -74.1],
        lat: [40.7, 40.8],
        text: ["A", "B"],
        marker: { color: [4, 5] },
      },
      expected:
        "series,longitude,latitude,label,value\r\nM,-73.9,40.7,A,4\r\nM,-74.1,40.8,B,5",
    },
    {
      label: "area maps",
      trace: { type: "choropleth", name: "C", locations: ["10001", "10002"], z: [2.5, 3.5] },
      expected: "series,location,value\r\nC,10001,2.5\r\nC,10002,3.5",
    },
  ])("exports $label as per-point CSV", ({ trace, expected }) => {
    expect(figureCsv({ data: [trace], layout: {} })).toBe(expected);
  });

  it("quotes labels without changing their values", () => {
    expect(
      figureCsv({ data: [{ type: "bar", x: ['a,"b"'], y: [1] }], layout: {} }),
    ).toBe('series,x,y\r\ntrace 1,"a,""b""",1');
  });
});
