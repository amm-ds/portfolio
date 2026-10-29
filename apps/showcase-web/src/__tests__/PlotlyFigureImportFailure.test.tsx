import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PlotlyFigure } from "../components/PlotlyFigure";

vi.mock("plotly.js-dist-min", () => {
  throw new Error("plotly chunk unavailable");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("PlotlyFigure import failure", () => {
  it("uses the existing HTML fallback and clears the native payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ data: [], layout: {} }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const onPayload = vi.fn();
    render(<PlotlyFigure pid="p" name="chunk_failure" onPayload={onPayload} />);

    await waitFor(() => expect(screen.getByTitle("Figure: chunk_failure")).toBeInTheDocument());
    expect(onPayload).toHaveBeenLastCalledWith(null);
  });
});
