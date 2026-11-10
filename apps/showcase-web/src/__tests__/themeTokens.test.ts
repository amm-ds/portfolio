import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const tokens = readFileSync("src/styles/tokens-base.css", "utf8");
const shell = readFileSync("src/styles/shell.css", "utf8");

/** Extract the body of a top-level selector block. */
function block(css: string, selector: string): string {
  // the selector must include its opening brace so comment mentions of the
  // selector name don't match
  const start = css.indexOf(selector);
  expect(start, `selector ${selector} present`).toBeGreaterThan(-1);
  const open = css.indexOf("{", start);
  const close = css.indexOf("\n}", open);
  return css.slice(open, close);
}

describe("theme tokens", () => {
  it("declares the dark palette as the default and the light palette under [data-theme='light']", () => {
    expect(tokens).toContain(":root,\n:root[data-theme=\"dark\"] {");
    expect(tokens).toContain(":root[data-theme=\"light\"] {");
    // the dark palette keeps the site's original terminal values…
    const dark = block(tokens, ":root[data-theme=\"dark\"] {");
    expect(dark).toContain("--bg: #0f172a;");
    expect(dark).toContain("--surface: #1e293b;");
    expect(dark).toContain("--accent: #2dd4bf;");
    expect(dark).toContain("--secondary: #38bdf8;");
    // …and the light palette is the high-contrast daylight counterpart
    const light = block(tokens, ":root[data-theme=\"light\"] {");
    for (const declaration of [
      "--bg: #f5f8fc;",
      "--surface: #ffffff;",
      "--surface-hover: #f4f7fb;",
      "--border: #b8c6d6;",
      "--border-soft: #d6dee8;",
      "--text: #172433;",
      "--muted: #4e6276;",
      "--dim: #536578;",
      "--accent: #14b8a6;",
      "--accent-bright: #0a5750;",
      "--secondary: #0369a1;",
      "--danger: #b4233a;",
      "--warning: #92400e;",
      "--ok: #047857;",
    ]) {
      expect(light).toContain(declaration);
    }
    // both themes pin the color scheme so native controls follow
    expect(dark).toContain("color-scheme: dark;");
    expect(light).toContain("color-scheme: light;");
  });

  it("keeps structural tokens theme-independent", () => {
    // spacing/type/radius are declared exactly once, in the plain :root block
    for (const name of ["--radius", "--gap-card", "--gap-section", "--mono", "--sans"]) {
      expect(tokens.match(new RegExp(`\\${name}:`, "g"))!.length).toBe(1);
    }
  });

  it("exposes a chart palette that matches the demo charts in dark and stays contrast-safe in light", () => {
    const dark = block(tokens, ":root[data-theme=\"dark\"] {");
    const light = block(tokens, ":root[data-theme=\"light\"] {");
    // dark values mirror the committed chart constants exactly
    for (const declaration of [
      "--chart-teal: #2dd4bf;",
      "--chart-teal-light: #5eead4;",
      "--chart-pink: #f472b6;",
      "--chart-amber: #fbbf24;",
      "--chart-gray: #94a3b8;",
      "--chart-lilac: #a78bfa;",
      "--chart-violet: #c4b5fd;",
      "--chart-sky: #38bdf8;",
      "--chart-green: #4ade80;",
      "--chart-history: #64748b;",
      "--chart-cursor: #f472b6;",
    ]) {
      expect(dark).toContain(declaration);
    }
    // light values are darker variants, safe on the light paper
    for (const declaration of [
      "--chart-teal: #0f766e;",
      "--chart-teal-light: #0d9488;",
      "--chart-pink: #be185d;",
      "--chart-amber: #b45309;",
      "--chart-lilac: #7c3aed;",
      "--chart-violet: #6d28d9;",
      "--chart-sky: #0369a1;",
      "--chart-green: #15803d;",
      "--chart-history: #64748b;",
      "--chart-cursor: #be185d;",
    ]) {
      expect(light).toContain(declaration);
    }
  });

  it("themes the previously hardcoded surfaces through semantic tokens", () => {
    const dark = block(tokens, ":root[data-theme=\"dark\"] {");
    const light = block(tokens, ":root[data-theme=\"light\"] {");
    // dark values reproduce the former literals…
    for (const declaration of [
      "--terminal-bg: #0b1120;",
      "--hero-grid-line: rgba(148, 163, 184, 0.05);",
      "--flow-canvas-dot: rgba(148, 163, 184, 0.16);",
      "--chip-blue-text: #7dd3fc;",
      "--chip-blue-bg: rgba(56, 189, 248, 0.08);",
      "--chip-green-bg: rgba(45, 212, 191, 0.08);",
      "--table-head-bg: rgba(45, 212, 191, 0.06);",
      "--notice-bg: rgba(45, 212, 191, 0.06);",
      "--attribution-bg: rgba(15, 23, 42, 0.8);",
      "--flow-violet: #a78bfa;",
      "--code-keyword: #f472b6;",
    ]) {
      expect(dark).toContain(declaration);
    }
    // …and every one of them is re-declared for light
    for (const name of [
      "--terminal-bg",
      "--terminal-shadow",
      "--terminal-shadow-hero",
      "--hero-grid-line",
      "--flow-canvas-dot",
      "--code-bg",
      "--figure-band-bg",
      "--input-bg",
      "--table-head-bg",
      "--notice-bg",
      "--attribution-bg",
      "--chip-blue-text",
      "--chip-blue-bg",
      "--chip-blue-bg-strong",
      "--chip-blue-border",
      "--chip-blue-border-soft",
      "--chip-green-bg",
      "--chip-green-border",
      "--chip-domain-bg",
      "--chip-domain-border",
      "--shadow-node",
      "--shadow-node-active",
      "--shadow-float",
      "--shadow-chip",
      "--shadow-shape",
      "--code-keyword",
      "--flow-violet",
      "--accent-glow",
      "--accent-ink",
    ]) {
      expect(light).toContain(`${name}:`);
    }
  });
});

describe("nav theme switcher styles", () => {
  it("styles the switcher as a compact segmented control with an accent active state", () => {
    const switcher = block(shell, ".theme-switcher {");
    expect(switcher).toContain("display: inline-flex;");
    expect(switcher).toContain("background: var(--bg);");
    expect(switcher).toContain("border: 1px solid var(--border-soft);");
    expect(switcher).toContain("border-radius: 7px;");
    expect(switcher).toContain("padding: 0.1rem;");

    const option = block(shell, ".theme-switcher__option {");
    expect(option).toContain("min-height: 28px;");
    expect(option).toContain("padding: 0.1rem 0.42rem;");
    expect(option).toContain("font-family: var(--mono);");
    expect(option).toContain("color: var(--muted);");
    expect(option).toContain("background: transparent;");

    const active = block(shell, ".theme-switcher__option.is-active {");
    expect(active).toContain("color: var(--accent);");
    expect(active).toContain("border-color: var(--accent);");
    expect(active).toContain("background: var(--accent-glow);");

    const hover = block(shell, ".theme-switcher__option:hover:not(:disabled) {");
    expect(hover).toContain("color: var(--accent);");
    expect(hover).toContain("border-color: var(--accent);");
  });

  it("lets the nav links wrap so the switcher stays usable at mobile widths", () => {
    const navLinks = block(shell, ".nav-links {");
    expect(navLinks).toContain("flex-wrap: wrap;");
    expect(shell).toContain(
      "@media (max-width: 640px) {\n  .nav-links {\n    gap: 0.6rem 0.9rem;\n  }\n}",
    );
  });
});
