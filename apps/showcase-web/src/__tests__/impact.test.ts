import { describe, expect, it } from "vitest";
import { summaryLine } from "../lib/impact";
import { STORY_SHORT } from "../lib/storyShort";

describe("summary lines (single source: story short_version)", () => {
  it("serves the generated short_version for every baked project", () => {
    for (const id of Object.keys(STORY_SHORT)) {
      expect(summaryLine(id), id).toBe(STORY_SHORT[id]);
    }
  });

  it("every baked entry is a non-empty short_version", () => {
    for (const [id, sv] of Object.entries(STORY_SHORT)) {
      expect(sv, id).toBeTruthy();
      expect(sv!.length, id).toBeGreaterThan(40);
    }
  });

  it("returns undefined for unknown project ids", () => {
    expect(summaryLine("99-unknown")).toBeUndefined();
  });
});
