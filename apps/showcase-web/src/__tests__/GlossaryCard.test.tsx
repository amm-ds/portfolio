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
});
