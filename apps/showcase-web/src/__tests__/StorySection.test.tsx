import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { StorySectionData } from "../api";
import { StorySection } from "../components/StorySection";

afterEach(cleanup);

const BASE: StorySectionData = {
  id: "results",
  title: "Results",
  text_md: "Numbers.",
  figures: [],
  metrics_keys: [],
};

describe("StorySection figure layout", () => {
  it("renders a single figure outside a grid with 1/1 caption", () => {
    render(
      <StorySection
        projectId="01-rag-agent"
        section={{ ...BASE, figures: ["retrieval_funnel"] }}
        index={4}
        metrics={null}
      />,
    );
    expect(document.querySelector(".figure-grid")).toBeNull();
    expect(document.querySelectorAll(".figure-frame")).toHaveLength(1);
    expect(document.querySelector(".figure-caption")?.textContent).toContain("1/1");
  });

  it("lays out 2+ figures in a 2-column grid with positional captions", () => {
    render(
      <StorySection
        projectId="01-rag-agent"
        section={{
          ...BASE,
          figures: ["retrieval_funnel", "latency_histogram", "model_comparison"],
        }}
        index={4}
        metrics={null}
      />,
    );
    const grid = document.querySelector(".figure-grid");
    expect(grid).not.toBeNull();
    expect(grid!.querySelectorAll(".figure-frame")).toHaveLength(3);
    const captions = [...document.querySelectorAll(".figure-caption")].map(
      (el) => el.textContent,
    );
    expect(captions[0]).toContain("1/3");
    expect(captions[1]).toContain("2/3");
    expect(captions[2]).toContain("3/3");
  });

  it("renders no figure markup when the section references none", () => {
    render(
      <StorySection projectId="01-rag-agent" section={BASE} index={4} metrics={null} />,
    );
    expect(document.querySelector(".figure-grid")).toBeNull();
    expect(document.querySelector(".figure-frame")).toBeNull();
  });
});
