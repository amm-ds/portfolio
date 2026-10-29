import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildLayout, PlotlyFigure, scaledHeight } from "../components/PlotlyFigure";

const mocks = vi.hoisted(() => ({
  react: vi.fn(),
  purge: vi.fn(),
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

const PAYLOAD = {
  data: [{ type: "bar", y: [1, 2, 3] }],
  layout: { height: 560, width: 1000, title: "eval" },
};

beforeEach(() => {
  mocks.react.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  mocks.react.mockReset();
  mocks.purge.mockReset();
});

describe("PlotlyFigure", () => {
  it("fetches the JSON payload and renders natively, full-size and re-skinned", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(PAYLOAD));
    vi.stubGlobal("fetch", fetchMock);
    render(<PlotlyFigure pid="01-rag-agent" name="retrieval_funnel" caption="fig :: results · 1/1 — Results" />);

    expect(fetchMock).toHaveBeenCalledWith("/projects/01-rag-agent/figures/retrieval_funnel.json");
    await waitFor(() => expect(mocks.react).toHaveBeenCalledTimes(1));
    // the labeled skeleton retires once the plot is painted
    expect(screen.queryByTestId("figure-skeleton")).toBeNull();
    const [el, data, layout, config] = mocks.react.mock.calls[0];
    expect((el as HTMLElement).dataset.testid).toBe("plotly-retrieval_funnel");
    expect(data).toEqual(PAYLOAD.data);
    // jsdom measures clientWidth as 0 → scaled height falls back to the 360 minimum.
    expect(layout).toMatchObject({
      height: 360,
      autosize: true,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: "#e2e8f0" },
    });
    expect(layout.width).toBeUndefined();
    expect(config).toEqual({ responsive: true, displayModeBar: false });
    expect(screen.getByText("fig :: results · 1/1 — Results")).toBeInTheDocument();
  });

  it("renders the caption as a link to the story section anchor when sectionId is given", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(PAYLOAD)));
    render(
      <PlotlyFigure
        pid="p"
        name="linked"
        caption="fig :: results · 1/1 — Results"
        sectionId="results"
      />,
    );
    await waitFor(() => expect(mocks.react).toHaveBeenCalled());
    const link = screen.getByRole("link", { name: "fig :: results · 1/1 — Results" });
    expect(link.getAttribute("href")).toBe("#sec-results");
    expect(link.classList.contains("figure-caption")).toBe(true);
  });

  it("renders a plain figcaption when no sectionId is given", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(PAYLOAD)));
    render(<PlotlyFigure pid="p" name="plain" caption="fig :: eda · 1/1 — EDA" />);
    await waitFor(() => expect(mocks.react).toHaveBeenCalled());
    expect(screen.queryByRole("link", { name: /fig ::/ })).toBeNull();
    expect(screen.getByText("fig :: eda · 1/1 — EDA").tagName).toBe("FIGCAPTION");
  });

  it("scales the authored height to the measured container width", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ data: [], layout: { height: 1200 } })),
    );
    render(<PlotlyFigure pid="p" name="tall" />);
    await waitFor(() => expect(mocks.react).toHaveBeenCalled());
    // 1200 * 0 / 1000 → clamped to the 360 minimum in jsdom
    expect(mocks.react.mock.calls[0][2].height).toBe(360);
  });

  it("shows a labeled skeleton placeholder until the plot renders", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<PlotlyFigure pid="p" name="pending_fig" />);
    const skeleton = screen.getByTestId("figure-skeleton");
    // intentional pending state: mono "$ name" corner label + status line
    expect(skeleton).toHaveTextContent("$ pending_fig");
    expect(skeleton).toHaveTextContent("rendering figure…");
  });

  it("defers the plotly import until the host nears the viewport", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(PAYLOAD)));
    // jsdom has no IntersectionObserver: stub a controllable one
    let ioCallback: ((entries: { isIntersecting: boolean }[]) => void) | null = null;
    class MockIO {
      constructor(cb: typeof ioCallback) {
        ioCallback = cb;
      }
      observe() {}
      disconnect() {}
    }
    vi.stubGlobal("IntersectionObserver", MockIO);
    render(<PlotlyFigure pid="p" name="gated" />);
    // payload arrives, but the plot must not render before intersection
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    await act(() => new Promise((r) => setTimeout(r, 20)));
    expect(mocks.react).not.toHaveBeenCalled();
    expect(screen.getByTestId("figure-skeleton")).toHaveTextContent("$ gated");
    expect(screen.getByText("rendering figure…")).toBeInTheDocument();
    // host enters the viewport → render proceeds, skeleton retires
    act(() => {
      ioCallback!([{ isIntersecting: true }]);
    });
    await waitFor(() => expect(mocks.react).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.queryByTestId("figure-skeleton")).toBeNull());
  });

  it("falls back to the HTML iframe when the JSON payload 404s", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no" }, 404)));
    render(<PlotlyFigure pid="01-rag-agent" name="old_fig" caption="fig :: eda · 1/2 — EDA" />);
    await waitFor(() =>
      expect(screen.getByTitle("Figure: old_fig")).toBeInTheDocument(),
    );
    expect(screen.getByTitle("Figure: old_fig")).toHaveAttribute(
      "src",
      "/projects/01-rag-agent/figures/old_fig",
    );
    expect(mocks.react).not.toHaveBeenCalled();
    expect(screen.getByText("fig :: eda · 1/2 — EDA")).toBeInTheDocument();
  });

  it("falls back to the iframe on non-404 fetch errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "err" }, 500)));
    render(<PlotlyFigure pid="p" name="boom" />);
    await waitFor(() => expect(screen.getByTitle("Figure: boom")).toBeInTheDocument());
    expect(mocks.react).not.toHaveBeenCalled();
  });

  it("falls back to the iframe when Plotly.react rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(PAYLOAD)));
    mocks.react.mockRejectedValue(new Error("renderer failed"));
    const onPayload = vi.fn();
    render(<PlotlyFigure pid="p" name="render_failure" onPayload={onPayload} />);

    await waitFor(() => expect(screen.getByTitle("Figure: render_failure")).toBeInTheDocument());
    expect(onPayload).toHaveBeenLastCalledWith(null);
  });

  it("purges the plot on unmount", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(PAYLOAD)));
    const { unmount } = render(<PlotlyFigure pid="p" name="cleanup_fig" />);
    await waitFor(() => expect(mocks.react).toHaveBeenCalled());
    const el = mocks.react.mock.calls[0][0] as HTMLElement;
    unmount();
    await waitFor(() => expect(mocks.purge).toHaveBeenCalledWith(el));
  });
});

describe("scaledHeight", () => {
  it("scales linearly against a 1000px design width", () => {
    expect(scaledHeight(560, 1000)).toBe(560);
    expect(scaledHeight(560, 800)).toBe(448);
    expect(scaledHeight(560, 1800)).toBe(1008);
  });

  it("clamps to [360, 1100]", () => {
    expect(scaledHeight(100, 1000)).toBe(360);
    expect(scaledHeight(1200, 2000)).toBe(1100);
  });

  it("falls back to the default height for missing/non-numeric values", () => {
    expect(scaledHeight(undefined, 1000)).toBe(560);
    expect(scaledHeight("560", 1000)).toBe(560);
    expect(scaledHeight(Number.NaN, 1000)).toBe(560);
  });
});

describe("buildLayout", () => {
  it("applies dark-theme defaults for font, legend and both axes", () => {
    const layout = buildLayout({ height: 560 }, 1000);
    expect(layout.font).toEqual({ color: "#e2e8f0" });
    expect(layout.legend).toEqual({
      bgcolor: "rgba(0,0,0,0)",
      font: { color: "#e2e8f0" },
    });
    for (const axis of ["xaxis", "yaxis"]) {
      expect(layout[axis]).toMatchObject({
        tickfont: { color: "#e2e8f0" },
        title: { font: { color: "#e2e8f0" } },
        linecolor: "rgba(148,163,184,0.3)",
        zerolinecolor: "rgba(148,163,184,0.3)",
        gridcolor: "rgba(148,163,184,0.15)",
      });
    }
    expect(layout.paper_bgcolor).toBe("rgba(0,0,0,0)");
    expect(layout.plot_bgcolor).toBe("rgba(0,0,0,0)");
    expect(layout.autosize).toBe(true);
    expect(layout.height).toBe(560);
    expect(layout.width).toBeUndefined();
  });

  it("payload values always win over defaults", () => {
    const raw = {
      height: 400,
      font: { color: "#ff0000", size: 14 },
      legend: { bgcolor: "#123456", font: { size: 10 } },
      xaxis: { gridcolor: "#00ff00", tickfont: { size: 9 } },
      yaxis: { title: { text: "score", font: { color: "#0000ff" } } },
    };
    const layout = buildLayout(raw, 1000);
    expect(layout.font).toEqual({ color: "#ff0000", size: 14 });
    expect(layout.legend).toEqual({ bgcolor: "#123456", font: { color: "#e2e8f0", size: 10 } });
    expect(layout.xaxis).toMatchObject({
      gridcolor: "#00ff00",
      tickfont: { color: "#e2e8f0", size: 9 },
      linecolor: "rgba(148,163,184,0.3)",
    });
    expect(layout.yaxis).toMatchObject({
      title: { text: "score", font: { color: "#0000ff" } },
    });
  });

  it("passes annotations through untouched (takeaway colors preserved)", () => {
    const annotations = [{ text: "takeaway", font: { color: "#94a3b8" } }];
    const layout = buildLayout({ annotations }, 1000);
    expect(layout.annotations).toEqual(annotations);
  });

  it("does not mutate the raw layout", () => {
    const raw = { height: 560, xaxis: { gridcolor: "#eee" } };
    const snapshot = JSON.parse(JSON.stringify(raw));
    buildLayout(raw, 1000);
    expect(raw).toEqual(snapshot);
  });
});
