import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { StorySectionData } from "../api";
import { StorySection } from "../components/StorySection";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const BASE: StorySectionData = {
  id: "results",
  title: "Results",
  text_md: "Numbers.",
  figures: [],
  metrics_keys: [],
};

describe("StorySection figure layout (wave 4)", () => {
  it("renders a single figure full-width with a 1/1 caption (no grid)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection
        projectId="01-rag-agent"
        section={{ ...BASE, figures: ["retrieval_funnel"] }}
        index={4}
        metrics={null}
      />,
    );
    expect(document.querySelector(".figure-grid")).toBeNull();
    await waitFor(() =>
      expect(document.querySelectorAll(".figure-frame")).toHaveLength(1),
    );
    expect(document.querySelector(".figure-caption")?.textContent).toContain("1/1");
  });

  it("stacks 2+ figures in a single column with positional captions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
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
    await waitFor(() =>
      expect(document.querySelectorAll(".figure-frame")).toHaveLength(3),
    );
    expect(document.querySelector(".figure-grid")).toBeNull();
    const captions = [...document.querySelectorAll(".figure-caption")].map(
      (el) => el.textContent,
    );
    expect(captions).toHaveLength(3);
    expect(captions[0]).toContain("1/3");
    expect(captions[1]).toContain("2/3");
    expect(captions[2]).toContain("3/3");
  });

  it("renders no figure markup when the section references none", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(<StorySection projectId="01-rag-agent" section={BASE} index={4} metrics={null} />);
    expect(document.querySelector(".figure-frame")).toBeNull();
  });

  it("uses the two-column story layout structure", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no json" }, 404)));
    render(
      <StorySection
        projectId="01-rag-agent"
        section={{ ...BASE, figures: ["f"] }}
        index={0}
        metrics={null}
      />,
    );
    expect(document.querySelector(".story-cols")).not.toBeNull();
    expect(document.querySelector(".story-main")).not.toBeNull();
    expect(document.querySelector(".story-figs")).not.toBeNull();
  });
});
