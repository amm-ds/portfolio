import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** Recursively collect source files under src/ (excluding tests and this guard). */
function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (entry === "__tests__") continue;
      out.push(...sourceFiles(full));
    } else if (/\.(tsx?|css)$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

/** The About page carries the dated CV, where seniority titles are factual
 * career history — not marketing copy. Everywhere else the ban holds. */
const ABOUT_PAGE = join("src", "pages", "About.tsx");

describe("copy guard: no senior/architect-level wording in src/ (About CV excepted)", () => {
  it("no source file outside the About page mentions 'senior' (case-insensitive)", () => {
    const offenders = sourceFiles("src").filter(
      (f) => f !== ABOUT_PAGE && /senior/i.test(readFileSync(f, "utf8")),
    );
    expect(offenders).toEqual([]);
  });

  it("no source file outside the About page mentions 'architect' (case-insensitive)", () => {
    const offenders = sourceFiles("src").filter(
      (f) => f !== ABOUT_PAGE && /\barchitect\b/i.test(readFileSync(f, "utf8")),
    );
    expect(offenders).toEqual([]);
  });

  it("the About CV states its seniority titles with date ranges", () => {
    const about = readFileSync(ABOUT_PAGE, "utf8");
    expect(about).toMatch(/Senior data scientist/);
    expect(about).toMatch(/\d{4} — \d{4}/);
  });
});
