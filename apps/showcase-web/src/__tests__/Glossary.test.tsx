import { cleanup, render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import glossary from "../lib/glossary.json";
import { Glossary } from "../pages/Glossary";

afterEach(cleanup);

const EXPECTED_SLUGS = [
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
];

describe("Glossary page", () => {
  it("ships exactly the required terms with stable slugs", () => {
    expect(glossary.map((e) => e.slug)).toEqual(EXPECTED_SLUGS);
    expect(new Set(glossary.map((e) => e.term)).size).toBe(glossary.length);
  });

  it("keeps every definition at or under 25 words with one example", () => {
    for (const entry of glossary) {
      const words = entry.definition.trim().split(/\s+/).length;
      expect(words, `${entry.slug} definition word count`).toBeLessThanOrEqual(25);
      expect(entry.example.trim().length, `${entry.slug} example`).toBeGreaterThan(0);
    }
  });

  it("renders every term in an accessible terminal-styled description list", () => {
    render(
      <MemoryRouter>
        <Glossary />
      </MemoryRouter>,
    );
    expect(document.querySelector(".glossary-page .terminal")).not.toBeNull();
    const dl = document.querySelector("dl.glossary-list")!;
    expect(dl).not.toBeNull();
    const dts = [...dl.querySelectorAll("dt")];
    expect(dts.map((dt) => dt.textContent)).toEqual(glossary.map((e) => e.term));
    // each dt exposes the stable slug anchor that story prose links to
    for (const entry of glossary) {
      expect(dl.querySelector(`dt[id="${entry.slug}"]`)).not.toBeNull();
    }
    // one dd per term, definition plus example
    const dds = dl.querySelectorAll("dd");
    expect(dds).toHaveLength(glossary.length);
    expect(dds[0].querySelector(".glossary-example")?.textContent).toContain("example:");
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
