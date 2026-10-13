import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { FigureFrame } from "../components/FigureFrame";

afterEach(cleanup);

describe("FigureFrame", () => {
  it("renders the iframe with the figure URL and a mono corner label", () => {
    render(<FigureFrame projectId="01-rag-agent" name="retrieval_funnel" />);
    const iframe = screen.getByTitle("Figure: retrieval_funnel");
    expect(iframe).toHaveAttribute("src", "/projects/01-rag-agent/figures/retrieval_funnel");
    expect(screen.getByText("$ retrieval_funnel")).toBeInTheDocument();
  });

  it("shows a loading skeleton until the iframe onLoad fires", () => {
    render(<FigureFrame projectId="01-rag-agent" name="retrieval_funnel" />);
    const wrap = document.querySelector(".frame-wrap")!;
    expect(wrap.classList.contains("loaded")).toBe(false);
    expect(document.querySelector(".frame-skeleton")).not.toBeNull();

    fireEvent.load(screen.getByTitle("Figure: retrieval_funnel"));
    expect(wrap.classList.contains("loaded")).toBe(true);
    expect(document.querySelector(".frame-skeleton")).toBeNull();
  });

  it("renders no skeleton markup and starts loaded is not assumed", () => {
    render(<FigureFrame projectId="p" name="f" />);
    // before load: iframe present but visually hidden via opacity
    const iframe = screen.getByTitle("Figure: f") as HTMLIFrameElement;
    expect(iframe.style.opacity).not.toBe("1");
  });

  it("renders the story-context caption as `fig :: section · n/total — title`", () => {
    render(
      <FigureFrame
        projectId="01-rag-agent"
        name="fold_stability"
        caption={{
          sectionId: "results",
          index: 2,
          total: 3,
          sectionTitle: "Results",
        }}
      />,
    );
    expect(screen.getByText("fig :: results · 2/3 — Results")).toBeInTheDocument();
  });

  it("omits the caption bar when no story context is provided", () => {
    render(<FigureFrame projectId="01-rag-agent" name="fold_stability" />);
    expect(document.querySelector(".figure-caption")).toBeNull();
  });
});
