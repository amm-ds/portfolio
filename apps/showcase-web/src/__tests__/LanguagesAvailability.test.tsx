import { readFileSync } from "node:fs";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { LanguagesAvailability } from "../components/LanguagesAvailability";
import { AVAILABILITY } from "../config";

afterEach(cleanup);

describe("LanguagesAvailability — the two shared fact cards", () => {
  it("renders a Languages card and a Timezone & replies card in one grid", () => {
    render(<LanguagesAvailability />);
    const grid = document.querySelector(".facts-grid")!;
    expect(grid).not.toBeNull();
    expect(grid.querySelector(".languages-card")).not.toBeNull();
    expect(grid.querySelector(".timezone-card")).not.toBeNull();
    // exactly the two cards — the single-card layout is gone
    expect(grid.querySelectorAll(".accent-card")).toHaveLength(2);
  });

  it("lists the three languages with bold labels, flags only where one exists", () => {
    render(<LanguagesAvailability />);
    // English and Spanish keep their country flags…
    expect(screen.getByText("🇬🇧 English").tagName).toBe("STRONG");
    expect(screen.getByText("🇪🇸 Spanish").tagName).toBe("STRONG");
    // …Catalan never gets a misused country emoji: its item is exactly the
    // word, with the flag DRAWN as an inline SVG instead
    const ca = screen.getByText("Catalan");
    expect(ca.tagName).toBe("STRONG");
    expect(ca.textContent!.trim()).toBe("Catalan");
    expect(ca.closest(".language-item")!.textContent!.trim()).toBe("Catalan");
    expect(ca.closest(".language-item")!.textContent).not.toMatch(/\p{Extended_Pictographic}/u);
  });

  it("draws the Senyera correctly: four red stripes on a yellow field", () => {
    render(<LanguagesAvailability />);
    const flag = document.querySelector(".flag-senyera")! as unknown as SVGElement;
    expect(flag).not.toBeNull();
    // decorative beside the adjacent "Catalan" text
    expect(flag.getAttribute("aria-hidden")).toBe("true");
    const rects = [...flag.querySelectorAll("rect")];
    // one yellow field + four red stripes
    expect(rects).toHaveLength(5);
    expect(rects[0].getAttribute("fill")).toBe("#FCDD09");
    expect(rects[0].getAttribute("width")).toBe("27");
    expect(rects[0].getAttribute("height")).toBe("18");
    const stripes = rects.slice(1);
    expect(stripes).toHaveLength(4);
    for (const stripe of stripes) {
      expect(stripe.getAttribute("fill")).toBe("#DA121A");
      expect(stripe.getAttribute("height")).toBe("2");
      expect(stripe.getAttribute("width")).toBe("27");
    }
    // the four stripes tile the field evenly (9-stripe Senyera: yellow at the
    // edges, red 2nd/4th/6th/8th of nine equal bands)
    const ys = stripes.map((s) => Number(s.getAttribute("y"))).sort((a, b) => a - b);
    expect(ys).toEqual([2, 6, 10, 14]);
  });

  it("states the timezone and the reply window in bold, from config", () => {
    render(<LanguagesAvailability />);
    const lines = [...document.querySelectorAll(".timezone-card .languages-line")];
    expect(lines).toHaveLength(2);
    expect(lines[0].textContent).toBe("Europe/Madrid (CET, UTC+1)");
    expect(lines[1].textContent).toBe(
      `replies within ${AVAILABILITY.replyHours}h on business days`,
    );
    for (const line of lines) {
      expect(line.querySelector("strong")!.textContent).toBe(line.textContent);
    }
  });

  it("lays the two cards out one per row on mobile and two columns from 640px up", () => {
    const css = readFileSync("src/styles.css", "utf8");
    const gridRule = css.match(/\.facts-grid \{[\s\S]*?\n\}/)![0];
    expect(gridRule).toContain("grid-template-columns: 1fr;");
    const twoCol = css.match(
      /@media \(min-width: 640px\) \{\s*\.facts-grid \{[\s\S]*?\n  \}/,
    )![0];
    expect(twoCol).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    // the old Catalan text chip is gone — the flag is drawn, not chipped
    expect(css).not.toContain(".languages-chip");
  });
});
