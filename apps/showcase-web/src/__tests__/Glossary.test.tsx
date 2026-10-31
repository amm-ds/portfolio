import { cleanup, render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { glossaryByGroup, glossaryEntries } from "../lib/glossary";
import glossary from "../lib/glossary.json";
import { Glossary } from "../pages/Glossary";

afterEach(cleanup);

const EXPECTED_SLUGS = [
  // core keywords — shared evaluation vocabulary
  "baseline",
  "holdout",
  "backtest",
  "confidence-interval",
  "wape",
  "mase",
  "macro-f1",
  "recall-at-5",
  "uplift",
  "qini-curve",
  "optimality-gap",
  "p50-p95-latency",
  "calibration",
  // experiment-specific methods
  "seasonal-naive",
  "split-conformal-band",
  "mint-reconciliation",
  "alns",
  "vrptw",
  "ece",
  "t-learner",
  "cuped",
  "quantisation",
  "drift-observatory",
  "event-aware-range-f1",
  "plan-act-review-loop",
];

describe("Glossary page", () => {
  it("ships exactly the required terms with stable slugs", () => {
    expect(glossary.map((e) => e.slug)).toEqual(EXPECTED_SLUGS);
    expect(new Set(glossary.map((e) => e.term)).size).toBe(glossary.length);
  });

  it("marks the 13 shared terms as core and the 12 method terms as experiment", () => {
    const { core, experiment } = glossaryByGroup(glossaryEntries);
    expect(core.map((e) => e.slug)).toEqual(EXPECTED_SLUGS.slice(0, 13));
    expect(experiment.map((e) => e.slug)).toEqual(EXPECTED_SLUGS.slice(13));
    for (const entry of glossary) {
      expect(["core", "experiment"]).toContain(entry.group);
    }
  });

  it("keeps every definition at or under 25 words with one example", () => {
    for (const entry of glossary) {
      const words = entry.definition.trim().split(/\s+/).length;
      expect(words, `${entry.slug} definition word count`).toBeLessThanOrEqual(25);
      expect(entry.example.trim().length, `${entry.slug} example`).toBeGreaterThan(0);
    }
  });

  it("renders both labelled groups with the existing dl styling per group", () => {
    render(
      <MemoryRouter>
        <Glossary />
      </MemoryRouter>,
    );
    expect(document.querySelector(".glossary-page .terminal")).not.toBeNull();
    // two labelled groups, core first
    const groups = document.querySelectorAll(".glossary-page section[aria-label]");
    expect(groups).toHaveLength(2);
    expect(groups[0].getAttribute("aria-label")).toBe("core keywords");
    expect(groups[1].getAttribute("aria-label")).toBe("experiment-specific");
    expect(groups[0].querySelector(".section-title")!.textContent).toBe("core keywords");
    expect(groups[1].querySelector(".section-title")!.textContent).toBe("experiment-specific");
    // existing dl styling per group
    const dls = document.querySelectorAll("dl.glossary-list");
    expect(dls).toHaveLength(2);
    const { core, experiment } = glossaryByGroup(glossaryEntries);
    const coreDts = [...dls[0].querySelectorAll("dt")].map((dt) => dt.textContent);
    expect(coreDts).toEqual(core.map((e) => e.term));
    const experimentDts = [...dls[1].querySelectorAll("dt")].map((dt) => dt.textContent);
    expect(experimentDts).toEqual(experiment.map((e) => e.term));
    // each dt exposes the stable slug anchor that story prose links to
    for (const entry of glossary) {
      expect(document.querySelector(`dt[id="${entry.slug}"]`)).not.toBeNull();
    }
    // one dd per term, definition plus example
    expect(dls[0].querySelectorAll("dd")).toHaveLength(core.length);
    expect(dls[1].querySelectorAll("dd")).toHaveLength(experiment.length);
    expect(dls[0].querySelector(".glossary-example")?.textContent).toContain("example:");
  });

  it("sets page metadata", async () => {
    render(
      <MemoryRouter>
        <Glossary />
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.title).toContain("Glossary"));
    expect(document.head.querySelector('meta[name="description"]')).not.toBeNull();
    expect(document.head.querySelector('link[rel="canonical"]')?.getAttribute("href")).toContain(
      "/glossary",
    );
  });
});
