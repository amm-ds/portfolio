import { STORY_SHORT } from "./storyShort";

/** Short "what it achieves" copy for a project — the story's generated
 * `short_version` (scripts/gen_story_short.py bakes every story.yaml into
 * lib/storyShort.ts through the same loader the showcase API uses). Feeds
 * ProjectDetail SEO descriptions, README rows, docs openings, and social
 * text — the projects-index cards take their copy from lib/cardCopy.ts
 * instead, so this is no longer the card source. */
export function summaryLine(projectId: string): string | undefined {
  return STORY_SHORT[projectId] ?? undefined;
}
