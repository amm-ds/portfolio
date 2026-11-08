import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildLayout, PlotlyFigure, reskinTraces, scaledHeight } from "../components/PlotlyFigure";
import { ThemeSwitcher } from "../components/ThemeSwitcher";
import { asRecord } from "../lib/records";
import { resetThemeStoreForTests, THEME_STORAGE_KEY } from "../theme/useTheme";

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
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  resetThemeStoreForTests();
  mocks.react.mockResolvedValue(undefined);
});

afterEach(() => {
  resetThemeStoreForTests();
  cleanup();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  mocks.react.mockReset();
  mocks.purge.mockReset();
});

describe("PlotlyFigure", () => {
  it("fetches the JSON payload and renders natively, full-size and re-skinned", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(PAYLOAD));
    vi.stubGlobal("fetch", fetchMock);
    render(<PlotlyFigure pid="01-rag-agent" name="retrieval_funnel" caption="fig :: results · 1/1 — Results" />);

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/projects/01-rag-agent/figures/retrieval_funnel.json",
      ),
    );
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

  it("re-renders with the light layout when the site theme switcher selects light", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(PAYLOAD)));
    render(
      <>
        <ThemeSwitcher />
        <PlotlyFigure pid="p" name="theme_fig" />
      </>,
    );
    await waitFor(() => expect(mocks.react).toHaveBeenCalledTimes(1));
    expect(mocks.react.mock.calls[0][2].font).toEqual({ color: "#e2e8f0" });

    fireEvent.click(screen.getByRole("button", { name: "light" }));
    await waitFor(() => expect(mocks.react).toHaveBeenCalledTimes(2));
    expect(mocks.react.mock.calls[1][2].font).toEqual({ color: "#172433" });
    expect(mocks.react.mock.calls[1][2].xaxis.tickfont).toEqual({ color: "#172433" });
  });

  it("re-skins authored trace colors when the light theme renders the plot", async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "light");
    const data = [
      { type: "scatter", line: { color: "#2dd4bf", width: 2 }, marker: { color: "#fbbf24" } },
      { type: "pie", marker: { colors: ["#a78bfa", "#636EFA"] } },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ data, layout: { height: 560 } })),
    );
    const snapshot = JSON.parse(JSON.stringify(data));
    render(<PlotlyFigure pid="p" name="light_traces" />);
    await waitFor(() => expect(mocks.react).toHaveBeenCalledTimes(1));
    expect(mocks.react.mock.calls[0][1]).toEqual([
      { type: "scatter", line: { color: "#0f766e", width: 2 }, marker: { color: "#b45309" } },
      { type: "pie", marker: { colors: ["#7c3aed", "#636EFA"] } },
    ]);
    // the fetched payload itself is never mutated
    expect(data).toEqual(snapshot);
  });

  it("passes trace data through unchanged when the dark theme renders the plot", async () => {
    const data = [{ type: "scatter", line: { color: "#2dd4bf" } }];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ data, layout: { height: 560 } })),
    );
    const onPayload = vi.fn();
    render(<PlotlyFigure pid="p" name="dark_traces" onPayload={onPayload} />);
    await waitFor(() => expect(mocks.react).toHaveBeenCalledTimes(1));
    // dark hands Plotly the fetched payload's own data array (no reskin copy)
    const payload = onPayload.mock.calls[0][0];
    expect(mocks.react.mock.calls[0][1]).toBe(payload.data);
    expect(mocks.react.mock.calls[0][1]).toEqual(data);
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
    // intentional pending state: mono "> name" corner label + status line
    expect(skeleton).toHaveTextContent("> pending_fig");
    expect(skeleton).toHaveTextContent("rendering figure…");
  });

  it("defers both figure JSON and Plotly until the host nears the viewport", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(PAYLOAD));
    vi.stubGlobal("fetch", fetchMock);
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
    await act(() => new Promise((r) => setTimeout(r, 20)));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(mocks.react).not.toHaveBeenCalled();
    expect(screen.getByTestId("figure-skeleton")).toHaveTextContent("> gated");
    expect(screen.getByText("rendering figure…")).toBeInTheDocument();
    // host enters the viewport → one fetch, then render and skeleton retirement
    act(() => {
      ioCallback!([{ isIntersecting: true }]);
    });
    await waitFor(() => expect(mocks.react).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledTimes(1);
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

  it("applies high-contrast light-theme defaults when requested", () => {
    const layout = buildLayout({ height: 560 }, 1000, "light");
    expect(layout.font).toEqual({ color: "#172433" });
    expect(layout.legend).toEqual({
      bgcolor: "rgba(0,0,0,0)",
      font: { color: "#172433" },
    });
    for (const axis of ["xaxis", "yaxis"]) {
      expect(layout[axis]).toMatchObject({
        tickfont: { color: "#172433" },
        title: { font: { color: "#172433" } },
        linecolor: "rgba(78,98,118,0.48)",
        zerolinecolor: "rgba(78,98,118,0.48)",
        gridcolor: "rgba(78,98,118,0.22)",
      });
    }
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

  it("remaps the template colorway in light mode and leaves it identical in dark", () => {
    const colorway = ["#2dd4bf", "#38bdf8", "#636EFA"];
    const raw = { height: 560, template: { layout: { colorway, font: { size: 14 } } } };
    const dark = buildLayout(raw, 1000, "dark");
    expect(dark.template).toBe(raw.template);
    const light = buildLayout(raw, 1000, "light");
    expect(asRecord(asRecord(light.template).layout).colorway).toEqual([
      "#0f766e",
      "#0284c7",
      "#636EFA",
    ]);
    expect(asRecord(asRecord(light.template).layout).font).toEqual({ size: 14 });
    // the raw template is never mutated
    expect(colorway).toEqual(["#2dd4bf", "#38bdf8", "#636EFA"]);
  });

  it("remaps a colorway nested directly on the template and skips missing ones", () => {
    const nested = buildLayout(
      { template: { colorway: ["#fbbf24"] } },
      1000,
      "light",
    );
    expect(asRecord(nested.template).colorway).toEqual(["#b45309"]);
    const bare = buildLayout({ height: 560 }, 1000, "light");
    expect(bare.template).toBeUndefined();
  });

  it("forces readable chrome over dark-authored payload colors in light mode only", () => {
    const raw = {
      height: 560,
      font: { color: "#e2e8f0", family: "Inter" },
      legend: { font: { color: "#e2e8f0", size: 12 }, bgcolor: "rgba(0,0,0,0)" },
      xaxis: {
        tickfont: { color: "#e2e8f0", size: 11 },
        gridcolor: "#293548",
        linecolor: "#3b4a61",
        zerolinecolor: "#3b4a61",
        title: { text: "score", font: { color: "#e2e8f0" } },
      },
    };
    const dark = buildLayout(raw, 1000, "dark");
    // dark preserves the authored chrome (and non-color props survive)
    expect(asRecord(dark.font)).toEqual({ color: "#e2e8f0", family: "Inter" });
    expect(asRecord(asRecord(dark.legend).font)).toEqual({ color: "#e2e8f0", size: 12 });
    expect(asRecord(dark.xaxis).gridcolor).toBe("#293548");
    expect(asRecord(asRecord(dark.xaxis).tickfont)).toEqual({ color: "#e2e8f0", size: 11 });

    const light = buildLayout(raw, 1000, "light");
    expect(asRecord(light.font)).toEqual({ color: "#172433", family: "Inter" });
    expect(asRecord(asRecord(light.legend).font)).toEqual({ color: "#172433", size: 12 });
    const lx = asRecord(light.xaxis);
    expect(asRecord(lx.tickfont)).toEqual({ color: "#172433", size: 11 });
    expect(lx.gridcolor).toBe("rgba(78,98,118,0.22)");
    expect(lx.linecolor).toBe("rgba(78,98,118,0.48)");
    expect(lx.zerolinecolor).toBe("rgba(78,98,118,0.48)");
    expect(asRecord(lx.title).font).toEqual({ color: "#172433" });
    // raw payload untouched
    expect(asRecord(raw.xaxis).gridcolor).toBe("#293548");
  });

  it("themes the figure title and subplot axes in light mode only", () => {
    const raw = {
      height: 560,
      title: {
        text: "Corpus composition<br><span style='font-size:12.5px;color:#cbd5e1'>tail capped</span>",
        font: { color: "#e2e8f0", size: 18 },
      },
      xaxis2: { tickfont: { color: "#e2e8f0" }, gridcolor: "#293548", linecolor: "#3b4a61" },
    };
    const dark = buildLayout(raw, 1000, "dark");
    const darkTitle = asRecord(dark.title);
    expect(darkTitle.font).toEqual({ color: "#e2e8f0", size: 18 });
    expect(darkTitle.text).toContain("color:#cbd5e1");
    expect(asRecord(dark.xaxis2).gridcolor).toBe("#293548");

    const light = buildLayout(raw, 1000, "light");
    const lightTitle = asRecord(light.title);
    expect(asRecord(lightTitle.font)).toEqual({ color: "#172433", size: 18 });
    expect(String(lightTitle.text)).toContain("font-size:12.5px;color:#475569");
    expect(String(lightTitle.text)).not.toContain("#cbd5e1");
    const lx2 = asRecord(light.xaxis2);
    expect(asRecord(lx2.tickfont).color).toBe("#172433");
    expect(lx2.gridcolor).toBe("rgba(78,98,118,0.22)");
    expect(lx2.linecolor).toBe("rgba(78,98,118,0.48)");
  });
});

describe("reskinTraces", () => {
  const AUTHORED = [
    {
      type: "scatter",
      line: { color: "#2dd4bf", width: 2 },
      marker: { color: "#38bdf8", size: 8 },
      fillcolor: "rgba(45,212,191,0.25)",
      y: [1, 2, 3],
    },
    { type: "pie", marker: { colors: ["#a78bfa", "#f472b6", "#636EFA"] } },
    { type: "bar", marker: { color: ["#2dd4bf", "#64748b"] } },
  ];

  it("remaps authored dark-palette colors for the light theme", () => {
    const out = reskinTraces(AUTHORED, "light");
    expect(out[0]).toEqual({
      type: "scatter",
      line: { color: "#0f766e", width: 2 },
      marker: { color: "#0284c7", size: 8 },
      fillcolor: "rgba(45,212,191,0.25)", // rgba washes are not table keys
      y: [1, 2, 3],
    });
    expect(out[1]).toEqual({
      type: "pie",
      marker: { colors: ["#7c3aed", "#db2777", "#636EFA"] }, // plotly default untouched
    });
    expect(out[2]).toEqual({ type: "bar", marker: { color: ["#0f766e", "#475569"] } });
  });

  it("matches color keys case-insensitively", () => {
    const out = reskinTraces([{ line: { color: "#2DD4BF" } }], "light");
    expect(out[0]).toEqual({ line: { color: "#0f766e" } });
  });

  it("returns dark-theme traces unchanged (identity)", () => {
    expect(reskinTraces(AUTHORED, "dark")).toBe(AUTHORED);
  });

  it("passes unknown colors through untouched", () => {
    const out = reskinTraces([{ line: { color: "#123456" }, fillcolor: "#abcdef" }], "light");
    expect(out[0]).toEqual({ line: { color: "#123456" }, fillcolor: "#abcdef" });
  });

  it("does not mutate the input payload", () => {
    const snapshot = JSON.parse(JSON.stringify(AUTHORED));
    reskinTraces(AUTHORED, "light");
    expect(AUTHORED).toEqual(snapshot);
  });
});
