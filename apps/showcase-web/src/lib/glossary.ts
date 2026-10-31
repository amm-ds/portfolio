import glossaryJson from "./glossary.json";

/** One glossary entry (apps/showcase-web/src/lib/glossary.json is the source).
 * `core` terms recur across case studies; `experiment` terms are specific to
 * one experiment's methods. */
export interface GlossaryEntry {
  term: string;
  slug: string;
  group: "core" | "experiment";
  definition: string;
  example: string;
}

export const glossaryEntries: GlossaryEntry[] = glossaryJson as GlossaryEntry[];

const BY_SLUG = new Map(glossaryEntries.map((e) => [e.slug, e]));

export function glossaryEntryBySlug(slug: string): GlossaryEntry | undefined {
  return BY_SLUG.get(slug);
}

/** Core entries first (glossary.json order), then the experiment-specific ones. */
export function glossaryByGroup(entries: GlossaryEntry[]): {
  core: GlossaryEntry[];
  experiment: GlossaryEntry[];
} {
  return {
    core: entries.filter((e) => e.group === "core"),
    experiment: entries.filter((e) => e.group === "experiment"),
  };
}
