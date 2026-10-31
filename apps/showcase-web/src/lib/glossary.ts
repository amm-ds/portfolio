import glossaryJson from "./glossary.json";

/** One glossary entry (apps/showcase-web/src/lib/glossary.json is the source). */
export interface GlossaryEntry {
  term: string;
  slug: string;
  definition: string;
  example: string;
}

export const glossaryEntries: GlossaryEntry[] = glossaryJson as GlossaryEntry[];

const BY_SLUG = new Map(glossaryEntries.map((e) => [e.slug, e]));

export function glossaryEntryBySlug(slug: string): GlossaryEntry | undefined {
  return BY_SLUG.get(slug);
}
