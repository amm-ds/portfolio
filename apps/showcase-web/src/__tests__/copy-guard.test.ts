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

describe("copy guard: no senior/architect-level wording in src/", () => {
  it("no source file mentions 'senior' (case-insensitive)", () => {
    const offenders = sourceFiles("src").filter((f) =>
      /senior/i.test(readFileSync(f, "utf8")),
    );
    expect(offenders).toEqual([]);
  });
});
