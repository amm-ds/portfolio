import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlotlyFigure } from "../components/PlotlyFigure";

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
    const [el, data, layout, config] = mocks.react.mock.calls[0];
    expect((el as HTMLElement).dataset.testid).toBe("plotly-retrieval_funnel");
    expect(data).toEqual(PAYLOAD.data);
    expect(layout).toMatchObject({
      height: 560,
      autosize: true,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
    });
    expect(layout.width).toBeUndefined();
    expect(config).toEqual({ responsive: true, displayModeBar: false });
    expect(screen.getByText("fig :: results · 1/1 — Results")).toBeInTheDocument();
  });

  it("clamps layout height to [320, 900]", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ data: [], layout: { height: 1200 } }),
      ),
    );
    render(<PlotlyFigure pid="p" name="tall" />);
    await waitFor(() => expect(mocks.react).toHaveBeenCalled());
    expect(mocks.react.mock.calls[0][2].height).toBe(900);

    cleanup();
    mocks.react.mockClear();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ data: [], layout: { height: 100 } })),
    );
    render(<PlotlyFigure pid="p" name="tiny" />);
    await waitFor(() => expect(mocks.react).toHaveBeenCalled());
    expect(mocks.react.mock.calls[0][2].height).toBe(320);
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

  it("purges the plot on unmount", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(PAYLOAD)));
    const { unmount } = render(<PlotlyFigure pid="p" name="cleanup_fig" />);
    await waitFor(() => expect(mocks.react).toHaveBeenCalled());
    const el = mocks.react.mock.calls[0][0] as HTMLElement;
    unmount();
    await waitFor(() => expect(mocks.purge).toHaveBeenCalledWith(el));
  });
});
