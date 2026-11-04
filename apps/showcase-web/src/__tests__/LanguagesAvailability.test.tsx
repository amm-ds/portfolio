import { readFileSync } from "node:fs";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { LanguagesAvailability } from "../components/LanguagesAvailability";
import { AVAILABILITY } from "../config";

afterEach(cleanup);

describe("LanguagesAvailability — the three shared fact cards", () => {
  it("renders Languages, Timezone, and Replies cards in one grid", () => {
    render(<LanguagesAvailability />);
    const grid = document.querySelector(".facts-grid")!;
    expect(grid).not.toBeNull();
    expect(grid.querySelector(".languages-card")).not.toBeNull();
    expect(grid.querySelector(".timezone-card")).not.toBeNull();
    expect(grid.querySelector(".replies-card")).not.toBeNull();
    // exactly the three cards — one line each, equal height
    expect(grid.querySelectorAll(".accent-card")).toHaveLength(3);
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

  it("states the timezone and the reply window in bold on their own cards, from config", () => {
    render(<LanguagesAvailability />);
    const tz = [...document.querySelectorAll(".timezone-card .languages-line")];
    expect(tz).toHaveLength(1);
    expect(tz[0].textContent).toBe("Europe/Madrid (CET, UTC+1)");
    const replies = [...document.querySelectorAll(".replies-card .languages-line")];
    expect(replies).toHaveLength(1);
    expect(replies[0].textContent).toBe(
      `within ${AVAILABILITY.replyHours}h on business days`,
    );
    // values only — no "Languages:"/"Timezone:"/"Replies:" labels
    expect(document.querySelector(".facts-grid")!.textContent).not.toMatch(
      /Languages:|Timezone:|Replies:/,
    );
    // centered terminal type
    const css = readFileSync("src/styles.css", "utf8");
    const cardRule = css.match(/\.languages-card,\n\.timezone-card,\n\.replies-card \{[\s\S]*?\n\}/)![0];
    expect(cardRule).toContain("text-align: center;");
    expect(cardRule).toContain("font-family: var(--mono);");
    for (const line of [...tz, ...replies]) {
      expect(line.querySelector("strong")!.textContent).toBe(line.textContent);
    }
  });

  it("lays the three cards out one per row on mobile and three columns from 640px up", () => {
    const css = readFileSync("src/styles.css", "utf8");
    const gridRule = css.match(/\.facts-grid \{[\s\S]*?\n\}/)![0];
    expect(gridRule).toContain("grid-template-columns: 1fr;");
    const threeCol = css.match(
      /@media \(min-width: 640px\) \{\s*\.facts-grid \{[\s\S]*?\n  \}/,
    )![0];
    expect(threeCol).toContain("grid-template-columns: repeat(3, minmax(0, 1fr));");
    // the old Catalan text chip is gone — the flag is drawn, not chipped
    expect(css).not.toContain(".languages-chip");
  });
});
