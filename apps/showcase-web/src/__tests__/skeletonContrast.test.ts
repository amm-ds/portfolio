import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const tokens = readFileSync("src/styles/tokens-base.css", "utf8");
const figures = readFileSync("src/styles/figures.css", "utf8");

function color(block: string, token: string): string {
  const value = block.match(new RegExp(`\\${token}:\\s*(#[0-9a-f]{6});`))?.[1];
  expect(value, `${token} is a six-digit hex color`).toBeDefined();
  return value!;
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((start) => Number.parseInt(hex.slice(start, start + 2), 16) / 255);
  const [r, g, b] = channels.map((value) =>
    value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(foreground: string, background: string): number {
  const [lighter, darker] = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
}

describe("loading skeleton contrast", () => {
  it.each([
    { theme: "dark", selector: ":root[data-theme=\"dark\"] {" },
    { theme: "light", selector: ":root[data-theme=\"light\"] {" },
  ])("keeps $theme text above WCAG AA without relying on animation", ({ selector }) => {
    const start = tokens.indexOf(selector);
    const palette = tokens.slice(tokens.indexOf("{", start), tokens.indexOf("\n}", start));
    expect(contrast(color(palette, "--muted"), color(palette, "--bg"))).toBeGreaterThanOrEqual(4.5);
  });

  it("animates only the decorative border, never text opacity", () => {
    const keyframes = figures.match(/@keyframes skeleton-pulse \{[\s\S]*?\n\}/)?.[0];
    expect(keyframes).toBeDefined();
    expect(keyframes).toContain("border-color:");
    expect(keyframes).not.toContain("opacity");
    expect(figures).not.toMatch(/\.frame-skeleton span\s*\{[^}]*animation:/);
    expect(figures).toMatch(/\.frame-skeleton\s*\{[^}]*color:\s*var\(--muted\);/);
  });
});
