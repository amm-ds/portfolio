import { cleanup, render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { GlossaryCard } from "../components/GlossaryCard";
import { glossaryEntries } from "../lib/glossary";

afterEach(cleanup);

const TWO = glossaryEntries.filter((e) => e.slug === "baseline" || e.slug === "holdout");

describe("GlossaryCard", () => {
  it("renders the project's used terms with definitions, each linking to its anchor", () => {
    render(
      <MemoryRouter>
        <GlossaryCard terms={TWO} />
      </MemoryRouter>,
    );
    const card = document.querySelector("aside.glossary-card")!;
    expect(card.getAttribute("aria-label")).toContain("Glossary");
    const rows = card.querySelectorAll(".glossary-card-row");
    expect(rows).toHaveLength(2);
    expect(rows[0].querySelector("dt a")?.getAttribute("href")).toBe("/glossary#baseline");
    expect(rows[0].querySelector("dd")?.textContent).toContain("reference model");
    expect(rows[1].querySelector("dt a")?.getAttribute("href")).toBe("/glossary#holdout");
    // no popups anywhere in the card
    expect(card.querySelectorAll('[role="tooltip"]')).toHaveLength(0);
    // full-glossary link in the header hint
    expect(card.querySelector(".glossary-card-hint a")?.getAttribute("href")).toBe("/glossary");
  });

  it("renders nothing when the story uses no glossary terms", () => {
    const { container } = render(
      <MemoryRouter>
        <GlossaryCard terms={[]} />
      </MemoryRouter>,
    );
    expect(container.firstChild).toBeNull();
  });

  it("groups used terms core-first with a divider label before the experiment group", () => {
    const terms = [
      glossaryEntries.find((e) => e.slug === "alns")!,
      glossaryEntries.find((e) => e.slug === "baseline")!,
      glossaryEntries.find((e) => e.slug === "cuped")!,
    ];
    render(
      <MemoryRouter>
        <GlossaryCard terms={terms} />
      </MemoryRouter>,
    );
    // core terms first regardless of input order, experiment terms after
    const rows = [...document.querySelectorAll(".glossary-card-row")];
    expect(rows.map((r) => r.querySelector("dt")!.textContent)).toEqual([
      "baseline",
      "ALNS",
      "CUPED",
    ]);
    // one dl per group, tiny divider label between them
    const lists = document.querySelectorAll("dl.glossary-card-list");
    expect(lists).toHaveLength(2);
    expect(lists[0].querySelectorAll(".glossary-card-row")).toHaveLength(1);
    expect(lists[1].querySelectorAll(".glossary-card-row")).toHaveLength(2);
    const label = document.querySelector(".glossary-card-group-label")!;
    expect(label.textContent).toBe("experiment-specific");
    expect(
      lists[0].compareDocumentPosition(label) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      label.compareDocumentPosition(lists[1]) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("renders a single group with no divider label when the story uses only one group", () => {
    const terms = glossaryEntries.filter((e) => e.slug === "alns" || e.slug === "cuped");
    render(
      <MemoryRouter>
        <GlossaryCard terms={terms} />
      </MemoryRouter>,
    );
    expect(document.querySelectorAll("dl.glossary-card-list")).toHaveLength(1);
    expect(document.querySelector(".glossary-card-group-label")).toBeNull();
  });
});
