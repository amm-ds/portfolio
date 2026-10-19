import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FigureCard } from "../components/FigureCard";

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

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  mocks.react.mockReset();
  mocks.purge.mockReset();
});

describe("FigureCard", () => {
  it("renders one container with the chart and a commentary band inside it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ data: [{ type: "bar" }], layout: { height: 560 } }),
      ),
    );
    render(
      <FigureCard
        pid="01-rag-agent"
        name="retrieval_funnel"
        caption="Retrieval recall@5 reaches 0.83 once claims are verified."
      />,
    );
    await waitFor(() => expect(mocks.react).toHaveBeenCalledTimes(1));
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
});
