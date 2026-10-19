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
  it("renders the chart with a footer holding the id line and the caption", async () => {
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
    const footer = document.querySelector(".figure-card-footer")!;
    expect(footer).not.toBeNull();
    expect(footer.querySelector(".figure-id")!.textContent).toBe(
      "fig :: retrieval_funnel",
    );
    expect(footer.querySelector(".figure-comment")!.textContent).toBe(
      "Retrieval recall@5 reaches 0.83 once claims are verified.",
    );
  });

  it("falls back to an id-only footer when no caption exists", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no" }, 404)));
    render(<FigureCard pid="01-rag-agent" name="latency_histogram" />);
    await waitFor(() => expect(screen.getByTitle("Figure: latency_histogram")).toBeInTheDocument());
    const footer = document.querySelector(".figure-card-footer")!;
    expect(footer.querySelector(".figure-id")!.textContent).toBe(
      "fig :: latency_histogram",
    );
    // no commentary paragraph, but the footer itself is still there
    expect(footer.querySelector(".figure-comment")).toBeNull();
  });

  it("keeps the footer next to the iframe fallback chart", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no" }, 404)));
    render(
      <FigureCard pid="05-ml-pipeline-churn" name="pr_curve" caption="Precision dominates above a 0.31 threshold." />,
    );
    await waitFor(() => expect(screen.getByTitle("Figure: pr_curve")).toBeInTheDocument());
    const card = document.querySelector(".figure-card")!;
    expect(card.querySelector("iframe")).not.toBeNull();
    expect(card.querySelector(".figure-comment")!.textContent).toContain(
      "Precision dominates above a 0.31 threshold.",
    );
  });
});
